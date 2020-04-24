import pytest
import time
import yaml
from collections import namedtuple
from typing import Dict
from unittest.mock import MagicMock

from odin.core import create_graph, read_pipeline_config
from odin.dag import topo_sort
from odin.k8s import TaskManager, Task, Handle, StatusType
from odin.executor import Executor
from odin.store import MemoryStore

YAML_CONFIG = """
name: test-job
tasks:

- name: train-sst2-2
  image: mead-ml/mead-gpu:1.3.0
  command: mead-train
  args:
   - "--datasets"
   - "${ROOT_PATH}/datasets.yml"
   - "--config"
   - "${WORK_PATH}/sst2.json"
   - "--reporting"
   - "xpctl"
   - "--xpctl:label"
   - "${TASK_ID}"
  mount:
     name: data
     path: "/data"
     claim: "myclaim"
  num_gpus: 1
  depends: [train-sst2-1]

- name: hello-python
  image: python:3.6.4-jessie
  command: python3
  args:
   - "-c"
   - "print('hello ${TASK_ID}')"

- name: train-sst2-1
  image: mead-ml/mead-gpu:latest
  command: mead-train
  args:
   - "--datasets"
   - "${ROOT_PATH}/datasets.yml"
   - "--config"
   - "${WORK_PATH}/sst2.json"
   - "--reporting"
   - "xpctl"
   - "--xpctl:label"
   - "${TASK_ID}"
  mount:
     name: data
     path: "/data"
     claim: "myclaim"
  num_gpus: 1
  depends: [hello-python]

- name: goodbye-python
  image: python:3.6.4-jessie
  command: python3
  depends: [train-sst2-1, train-sst2-2]
  args:
   - "-c"
   - "print('goodbye cruel world')"
"""


MockStatus = namedtuple('MockStatus', 'phase, status_type')


class MockTaskManager(TaskManager):
    """Base interface for a task manager

    """

    def __init__(self):
        """Base init for a task manager

        :param api: A Swagger API that we can use to interface with k8s
        :param namespace: The namespace to schedule into
        """
        super().__init__()

    def submit(self, job: Task, **kwargs) -> Dict:
        """Submit something to k8s
        """
        return {}

    def status(self, handle: Handle) -> Dict:
        """Get progress
        """
        return MockStatus("Succeeded", StatusType.SUCCEEDED)

    def kill(self, handle: Handle) -> Dict:
        """Kill a resource
        """
        raise Exception("Cant kill")

    async def wait_for(self, handle: Handle) -> Dict:
        time.sleep(1)
        return MagicMock(name=handle.name) if isinstance(handle, str) else handle

    def results(self, handle: Handle) -> Dict:
        return {}


def test_scheduling_order():
    graph = create_graph(yaml.load(YAML_CONFIG, Loader=yaml.FullLoader)['tasks'])
    sequence = topo_sort(graph)
    assert sequence == [1, 2, 0, 3]


def test_substitution():
    no_sub = yaml.load(YAML_CONFIG, Loader=yaml.FullLoader)['tasks']
    context, tasks = read_pipeline_config('RANDOM_WORK', 'RANDOM_ROOT', 'RANDOM_DATA', YAML_CONFIG)

    pipe_id = context['PIPE_ID']
    task_name = no_sub[0]['name']
    assert f'{pipe_id}--{task_name}' == context['TASK_IDS'][0]
    assert context['TASK_IDS'] == [task['name'] for task in tasks]
    assert context['ROOT_PATH'] == 'RANDOM_ROOT'
    assert context['WORK_PATH'] == 'RANDOM_WORK'

    assert tasks[0]['args'][1] == "RANDOM_ROOT/datasets.yml"
    assert tasks[0]['args'][:-1] == tasks[2]['args'][:-1]
    assert tasks[0]['args'][-1] != tasks[2]['args'][-1]

    assert tasks[1]['args'][-1] == "print('hello {}')".format(context['TASK_IDS'][1])


def test_pipeline():
    import asyncio

    context, tasks = read_pipeline_config('RANDOM_WORK', 'RANDOM_ROOT', 'RANDOM_DATA', YAML_CONFIG)
    store = MemoryStore()
    loop = asyncio.get_event_loop()

    try:
        p = Executor(store, MockTaskManager())
        pipe_id = context['PIPE_ID']

        async def run():
            async for _ in p.run(pipe_id, 'jid', '1', tasks):
                pass

        loop.run_until_complete(run())
        for tasks in context['TASK_IDS']:
            print(store.get(tasks))
    finally:
        loop.close()
