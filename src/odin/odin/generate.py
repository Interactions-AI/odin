"""Generate odin configs from mead configs
"""
import argparse
import getpass
import inspect
import logging
import os
import re
import stat
import shutil
from copy import deepcopy
from itertools import chain
from typing import Dict, Union, Optional, List, Tuple, Any

from baseline.utils import read_config_file, str2bool, listify, import_user_module, idempotent_append
from odin import Path
from odin.utils.yaml import write_yaml


LOGGER = logging.getLogger('odin')
FILE_PERM = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH
ALWAYS = 'Always'
IF_NOT_PRESENT = 'IfNotPresent'
NEVER = 'Never'


def set_permissions(file_name: str) -> None:
    """Update permissions on a file to be rw-rw-rw-

    :param file_name: The name of the file.
    """
    if os.path.isfile(file_name):
        os.chmod(file_name, FILE_PERM)


def generate_mead_task(  # pylint: disable=too-many-locals
    template: Dict,
    task_name: str,
    config_name: str,
    mead_image: str,
    claim: str,
    datasets: Optional[str] = None,
    embeddings: Optional[str] = None,
    data_files: Optional[Dict[str, str]] = None,
    depends: Optional[Union[str, List[str]]] = None,
    gpus: int = 1,
    addons: Dict[str, str] = None,
    pull_policy: str = ALWAYS,
) -> Dict:
    """Generate a task (an element in the task list in main.yaml) that is a mead job.

    :param template: The skeleton mead task to fill in.
    :param task_name: The name of this task.
    :param config_name: The name of the mead config file for this task.
    :param mead_image: The name of the mead docker image to use.
    :param claim: The name of the pvc to use.
    :param datasets: The path to a dataset index
    :param embeddings: The path to a embeddings index
    :param data_files: A mapping of dataset overrides.
    :param depends: Tasks that this one needs to be scheduled after.
    :param gpus: The number of gpus this task wants.
    :param addons: A mapping of addon filenames to source code.
    :param pull_policy: Should k8s repull your containers.

    :returns:
        Dict, The task that runs a mead job in an odin pipeline.
    """
    template = deepcopy(template)

    template['name'] = task_name
    template['image'] = mead_image
    template['num_gpus'] = gpus
    template['mount']['claim'] = claim
    template['pull_policy'] = pull_policy

    if depends:
        template['depends'] = deepcopy(listify(depends))

    # Update the config location.
    config_idx = template['args'].index('--config') + 1
    template['args'][config_idx] = config_name

    # Update the dataset location.
    if datasets:
        template['args'].append('--datasets')
        template['args'].append(datasets)
    if embeddings:
        template['args'].append('--embeddings')
        template['args'].append(embeddings)

    if addons:
        template['args'].append("--modules")
        for addon in addons:
            template['args'].append(f"${{WORK_PATH}}/{addon}")

    data_files = data_files if data_files else {}
    for ds, df in data_files.items():
        template['args'].append(f'--mod_{ds}_file')
        template['args'].append(df)

    return template


def generate_hpctl_task(
    template: Dict,
    image: str,
    claim: str,
    name: str,
    config_file: str,
    models: List[str],
    addons: Optional[List[str]] = None,
    seed: Optional[int] = None,
    pull_policy: str = ALWAYS,
) -> Dict:
    """Generate an hpctl task based on the template.

    :param template: The template
    :param image: The image to use
    :param claim: The pvc claim to use
    :param name: What should this task is called
    :param config_file: The location of the config file to sample from
    :param models: The models that will be trained on these samples
        This controls how many configs are sampled
    :param addons: Sampling addons that are used to sample the config
    :param seed: A seed for the RNG when sampling
    :param pull_policy: When should you pull the image
    :returns: The task definition
    """
    addons = addons if addons is not None else []
    template = deepcopy(template)

    template['name'] = name
    template['image'] = image
    template['mount']['claim'] = claim
    template['pull_policy'] = pull_policy

    # Update the config location
    template['args'][0] = re.sub(r"{{sample-config}}", config_file, template['args'][0])

    for model in models:
        template['args'].append(model)

    if seed is not None:
        template['args'].extend(['--seed', seed])

    if addons:
        template['args'].extend(chain(['--modules'], addons))

    return template


