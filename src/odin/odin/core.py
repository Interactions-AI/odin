"""Core components for odin
"""
import os
import re
import inspect
import logging
from collections import defaultdict
from string import Template
from typing import Dict, Union, List, Tuple, Any, Optional
import yaml
import shortid
from baseline.utils import listify, is_sequence
from odin.dag import Graph


SHORT_ID = shortid.ShortId()
DEPENDENCY_KEY = 'depends'
TASK_LIST = 'tasks'
ROOT_PATH = 'ROOT_PATH'
WORK_PATH = 'WORK_PATH'
DATA_PATH = 'DATA_PATH'
RUN_PATH = 'RUN_PATH'
TASK_PATH = 'TASK_PATH'
PIPE_ID = 'PIPE_ID'
TASK_IDS = 'TASK_IDS'
TASK_ID = 'TASK_ID'
TASK_NAME = 'TASK_NAME'
K8S_NAME = re.compile(r"[a-z0-9-\.]+")
REFERENCE_KEY = re.compile(r"^\^")


LOGGER = logging.getLogger('odin')


def is_reference(key: Any) -> bool:
    """Is this key a reference to output from elsewhere in the chores.

    A reference has the form ^chore(.output)? where `chore` is the name of the
    node you are consuming output from and `output` is either a name or a
    number to tell which part of the output to take.

    :param key: A key to test
    :returns: `True` if its a reference
    """
    return isinstance(key, str) and key.startswith('^')


def parse_reference(ref: str) -> Tuple[str, ...]:
    """Convert the references in to a list of lookups.

    The reference is assumed to be of the form `^X.Y...` or just `X`

    :param ref: A reference to parse
    :returns: A tuple based on dot splitting and removing the `^`
    """
    parts = ref.split('.')
    parts[0] = REFERENCE_KEY.sub("", parts[0])  # Remove beginning `^` if there.
    return parts


def extract_outputs(path: List[str], results: Dict) -> Union[Any, List[Any]]:
    """Pull data out of results according to ref.

    :param path: The data location.
    :param results: The data to pull content from.
    :returns: The data or None if it could not be found.
    """
    miss = False
    for key in path:
        if key not in results:
            miss = True
            break
        results = results[key]
    return results if not miss else None


def wire_inputs(inputs: Dict, results: Dict, chore: 'Chore') -> Dict:
    """Replace the reference inputs with the output files.

    References are assumed to be of the form `^X.Y` or just `X`.
    If the former, the chore and sub-field of the results Dict
    are returned.  In the latter case, the whole Dict associated
    with the results is returned

    :param inputs: A dictionary of inputs
    :param results: A dictionary of upstream results
    :param chore: The chore function that will be called.
    :returns: The substituted input dictionary
    """
    for key, values in inputs.items():
        if is_sequence(values):
            new_vs = []
            for value in values:
                if is_reference(value):
                    new_vs.append(extract_outputs(parse_reference(value), results))
                else:
                    new_vs.append(value)
            inputs[key] = new_vs
        else:
            if is_reference(values):
                inputs[key] = extract_outputs(parse_reference(values), results)
    # Get the signature of the function
    sig = inspect.signature(chore)
    # Bind the args we populated with inputs
    bound = sig.bind_partial(**inputs)
    for param in sig.parameters.values():
        # Look at all params and if they haven't been bound (they are not
        # present in the bound args and therefore were not in inputs) default
        # them to `None` in inputs. If this param has a default value we
        # don't need to add it to inputs
        if param.name not in bound.arguments and param.default is param.empty:
            inputs[param.name] = None
    return inputs


def create_graph(  # pylint: disable=too-many-nested-blocks,too-many-branches
    task_list: List[Dict], external_inputs: Dict = {}
) -> Graph:
    """Convert task list into a graph.

    There is a link between a chores if a chore references another in
    any of it's inputs or if the chore is listed in a key called `depends`
    (`depends` is used for forced control flow when not a explicit input dep)

    :param task_list: A list of dictionaries describing tasks
    :param external_inputs: A dictionary of external inputs
    :raises ValueError: If a task name contains a `.` or there is a phantom dependency
    :returns: A DAG
    """
    graph: Graph = defaultdict(set)
    name2idx = {task.get('_name', task.get('name')): i for i, task in enumerate(task_list)}
    idx2name = {i: k for k, i in name2idx.items()}
    for name in name2idx:
        if '.' in name:
            raise ValueError(f"Names cannot contain `.` found {name} ")

    for dst, task in enumerate(task_list):
        if DEPENDENCY_KEY in task:
            for src in listify(task[DEPENDENCY_KEY]):
                src = src[1:] if src.startswith('^') else src
                if src not in name2idx:
                    raise ValueError(f"Dependency `{src}` of node `{idx2name[dst]}` not found in graph.")
                graph[name2idx[src]].add(dst)
        for values in task.values():
            values = listify(values)
            for value in values:
                if is_reference(value):
                    lookups = parse_reference(value)
                    src = lookups[0]
                    if src not in external_inputs:
                        if src not in name2idx:
                            raise ValueError(f"Dependency `{src}` of node `{idx2name[dst]}` not found in graph.")
                        graph[name2idx[src]].add(dst)
                    else:
                        LOGGER.info("No dependency required in this graph from %s to %s", dst, src)
    for dst in range(len(task_list)):
        if dst not in graph:
            graph[dst] = set()
    return graph


