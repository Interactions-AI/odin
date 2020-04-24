"""Pipeline primitive
"""
import asyncio
from datetime import datetime
import json
import logging
from hashlib import sha1
from itertools import chain
from typing import Dict, List, Optional, Union, AsyncIterator, Any
from baseline.utils import listify
from mead.utils import order_json
from odin.core import create_graph, is_reference, parse_reference, extract_outputs, _get_child_name
from odin.dag import topo_sort_parallel, dot_graph, CycleError
from odin.k8s import Task, TaskManager, KubernetesTaskManager, StatusType, SubmitError
from odin.store import Store, Cache, MemoryCache
from odin.utils.hash import hash_files, hash_args

LOGGER = logging.getLogger('odin')


def hash_outputs(outputs: Dict[str, Union[str, List[str]]]) -> str:
    """Hash the outputs of a task.

    :param outputs: The list of output files to hash.
    :returns: The hash of the outputs.
    """
    LOGGER.debug("Hashing %s", outputs)
    output_hashes = {k: hash_files(listify(v)) for k, v in outputs.items()}
    LOGGER.debug(output_hashes)
    out_hash = sha1(json.dumps(order_json(output_hashes)).encode('utf-8')).hexdigest()
    LOGGER.debug("Output hash: %s", out_hash)
    return out_hash


async def hash_inputs(task: Task, sched: TaskManager) -> str:
    """Hash all things that are inputs to a task, the containers, the arguments, and input data.

    :param task: The Task that will be run.
    :param sched: The scheduler, needed to get the container hashes.
    :returns: The hash that describes the inputs to the Task.
    """
    LOGGER.debug("Hashing inputs for %s", task.name)
    arg_hash = hash_args(task.command, task.args)
    LOGGER.debug("Argument hash: %s", arg_hash)
    container_hash = await sched.hash_task(task)
    LOGGER.debug("Container hash: %s", container_hash)
    input_hash = hash_files(task.inputs) if task.inputs is not None else ""
    LOGGER.debug("Input data hash: %s", input_hash)
    full_hash = sha1(f"{arg_hash}{''.join(container_hash)}{input_hash}".encode('utf-8')).hexdigest()
    LOGGER.debug("Full input hash: %s", full_hash)
    return full_hash


class PipelineStatus:
    """Enum of pipeline status.

    Not a real enum to get easier access to string values.
    """

    BUILDING = "BUILDING"
    RUNNING = "RUNNING"
    TERMINATED = "TERMINATED"
    DONE = "DONE"