def generate_template_task(
    template: Dict,
    image: str,
    claim: str,
    template_file: str,
    task: str,
    depends: Optional[Union[str, List[str]]] = None,
    pull_policy: str = ALWAYS,
) -> Tuple[Dict, str]:
    """Create a odin-template task.

    :param template: The skeleton to fill in
    :param image: The docker container to use
    :param claim: The name of the k8s data pvc
    :param template_file: The path to the sampling directive file
    :param task: The baseline task we are templating for
    :param depends: Tasks that need to be run before this one
    :param pull_policy: Should we try to pull the image

    :returns: The template file and the output file name.
    """

    template = deepcopy(template)
    template['image'] = image
    template['mount']['claim'] = claim
    template['pull_policy'] = pull_policy

    template['name'] = f'template-{task}'

    if depends:
        template['depends'] = deepcopy(listify(depends))

    template['args'][0] = template_file

    output_idx = template['args'].index('--output') + 1
    template['args'][output_idx] = re.sub(r"{{task}}", task, template['args'][output_idx])

    template['args'][template['args'].index('--task') + 1] = task

    return template, template['args'][output_idx]


def generate_chore_task(
    template: Dict, odin_image: str, claim: str, depends: Optional[Union[str, List[str]]], pull_policy: str = ALWAYS
) -> Dict:
    """Generate a task (an element in the task list in main.yaml) that is a chore job.

    :param template: The skeleton of a chore task to fill in.
    :param odin_image: The name of the odin docker image to use.
    :param claim: The name of the pvc to use.
    :param depends: Tasks that need to run before this one.
    :param pull_policy: Should k8s repull your containers.

    :returns:
        Dict, The task that will run a single chore file in an odin pipeline.
    """
    template = deepcopy(template)

    template['image'] = odin_image
    template['mount']['claim'] = claim
    template['pull_policy'] = pull_policy

    if depends:
        template['depends'] = deepcopy(listify(depends))

    return template


def generate_chore_yaml(
    template_loc: str,
    slack: bool = True,
    slack_web_hook: Optional[str] = None,
    git_commit: bool = False,
    k8s_bump: bool = False,
    selected: bool = False,
) -> List:
    """Generate the yaml for the chore file.

    :param template_loc: The location of the various pre-defined chore files.
    :param slack: Should we have a slack chore?
    :param slack_web_hook: A custom endpoint for final slack messages.
    :param git_commit: Should we have a git commit chore?
    :param k8s_bump: Should we have a chore to bump a k8s version?
    :param selected: Should we send a message about what as selected to export?

    :returns:
        List, The chores definitions. If there are no chores it return and empty list
    """
    chores = []
    git_depends = []
    if git_commit:
        chores.extend(read_config_file(os.path.join(template_loc, 'git-chore.yml')))
        git_depends = [c['name'] for c in chores]
    if slack:
        slack_chore = read_config_file(os.path.join(template_loc, 'slack-chore.yml'))
        if slack_web_hook is not None:
            slack_chore['webhook'] = slack_web_hook
        if git_depends:
            slack_chore['depends'] = deepcopy(listify(slack_chore.get('depends', [])) + git_depends)
        chores.append(slack_chore)
    if selected:
        selected_chore = read_config_file(os.path.join(template_loc, 'selected-chore.yml'))
        if slack_web_hook is not None:
            selected_chore['webhook'] = slack_web_hook
        chores.append(selected_chore)
    return chores