def format_output(output) -> Union[Dict, List]:
    """Convert the outputs into a consistent format.

    The outputs are dicts. When functions return lists/scalars they are
    converted into dicts with numbers (as str's) for the keys.

    :param output Output to convert
    :return the formatted output
    """
    if is_sequence(output):
        result = {}
        for i, out in enumerate(listify(output)):
            result[str(i)] = out
        output = result
    return output


def _to_kwargs(params: Dict) -> str:
    """Stringify the params as an arg list

    :param params: The params
    :return: A string representation of the parameters in the for `param=arg`.
    """
    return ", ".join(f"{k}={v}" for k, v in params.items() if k != 'name')


def _generate_name(prefix: str) -> str:
    """This generates a new name from the provided prefix suffixed by a shortid

    :param prefix: A provided prefix
    :returns: A unique name that is a combination of the prefix and a shortid
    """
    short_id = SHORT_ID.generate().lower().replace('_', '-')
    return f'{prefix}-{short_id}j'


def validate_pipeline_name(name: str) -> bool:
    """Check if a pipeline name is valid.

    From the k8s docs (https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#names):
        By convention, the names of Kubernetes resources should be up to maximum length of 253 characters and consist
        of lower case alphanumeric characters, -, and ., but certain resources have more specific restrictions.

    :param name: The name to validate
    :returns: Is the name valid of not?
    """
    return K8S_NAME.fullmatch(name) is not None


def _get_child_name(parent_name: str, name: str) -> str:
    """Child pod names are canonical keyed off the unique id of the parent

    :param parent_name: The parent name
    :param name: The child task name
    :returns: A new id that is unique for the child
    """
    return f'{parent_name}--{name}'


def read_pipeline_config(  # pylint: disable=too-many-locals
    work_dir: str,
    root_dir: str,
    data_dir: Optional[str] = None,
    main_file: Optional[str] = None,
    pipeline_id: Optional[str] = None,
) -> Tuple[Dict, List[Dict]]:
    """Read in the pipeline configuration from a directory

    The actual flow is specified in a `main.yml` inside this directory.
    The names that are given in the file are relative to the flow, whose actual
    name is some randomized version based on the `name` given.   We need some
    way to refer to these jobs by other jobs in the same flow.  To facilitate,
    use a context and properly substitute user variables which may be present
    in the command arguments

    :param work_dir: A directory pointing to this workflow
    :param root_dir: A directory pointing to all global config info
    :param data_dir: A directory pointing to where this workflow saves data
    :param main_file: Optional config path.  Defaults to `{work_dir}/main.yml`
    :raises ValueError: If there are multiple tasks of the same name.
    :return: A tuple of the context and the interpolated task list
    """
    template_file = main_file if main_file else f'{work_dir}/main.yml'
    if os.path.isfile(template_file):
        LOGGER.info("Loading file: %s", template_file)
        with open(template_file) as read_file:
            flow = yaml.load(read_file, Loader=yaml.FullLoader)
    else:
        LOGGER.info("Loading YAML string: ...%s", format(template_file[-20:]))
        flow = yaml.load(template_file, Loader=yaml.FullLoader)
    basename = flow.get('name', 'flow')
    if not validate_pipeline_name(basename):
        raise ValueError(f"Pipeline name must match {K8S_NAME.pattern}, got {basename}")
    if pipeline_id is None:
        my_id = _generate_name(basename)
    else:
        my_id = f"{basename}-{pipeline_id}"

    tasks = flow['tasks']
    child_job_ids = [_get_child_name(my_id, task['name']) for task in tasks]
    data_dir = data_dir if data_dir is not None else work_dir
    run_dir = os.path.join(data_dir, my_id)

    context = {
        WORK_PATH: work_dir,
        ROOT_PATH: root_dir,
        PIPE_ID: my_id,
        TASK_IDS: child_job_ids,
        DATA_PATH: data_dir,
        RUN_PATH: run_dir,
    }
    task_names = set()
    for i in range(len(tasks)):
        task_name = tasks[i]['name']
        if task_name in task_names:
            raise ValueError(f"Task names must be unique. Found {task_name} twice.")
        task_names.add(task_name)
        tasks[i]['name'] = child_job_ids[i]
        context[TASK_ID] = child_job_ids[i]
        context[TASK_NAME] = task_name
        task_dir = os.path.join(run_dir, task_name)
        os.makedirs(task_dir, exist_ok=True)
        context[TASK_PATH] = task_dir
        tasks[i]['_name'] = task_name
        for j, arg in enumerate(tasks[i].get('args', [])):
            tasks[i]['args'][j] = Template(arg).substitute(context)
            if arg != tasks[i]['args'][j]:
                LOGGER.info("Interpolated: %s", tasks[i]['args'][j])

    del context[TASK_ID]
    del context[TASK_NAME]
    del context[TASK_PATH]
    return context, tasks