class Executor:
    """A task scheduler backed by kubernetes

    Pipelines are long-running tasks and therefore implemented with
    `asyncio` and `async/await`.  There are 2 components
    that an `Executor` manages: the tasks `Store` and the `TaskManager`

    Tasks that have no dependencies with each other are scheduled to be run in parallel
    """

    def __init__(self, store: Store, sched: TaskManager = None, cache: Optional[Cache] = None):
        """Create a Pipeline, inject params

        :param store: The `Store` provides access to the job DB
        :param sched: The `TaskManager` handles Task management
        :param cache: The key value store used to track input and output hashes for tasks.
        """
        self.sched = sched if sched else KubernetesTaskManager(store)
        self.store = store
        self.cache = cache if cache else MemoryCache()

    @staticmethod
    def _task_to_entry(my_id: str, child_task_id: str, name: str, task: Task) -> object:
        return {
            Store.PIPE_ID: child_task_id,
            Store.PARENT: my_id,
            "command": task.command,
            "name": name,
            "image": task.image,
            "args": task.args,
            "resource_type": task.resource_type,
            "node_selector": task.node_selector,
            "pull_policy": task.pull_policy,
            "num_gpus": task.num_gpus,
            "outputs": task.outputs,
            "inputs": task.inputs,
        }

    def extract_outputs(self, pipeline_id: str, reference: str) -> Any:
        """Pull data out of the job store based on the reference path.

        :param pipeline_id: The id of the pipeline that is currently running.
        :param reference: The reference in the form `^a.b` to extract data from.
        :returns: The data pulled out..
        """
        assert is_reference(reference)
        task, *path = parse_reference(reference)
        label = _get_child_name(pipeline_id, task)
        task_entry = self.store.get(label)
        return extract_outputs(path, task_entry)

    def rewrite_references(self, pipeline_id: str, reference: str) -> Any:
        """Pull data out of the job store to replace subsections of arguments.

        :param pipeline_id: The id of the pipelines that is currently running.
        :param reference: The argument with references in the form `^a.b` if you
            wrap these in curlies like `example-{^a.b}-more` you can replace just
            one part of it.
        :returns: The input with references replaced with the data from the job store.
        """
        starts = []
        new_ref = []
        for i, char in enumerate(reference):
            # If we are at the start of a possible reference span
            if char == "{":
                starts.append(i + 1)
            # We hit the end of a span
            elif char == "}":
                # If this is a } without a start it must just be something the user has in text so skip
                if not starts:
                    new_ref.append(char)
                    continue
                # Grab the opening of this span
                start = starts.pop()
                if not starts:
                    to_sub = reference[start:i]
                    # Recursively substitute in the open span
                    sub = self.rewrite_references(pipeline_id, reference[start:i])
                    # If this open span wasn't a real substitution add the `{` and `}` back
                    if sub == to_sub:
                        sub = f"{{{sub}}}"
                    # Save out the substituted value
                    new_ref.append(sub)
            else:
                # If outside of a span collect the text for later use
                if not starts:
                    new_ref.append(char)
        # If there is a span that is never closed copy out everything since then
        if starts:
            new_ref.append(reference[starts[0]-1:])
        # Combine the substituted sections into a single string
        reference = "".join(new_ref)
        # If the whole string is a reference just substitute it (base case)
        if is_reference(reference):
            return self.extract_outputs(pipeline_id, reference)
        # If the whole thing isn't a reference just return as is (with possible sub references subsituted)
        return reference

    async def run(  # pylint: disable=too-many-locals,too-many-statements,too-many-branches,missing-yield-type-doc
        self, my_id: str, task_id: str, rev_ver: str, tasks: List[Dict]
    ) -> AsyncIterator[str]:
        """Run a pipeline by stepping through sets of tasks

        This (async) method manages scheduling a series of
        tasks, launching each, updating the parent
        status in the jobs DB, and waiting for
        each task to complete.  A pipeline records its
        success or failure directly to the jobs DB

        :param my_id: The pipeline unique identifier
        :param task_id: The task unique identifier
        :param rev_ver: The revision version if available
        :param tasks: The tasks to execute (with their params)
        :raises ValueError: If the pipeline definition fails.
        :raises KeyError: If the pipeline definition fails.
        :return: AsyncIterator[str]
        """
        try:
            graph = create_graph(tasks)
            named_graph = {tasks[k]['name']: [tasks[v]['name'] for v in vs] for k, vs in graph.items()}
            LOGGER.info(dot_graph(named_graph))
            groups = topo_sort_parallel(graph)
        except (KeyError, ValueError, CycleError) as exc:
            self.store.set(
                {
                    Store.PIPE_ID: my_id,
                    Store.JOB_NAME: task_id,
                    Store.REV_VER: rev_ver,
                    Store.STATUS: PipelineStatus.TERMINATED,
                    Store.EXECUTED: [],
                    Store.WAITING: [],
                    Store.EXECUTING: [],
                    Store.SUBMIT_TIME: datetime.utcnow(),
                    Store.COMPLETION_TIME: None,
                    Store.ERROR_MESSAGE: str(exc),
                }
            )
            yield f"Pipeline {my_id} terminated"
            raise exc
        self.store.set(
            {
                Store.PIPE_ID: my_id,
                Store.JOB_NAME: task_id,
                Store.REV_VER: rev_ver,
                Store.STATUS: PipelineStatus.BUILDING,
                Store.EXECUTED: [],
                Store.WAITING: [],
                Store.EXECUTING: [],
                Store.SUBMIT_TIME: datetime.utcnow(),
                Store.COMPLETION_TIME: None,
                Store.ERROR_MESSAGE: None,
            }
        )
        task_list = []
        waiting = []

        for group in groups:
            task_group = []
            waiting_group = []
            for task in group:
                child_task_id = tasks[task]['name']
                task_obj = Task.from_dict(tasks[task])
                task_entry = Executor._task_to_entry(my_id, child_task_id, tasks[task]['_name'], task_obj)
                self.store.set(task_entry)
                task_group.append(task_obj)
                waiting_group.append(child_task_id)
            task_list.append(task_group)
            waiting.append(waiting_group)

        my_status = self.store.get(my_id)
        my_status['status'] = PipelineStatus.RUNNING
        all_tasks = list(chain(*waiting))
        my_status[Store.WAITING] = all_tasks
        my_status[Store.JOBS] = all_tasks
        self.store.set(my_status)

        for task_group in task_list:
            # We are about to move this first set from waiting to executing so remove it from waiting.
            waiting.pop(0)
            # Last rounds tasks are still in the EXECUTING state so set them to EXECUTED
            if my_status[Store.EXECUTING]:
                my_status[Store.EXECUTED].extend(my_status[Store.EXECUTING])
            my_status[Store.EXECUTING] = [task_obj.name for task_obj in task_group]
            my_status[Store.WAITING] = list(chain(*waiting))
            self.store.set(my_status)

            running = []
            for task_obj in task_group:
                # Replace inputs and args with values generated by previous tasks
                task_obj.inputs = (
                    [self.rewrite_references(my_id, task_input) for task_input in task_obj.inputs]
                    if task_obj.inputs is not None else None
                )
                task_obj.args = [self.rewrite_references(my_id, a) for a in task_obj.args]
                task_entry = self.store.get(task_obj.name)
                task_entry['args'] = task_obj.args
                task_entry['inputs'] = task_obj.inputs
                self.store.set(task_entry)

                if task_obj.outputs is not None:
                    try:
                        in_hash = await hash_inputs(task_obj, self.sched)
                    except SubmitError as exc:
                        my_status[Store.STATUS] = PipelineStatus.TERMINATED
                        my_status[Store.ERROR_MESSAGE] = str(exc)
                        self.store.set(my_status)
                        yield f"Pipeline {my_id} terminated"
                        raise exc
                    out_hash = hash_outputs(task_obj.outputs)
                    prev_hash = self.cache[in_hash]
                    if out_hash == prev_hash:
                        LOGGER.info("%s is cached and will not be run", task_obj.name)
                        task_status = self.store.get(task_obj.name)
                        task_status.update({Store.RESOURCE_ID: Store.CACHED})
                        self.store.set(task_status)
                        my_status[Store.EXECUTING].remove(task_obj.name)
                        my_status[Store.EXECUTED].append(task_obj.name)
                        self.store.set(my_status)
                        continue
                    LOGGER.info("Hash of outputs for %s doesn't match stored hash, re-running.", task_obj.name)
                LOGGER.info("Submitting %s", task_obj.name)
                yield f"Submitting {task_obj.name}"
                try:
                    resource_id = self.sched.submit(task_obj)
                except SubmitError as exc:
                    my_status[Store.STATUS] = PipelineStatus.TERMINATED
                    my_status[Store.ERROR_MESSAGE] = str(exc)
                    self.store.set(my_status)
                    yield f"Pipeline {my_id} terminated"
                    raise exc

                task_status = self.store.get(task_obj.name)
                task_status.update({Store.RESOURCE_ID: resource_id, Store.SUBMIT_TIME: datetime.utcnow()})
                self.store.set(task_status)
                running.append(task_obj)

            # This processes jobs in the order they finish, we should eventually
            # be able to kill the other jobs if one gets terminated.
            for future in asyncio.as_completed(map(self.sched.wait_for, running)):
                task_obj = await future
                LOGGER.info("Done running %s", task_obj.name)
                yield f"Done running {task_obj.name}"
                task_status = self.store.get(task_obj.name)
                task_status[Store.COMPLETION_TIME] = datetime.utcnow()
                self.store.set(task_status)
                completion_status = self.sched.status(task_obj)

                if StatusType(completion_status.status_type) is not StatusType.SUCCEEDED:
                    my_status[Store.STATUS] = PipelineStatus.TERMINATED
                    my_status[Store.ERROR_MESSAGE] = (
                        completion_status.message
                        if completion_status.message is not None
                        else f"Task `{task_obj.name}` failed"
                    )
                    self.store.set(my_status)
                    LOGGER.error([my_status, completion_status.message])
                    continue

                if self.store.get(task_obj.name).get(Store.REQUEST_EARLY_EXIT, False):
                    LOGGER.info("%s requested an early exit. Pipeline will complete now.", task_obj.name)
                    my_status[Store.STATUS] = PipelineStatus.DONE

                my_status[Store.EXECUTING].remove(task_obj.name)
                my_status[Store.EXECUTED].append(task_obj.name)
                self.store.set(my_status)

                if task_obj.outputs is not None:
                    LOGGER.info("Saving the hash of %s's output", task_obj.name)
                    self.cache[in_hash] = hash_outputs(task_obj.outputs)
            if my_status[Store.STATUS] is PipelineStatus.DONE or my_status[Store.STATUS] is PipelineStatus.TERMINATED:
                if my_status[Store.STATUS] == PipelineStatus.TERMINATED:
                    yield f"Pipeline: {my_id} Terminated"
                waiting = []
                break

        my_status[Store.COMPLETION_TIME] = datetime.utcnow()
        if my_status[Store.EXECUTING] and my_status[Store.STATUS] != PipelineStatus.TERMINATED:
            my_status[Store.EXECUTED].extend(my_status[Store.EXECUTING])
            my_status[Store.EXECUTING] = []
        assert not waiting

        if my_status[Store.STATUS] != PipelineStatus.TERMINATED:
            my_status[Store.STATUS] = PipelineStatus.DONE
        self.store.set(my_status)