def generate_eval_task(  # pylint: disable=too-many-locals
    template: Dict,
    task_name: str,
    image: str,
    claim: str,
    eval_task: str,
    eval_dataset: str,
    config: Dict,
    depends: Union[str, List[str]],
    addons: Optional[List[str]] = None,
    pull_policy: str = ALWAYS,
    **kwargs,
) -> Dict:
    """Generate the task yaml for a mead eval task.

    :param template: The skeleton of the file to add
    :param task_name: The name of this mead-eval task
    :param image: The docker image to use for this task
    :param claim: The pvc to use for this task
    :param eval_task: The task you are evaluating
    :param eval_dataset: The dataset you are evaluating with
    :param config: The config of the model you are evaluating
    :param depends: Tasks that need to be run before this one.
    :param addons: addons this task needs to use.
    :param pull_policy: When should you try to pull a new container
    :param kwargs: extra argument mapping that are converted to cli args
      `--key value for key, value in kwargs.items()`
    :returns: The mead-eval yaml
    """
    depends = listify(depends)
    idempotent_append(eval_task, depends)
    config = deepcopy(config)
    template = deepcopy(template)
    template['name'] = task_name
    template['image'] = image
    template['mount']['claim'] = claim
    template['pull_policy'] = pull_policy
    template['depends'] = deepcopy(depends)

    model_idx = template['args'].index('--model') + 1
    template['args'][model_idx] = re.sub(r"{{eval-task}}", eval_task, template['args'][model_idx])

    # Point this at the bundle created by the mead-train you are testing.
    label_idx = template['args'].index('--odin:label') + 1
    template['args'][label_idx] = re.sub(r"{{eval-task}}", eval_task, template['args'][label_idx])

    # The dataset is the new evaluation dataset
    template['args'][template['args'].index('--dataset') + 1] = eval_dataset
    # Task and backend can be pulled from the config
    template['args'][template['args'].index('--task') + 1] = config['task']
    template['args'][template['args'].index('--backend') + 1] = config['backend']

    # Pull reader type from the config and set that in the args
    reader_params = config.get('reader', config.get('loader'))
    reader_type = reader_params.pop('type') if 'type' in reader_params else reader_params.pop('reader_type')
    template['args'][template['args'].index('--reader') + 1] = reader_type
    # Extract features from the config and convert to the cli format
    features = reader_params.pop("named_fields", {})
    if features:
        template['args'].append('--features')
        for idx, name in features.items():
            template['args'].append(f"{name}:{idx}")

    # Extract the pair suffix from the config and use it from cli (because the overrides can't handle lists)
    pair_suffix = reader_params.pop("pair_suffix", [])
    if pair_suffix:
        template['args'].append('--pair_suffix')
        for suf in pair_suffix:
            template['args'].append(suf)

    # Convert the reset of the reader params to cli args
    for flag, value in reader_params.items():
        template['args'].extend(chain([f"--reader:{flag}"], map(str, listify(value))))

    # Extract trainer type
    trainer = config['train'].pop("type", config['train'].pop("trainer_type", "default"))
    # Extract verbose options
    verbose_options = config['train'].pop('verbose', {})

    # Set the rest of the trainer options as cli args
    template['args'].extend(['--trainer', trainer])
    for flag, value in config['train'].items():
        template['args'].extend(chain([f"--trainer:{flag}"], map(str, listify(value))))

    # If verbose is a bool (like in tagger config) convert to dict
    if isinstance(verbose_options, bool):
        verbose_options = {'console': 1}
    # Convert verbose options to cli options
    for flag, value in verbose_options.items():
        template['args'].extend(chain([f"--verbose:{flag}"], map(str, listify(value))))

    if addons:
        module_idx = template['args'].index('--modules') + 1
        for addon in addons:
            template['args'].insert(module_idx, addon)

    # Set any kwargs to cli args.
    for flag, value in kwargs.items():
        template['args'].extend([f"--{flag}", value])

    return template


def generate_export_task(  # pylint: disable=too-many-locals
    template: Dict,
    odin_image: str,
    claim: str,
    models: List[str],
    task: str,
    dataset_name: str,
    depends: List[str],
    metric: str = 'acc',
    export_policy: Optional[str] = None,
    pull_policy: str = ALWAYS,
    models_claim: Optional[str] = None,
) -> Dict:
    """Generate a task (an element in the task list for the pipeline) that is a export job.

    :param template: The skeleton version of the export task.
    :param odin_image: The name of the odin docker image to use.
    :param claim: The name of the pvc to use.
    :param models: A list of models to evaluate.
    :param task: The name of the task that was used in training.
    :param dataset_name: The name of the dataset used to train on.
    :param depends: The tasks that need to be run before this one
    :param metric: The metric to use when comparing models.
    :param export_policy: How to make a decision if we should export things.
    :param pull_policy: Should k8s repull your containers.
    :param models_claim: The name of the /models claim.

    :returns:
        Dict, The task the represents a export job to run in the odin pipeline.
    """
    if not export_policy:
        return {}
    depends = listify(depends)
    template = deepcopy(template)
    template['image'] = odin_image
    template['mounts'][0]['claim'] = claim
    template['pull_policy'] = pull_policy

    # Add the models pvc to the mounts.
    if models_claim:
        template['mounts'].append({"name": "models", "path": "/models", 'claim': models_claim})

    # For each model we trained add it to `args` just after `--models`
    models_idx = template['args'].index('--models') + 1
    template['args'].pop(models_idx)
    for model in (f"${{PIPE_ID}}--{name}" for name in models):
        template['args'].insert(models_idx, model)

    template['args'][template['args'].index('--task') + 1] = task
    template['args'][template['args'].index('--type') + 1] = export_policy
    template['args'][template['args'].index('--metric') + 1] = metric

    template['depends'] = deepcopy(listify(depends))
    return template


