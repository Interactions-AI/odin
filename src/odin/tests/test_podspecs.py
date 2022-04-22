import pytest
import pickle
import os
import time
import yaml
from collections import namedtuple
from typing import Dict
from unittest.mock import MagicMock

from odin.core import create_graph, read_pipeline_config
from odin.dag import topo_sort
from odin.k8s import TaskManager, Task, Handle, StatusType, task_to_pod_spec
from odin.executor import Executor
from odin.store import MemoryStore

YAML_CONFIG = """
name: test-job
tasks:

- name: shm
  image: blah:800000.6
  command: stuff
  args: []
  mounts:
   - name: data
     path: "/data"
     claim: "myclaim"
   - path: /dev/shm
     name: dshm
  ephem_volumes:
   - name: dshm
     type: emptyDir
     medium: Memory
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
  security_context:
     fs_group: 1152
     run_as_user: 1000
     run_as_group: 1000
  cpu:
     limits: 4.5
     requests: 1.0
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

SRC_DIR = os.path.dirname(os.path.abspath(__file__))

import json

def test_task_to_pod_specs():
    context, tasks = read_pipeline_config('RANDOM_WORK', 'RANDOM_ROOT', 'RANDOM_DATA', YAML_CONFIG, pipeline_id="xxxx")
    print(tasks)
    for idx, task in enumerate(tasks):
        task_obj = Task.from_dict(task)
        # pod_specs is type V1PodSpec
        pod_specs = task_to_pod_spec(task_obj, container_name="xxyy")

        with open(f"{SRC_DIR}/test_pod_{idx}.json", 'r') as ref_f:
            ref_specs = json.load(ref_f)
        assert ref_specs == pod_specs.to_dict()

        # writes the reference
        #print(f"{SRC_DIR}")
        #with open(f"{SRC_DIR}/test_pod_{idx}.json", 'w') as ref_f:
        #    json.dump(pod_specs.to_dict(), ref_f)