def make_user_dir(root_path: Path, uname: str) -> Path:
    """Create the directory where we will store all the users pipelines.

    :param root_path: Where all the pipelines live
    :param uname: The user making the pipelines name
    :returns: The path to the user dir
    """
    user_dir = os.path.join(root_path, uname)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir


def make_pipeline_dir(root_path: Path, uname: str, pipeline_name: str, clobber: bool = False) -> Path:
    """Create the directory for the pipeline at {root_path}/{uname}/{pipeline_name}."""
    pipeline_loc = os.path.join(root_path, uname, pipeline_name)
    if os.path.exists(pipeline_loc):
        if not clobber:
            raise FileExistsError(f"{pipeline_loc} already exists!")
        shutil.rmtree(pipeline_loc)
    os.makedirs(pipeline_loc)
    return pipeline_loc


def find_const_config_prop(key: str, configs: Dict) -> Any:
    """Find a value by key and make sure it is the same across all configs.

    :param key: The key to search for
    :param configs: The configs to check the value in
    :raises ValueError: If the configs have conflicting information
    :returns: The value found.
    """
    found = set(c[key] for c in configs)
    if len(found) > 1:
        raise ValueError(f"More than one {key} was found in the configs, {found}")
    return found.pop()


def generate_pipeline(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    root_path: str,
    uname: str,
    pipeline_name: str,
    configs: Dict[str, Dict],
    datasets: Optional[Union[str, List[Dict[str, str]]]],
    embeddings: Optional[Union[str, List[Dict[str, str]]]],
    models: int = 1,
    gpus: int = 1,
    metric: str = 'acc',
    export_policy: Optional[str] = None,
    slack: bool = True,
    slack_web_hook: Optional[str] = None,
    git_commit: bool = False,
    mead_image: Optional[str] = None,
    odin_image: Optional[str] = None,
    claim_name: Optional[str] = None,
    pull_policy: str = ALWAYS,
    clobber: bool = False,
    addons: Dict[str, Dict[str, str]] = None,
    mead_eval_dataset: Optional[str] = None,
    models_claim: Optional[str] = None,
    export_to_dev: bool = False,
    template: Optional[Union[Dict, List, str]] = None,
    hpctl: bool = False,
    hpctl_addons: List[Dict[str, str]] = None,
    seed: Optional[int] = None,
    **kwargs,
) -> str:
    """Generate a pipeline.

    This function can generate an odin pipeline from a mead config and some configuration options.

    The pipeline will be named {uname}/{pipeline_name}

    If you use the hpctl flag then hpctl will be used in the pipeline to generate
    configs for each model on the fly. This records it's seed (which is also settable)
    to allow for reproducability

    If a mead_eval dataset is provided a mead-eval task is created for each training task.

    If an export_type is provided then an export task will be created that depends on all the
    previous mead jobs. All of the models are considered by the export decider.

    If any chores are requested (slack, git_commit, etc.) a chore task is added. This depends on
    either the export job (if it exists) otherwise it depends on the mead tasks.

    :param root_path: The location to write the pipeline to.
    :param uname: The username of the person generating the pipeline.
    :param pipeline_name: The name of the pipeline.
    :param configs: The mead configs for the each model, mapped form name to config.
    :param datasets: A custom datasets index definition (or location) to use.
    :param embeddings: A custom embeddings index definition (or location) to use.
    :param models: The number of models to train.
    :param gpus: The number of gpus to train each model with.
    :param metric: The metric to compare models when exporting.
    :param export_policy: The export criteria to use.
    :param slack: Should we send a slack notification?
    :param slack_web_hook: A custom endpoint for final slack messages.
    :param git_commit: Should we commit an exported model to git?
    :param mead_image: The docker image for the mead config.
    :param odin_image: The docker image for the odin config.
    :param claim_name: The name of the pvc to use.
    :param pull_policy: Should k8s repull your containers.
    :param clobber: Should you overwrite an old pipeline?
    :param addons: A mapping of addon file names to source code is contained
       in a mapping keyed by the model name.
    :param mead_eval_dataset: The dataset to use in mead-eval.
    :param models_claim: The name of the model pvc for exporting.
    :param export_to_dev: Should the models be copied to raven-dev.
    :param template: The raven-template sampling directives or a file.
    :param hpctl: Should we run hpctl sampling at the start of the file?
    :param hpctl_addons: Sampling addons needed from hpctl, not support atm
    :param seed: A seed to set hpctl's RNG.
    :param kwargs: Absorb extra args for now.
    :returns: str, The name of the generated pipeline
    """

    pipeline_loc = make_pipeline_dir(root_path, uname, pipeline_name, clobber)

    pipeline = {}
    pipeline['name'] = pipeline_name if len(configs) == 1 else f"{pipeline_name}-auto"

    # Write out any addons that and config needs
    addons = addons if addons is not None else {}
    for _, addon in addons.items():
        for addon_file, addon_source in addon.items():
            addon_file = os.path.join(pipeline_loc, addon_file)
            with open(addon_file, 'w') as wf:
                wf.write(addon_source)
                set_permissions(addon_file)
    for config in configs.values():
        config.pop('modules', None)

    # Write out datasets
    if datasets:
        if isinstance(datasets, list):
            dataset_file = os.path.join(pipeline_loc, 'datasets.yml')
            write_yaml(datasets, dataset_file)
            set_permissions(dataset_file)
            datasets = os.path.join("${WORK_PATH}", "datasets.yml")
    # Write out embeddings
    if embeddings:
        if isinstance(embeddings, list):
            embeddings_file = os.path.join(pipeline_loc, 'embeddings.yml')
            write_yaml(embeddings, embeddings_file)
            set_permissions(embeddings_file)
            embeddings = os.path.join("${WORK_PATH}", "embeddings.yml")

    template_loc = os.path.join(root_path, 'templates')
    images, claims = get_images(template_loc, mead_image, odin_image, claim_name, models_claim)

    templating_template = read_config_file(os.path.join(template_loc, 'templating-template.yml'))
    mead_template = read_config_file(os.path.join(template_loc, 'mead-task-template.yml'))
    mead_eval_template = read_config_file(os.path.join(template_loc, 'mead-eval-template.yml'))
    export_template = read_config_file(os.path.join(template_loc, 'export-template.yml'))
    hpctl_template = read_config_file(os.path.join(template_loc, 'hpctl-template.yml'))
    chore_template = read_config_file(os.path.join(template_loc, 'chore-template.yml'))

    task = find_const_config_prop('task', configs.values())
    dataset = find_const_config_prop('dataset', configs.values())

    all_tasks = []
    data_files = {}
    dep = None
    # Create the template task to generate datasets
    if template:
        if isinstance(template, str):
            template_file = template
        else:
            file_name = 'sample-template.yml'
            write_yaml(template, os.path.join(pipeline_loc, file_name))
            template_file = os.path.join("${WORK_PATH}", file_name)
        template_task, output_file = generate_template_task(
            templating_template, images['template'], claims['data'], template_file, task, pull_policy=pull_policy
        )
        all_tasks.append(template_task)
        data_files = {dataset: f"{output_file}.{dataset}" for dataset in ("train", "valid", "test")}
        dep = template_task['name']

    trained_models = []
    evals = []
    for config_name, config in configs.items():
        addon = addons[config_name]
        config_file = os.path.join(pipeline_loc, f"{config_name}.yml")
        write_yaml(config, config_file)
        set_permissions(config_file)
        config_file = os.path.join("${WORK_PATH}", f"{config_name}.yml")
        if hpctl:
            hpctl_task = generate_hpctl_task(
                hpctl_template,
                images['hpctl'],
                claims['data'],
                f"{config_name}-sample",
                config_file,
                [f"{config_name}-{i}" for i in range(models)],
                seed=seed,
                pull_policy=pull_policy,
            )
            all_tasks.append(hpctl_task)
            dep = hpctl_task['name']
            config_file = os.path.join("${TASK_PATH}", "config.yml")
        for i in range(models):
            task_name = f"{config_name}-{i}"
            train_task = generate_mead_task(
                mead_template,
                task_name,
                config_file,
                images['mead'],
                claims['data'],
                datasets=datasets,
                embeddings=embeddings,
                data_files=data_files,
                gpus=gpus,
                addons=addons[config_name],
                depends=dep,
                pull_policy=pull_policy,
            )
            all_tasks.append(train_task)
            trained_models.append(train_task['name'])
            if mead_eval_dataset:
                name = f"{task_name}-eval"
                eval_task = generate_eval_task(
                    template=mead_eval_template,
                    task_name=name,
                    image=images['odin'],
                    claim=claims['data'],
                    eval_task=task_name,
                    eval_dataset=mead_eval_dataset,
                    config=config,
                    depends=task_name,
                    addons=addons[config_name],
                    pull_policy=pull_policy,
                )
                all_tasks.append(eval_task)
                evals.append(eval_task['name'])

    prev_tasks = list(chain(trained_models, evals))
    export_task = generate_export_task(
        export_template,
        images['odin'],
        claims['data'],
        trained_models,
        task,
        dataset,
        depends=prev_tasks,
        metric=metric,
        export_policy=export_policy,
        pull_policy=pull_policy,
        models_claim=claims['models'] if export_to_dev else None,
    )
    chore_depends = prev_tasks
    if export_task:
        all_tasks.append(export_task)
        chore_depends = 'export'
    chores = generate_chore_yaml(template_loc, slack, slack_web_hook, git_commit, selected=export_task)
    if chores:
        chore_task = generate_chore_task(
            chore_template, images['odin'], claims['data'], depends=chore_depends, pull_policy=pull_policy
        )
        all_tasks.append(chore_task)
        chore_file = os.path.join(pipeline_loc, 'chores.yml')
        write_yaml({'chores': chores}, chore_file)
        set_permissions(chore_file)

    pipeline['tasks'] = all_tasks
    main_file = os.path.join(pipeline_loc, 'main.yml')
    write_yaml(pipeline, main_file)
    set_permissions(main_file)

    return os.path.join(uname, pipeline_name)


def get_images(
    template_loc: Path,
    mead: Optional[str] = None,
    odin: Optional[str] = None,
    claim: Optional[str] = None,
    models: Optional[str] = None,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Get image names with a fallback to the images file."""
    defaults = read_config_file(os.path.join(template_loc, 'images.yml'))
    mead = mead if mead is not None else defaults['mead-image']
    odin = odin if odin is not None else defaults['odin-image']
    claim = claim if claim is not None else defaults['claim-name']
    models = models if models is not None else defaults['models-claim']
    images = {'mead': mead, 'odin': odin, 'template': defaults['template-image'], 'hpctl': defaults['hpctl-image']}
    claims = {'data': claim, 'models': models}
    return images, claims


def guess_export_loc(
    config: Dict, output_dir: Optional[str] = None, project: Optional[str] = None, name: Optional[str] = None
) -> Dict:
    """Try to fill in missing export information."""
    export = config.get('export', {})
    if output_dir is not None:
        export['output_dir'] = output_dir
    if project is not None:
        export['project'] = project
    if name is not None:
        export['name'] = name

    required = {'output_dir', 'project', 'name'}
    if all(r in export for r in required):
        return export

    if 'output_dir' not in export:
        export['output_dir'] = '/data/nest/models'

    dataset = config['dataset']
    parts = dataset.split(":")
    if len(parts) == 1 and any(r not in export for r in required):
        LOGGER.warning(
            "Cannot guess the export location of this config."
            " Please fill in the export section of the config, "
            "switch to the new dataset format (project:name:features:date), "
            "or use the --output-dir, --project, and --name cli flags."
        )
        return {}
    if 'project' not in export:
        export['project'] = parts[0]
    if 'name' not in export:
        export['name'] = parts[1]
    print(
        f"Planning to export to `{export['output_dir']}` in the"
        f" `{export['project']}` project under the `{export['name']}` name"
    )
    resp = input("Is this ok (y/n) ")
    if resp.lower() == "n":
        LOGGER.warning(
            "Guessed locations were unsatisfactory, please fill in the export "
            "section of the config or use the --output-dir, --project, and --name cli flags."
        )
        return {}
    return export


def preprocess_arguments(args: argparse.Namespace) -> Dict:  # pylint: disable=too-many-branches
    """Update the cli args be doing things like reading in the files they point to and things like that.

    :params args: The command line args.
    :returns: The command line args with values updated.
    """
    if args.pipeline_name is None:
        args.pipeline_name, _ = os.path.splitext(os.path.basename(args.configs[0]))
    configs = {os.path.splitext(os.path.basename(config))[0]: read_config_file(config) for config in args.configs}
    for config in configs.values():
        if args.task is None and 'task' not in config:
            LOGGER.warning("No task specified, defaulting to `classify`")
            config['task'] = 'classify'
    # If there is requested export type make sure the export section is filled in in the config.
    if args.export_policy is not None:
        export = guess_export_loc(list(configs.values())[0], args.output_dir, args.project, args.name)
        if export:
            for config in configs.values():
                config['export'] = export
        else:
            exit(1)
    if args.embeddings is not None:
        if os.path.exists(args.embeddings):
            args.embeddings = read_config_file(args.embeddings)
    if args.datasets is not None:
        if os.path.exists(args.datasets):
            args.datasets = read_config_file(args.datasets)
    # If train, valid, or tests files are provided use them to populate the datasets.
    if args.train_file is not None or args.valid_file is not None or args.test_file is not None:
        # If we are not overwriting entries in a dataset index and we don't have enough datasets listed
        if args.datasets is None and (args.train_file is None or args.valid_file is None):
            LOGGER.warning("Both a train file and a valid file are required.")
            exit(1)
        args.datasets = args.datasets if args.datasets is not None else [{}]
        dataset_label = find_const_config_prop('dataset', configs.values())
        index, dataset = next(((i, d) for i, d in enumerate(args.datasets) if d.get('label') == dataset_label), (0, {}))
        # This populate this if we are build from starch, will be the same otherwise
        dataset['label'] = dataset_label
        dataset['train_file'] = args.train_file if args.train_file is not None else dataset.get('train_file')
        dataset['valid_file'] = args.valid_file if args.valid_file is not None else dataset.get('valid_file')
        dataset['test_file'] = args.test_file if args.test_file is not None else dataset.get('test_file')
        args.datasets[index] = dataset
    dataset = find_const_config_prop('dataset', configs.values())
    if args.datasets is None and ":" not in dataset:
        LOGGER.warning(
            "You did not provide a custom dataset file and the dataset (%s) appears to be an old style dataset."
            " This means the server will most likely not be able to find this dataset.",
            dataset,
        )
    config = list(configs.values())[0]  # Hack
    config_gpus = config['train'].get('gpus', config['model'].get('gpus', config.get('gpus', None)))
    config_gpus = int(config_gpus) if config_gpus is not None else config_gpus
    # If they don't pass gpu via cli set it to match the config with a default of 1
    args.gpus = (config_gpus if config_gpus is not None else 1) if args.gpus is None else args.gpus
    if config_gpus is not None and args.gpus != config_gpus:
        LOGGER.warning(
            "The number of gpus requested via cli [%d] is not equal to number requested in the config file [%d]",
            args.gpus,
            config_gpus,
        )
        exit(1)
    addons = {}
    for config_name, config in configs.items():
        config['modules'] = list(set(chain(config.get('modules', []), args.modules)))
        addons[config_name] = {
            os.path.basename(mod.__file__): inspect.getsource(mod)
            for mod in (import_user_module(m) for m in config['modules'])
        }
    if args.template is not None and os.path.isfile(args.template):
        args.template = read_config_file(args.template)

    config = {
        'uname': args.user,
        'pipeline_name': args.pipeline_name,
        'configs': configs,
        'datasets': args.datasets,
        'embeddings': args.embeddings,
        'models': args.models,
        'gpus': args.gpus,
        'metric': args.metric,
        'export_policy': args.export_policy,
        'slack': args.slack,
        'slack_web_hook': args.slack_web_hook,
        'git_commit': False,
        'mead_image': args.mead_image,
        'odin_image': args.odin_image,
        'claim_name': args.claim_name,
        'pull_policy': args.pull_policy,
        'clobber': args.clobber,
        'addons': addons,
        'mead_eval_dataset': args.mead_eval_dataset,
        'models_claim': args.models_claim,
        'export_to_dev': args.export_to_dev,
        'template': args.template,
        'hpctl': args.hpctl,
        'seed': args.seed,
    }
    return config


def main():
    """Generate a pipeline locally."""
    parser = argparse.ArgumentParser()
    parser.add_argument("configs", help="The path to the mead config we want to turn into a pipeline.", nargs="+")
    parser.add_argument(
        "--root-path", "--root_path", default="/data/pipelines", help="The location of the pipelines repo."
    )
    parser.add_argument("--user", default=getpass.getuser(), help="The prefix of your pipeline name.")
    parser.add_argument(
        "--pipeline-name", "--pipeline_name", help="The name of your pipeline. Defaults to the name of the mead config."
    )
    parser.add_argument("--datasets", help="The location of your custom datasets index file.")
    parser.add_argument("--embeddings", help="The location of you custom embeddings file.")
    parser.add_argument("--train-file", "--train_file", help="The location of a custom train file")
    parser.add_argument("--valid-file", "--valid_file", help="The location of a custom valid file")
    parser.add_argument("--test-file", "--test_file", help="The location of a custom test file")
    parser.add_argument("--task", help="The baseline task for this model")
    parser.add_argument(
        "--models",
        type=int,
        default=1,
        help="The number of times to train the model" " (or the number of models to train when using hpctl).",
    )
    parser.add_argument("--gpus", type=int, help="The number of GPUs to give to each model training task.")
    parser.add_argument("--metric", default="acc", help="The name of the metric used to compare the results of models.")
    parser.add_argument(
        "--export-policy",
        "--export_policy",
        "--export-type",
        default=None,
        help="The type of decision to use when deciding if a model should be exported.",
    )
    parser.add_argument(
        "--slack",
        type=str2bool,
        default=True,
        help="Should we send a slack message when the pipeline has finished running?",
    )
    parser.add_argument(
        "--slack-web-hook", "--slack_web_hook", default=None, help="The endpoint for slack messages to go to"
    )
    # parser.add_argument("--git-commit", type=str2bool, default=False,
    #                     help="Should we commit the exported model with git?")
    parser.add_argument("--mead-image", "--mead_image", help="The name of the image to use for mead training.")
    parser.add_argument(
        "--odin-image", "--odin_image", help="The name of the image to use for odin exporting and odin chores."
    )
    parser.add_argument("--claim-name", "--claim_name", help="The name of the k8s pvc claim.")
    parser.add_argument('--models-claim', "--models_claim", help="/models pvc name")
    parser.add_argument(
        "--pull-policy",
        "--pull_policy",
        help="The pull policy to use for containers",
        choices={IF_NOT_PRESENT, ALWAYS, NEVER},
        default=ALWAYS,
    )
    parser.add_argument("--clobber", type=str2bool, default=True, help="Should we overwrite a previous pipeline?")
    parser.add_argument("--output-dir", "--output_dir", help="The base dir for where a model should be exported.")
    parser.add_argument("--project", help="The name of the project this model is for.")
    parser.add_argument("--name", help="The name of the model, i.e. intent, sf, etc.")
    parser.add_argument('--modules', help='modules to load', default=[], nargs='+', required=False)
    parser.add_argument('--mead-eval-dataset', "--mead_eval_dataset", help="The dataset to use for mead-eval")
    parser.add_argument(
        '--export-to-dev', "--export_to_dev", action='store_true', help="Should exported models be copied to raven-dev"
    )
    parser.add_argument('--template', help='An odin-template sample file.')
    parser.add_argument('--hpctl', help='Should hpctl be used in the pipeline to sample configs', action="store_true")
    parser.add_argument('--seed', help='A seed for controlling hpctl', type=int)
    args = parser.parse_args()

    config = preprocess_arguments(args)
    config['root_path'] = args.root_path

    name = generate_pipeline(**config)
    print(f"Pipeline created at {os.path.join(args.root_path, name)}")


if __name__ == "__main__":
    main()
