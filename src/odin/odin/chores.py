"""DSL to execute common chores
"""
import argparse
import logging
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Callable, NewType, Optional
import git

from baseline.utils import exporter, optional_params, read_config_stream, import_user_module
from odin.core import create_graph, _to_kwargs, wire_inputs, format_output
from odin.dag import topo_sort, find_children, dot_graph
from odin.store import MongoStore

__all__ = []
export = exporter(__all__)
CHORE_REGISTRY = {}
Chore = NewType('Chore', Callable)

DEPENDENCY_KEY = 'depends'
LOGGER = logging.getLogger('odin')


def set_repo_creds(
    repo: git.Repo,
    name: Optional[str] = None,
    email: Optional[str] = None,
    name_env: str = "ODIN_GIT_NAME",
    email_env: str = "ODIN_GIT_EMAIL"
) -> git.Repo:
    """Set the name and email on the git repo so you can commit.

    :param repo: The repo object
    :param name: The name to set
    :param email: The email to set
    :param name_env: The env variable to read the name from if no name provided
    :param email_env: The env variable to read the email from if no email is provided

    :returns: The repo with the creds set
    """
    name = os.environ[name_env] if name is None else name
    email = os.environ[email_env] if email is None else email
    repo.config_writer().set_value("user", "name", name).release()
    repo.config_writer().set_value("user", "email", email).release()
    return repo


class ChoreSkippedException(Exception):
    """A special exception chores use to signal they want to quit."""


@contextmanager
def change_dir(path: str):  # pylint: disable=missing-yield-doc,missing-yield-type-doc
    """Change the current directory

    :param path: Change to what
    """
    current_dir = os.getcwd()
    try:
        os.chdir(os.path.expanduser(path))
        yield
    finally:
        os.chdir(current_dir)


@export
@optional_params
def register_chore(chore: Chore, name: str = None) -> Chore:
    """Register a chore (some callable) to a name
    :param chore: Some callable
    :param name: A unique name for this registry
    :raises Exception: If the name is already registered.
    :return: The callable
    """
    name = name if name is not None else chore.__name__
    if name in CHORE_REGISTRY:
        raise Exception(
            'Error: attempt to re-define previously'
            f' registered Chore {name} (old: {CHORE_REGISTRY[name]}, new: {chore}) in registry'
        )
    CHORE_REGISTRY[name] = chore
    return chore


@export
def create_chore(name: str) -> Chore:
    """Factory method to give back a chore requested by name

    :param name: Name of the chore
    :return: The (callable) Chore
    """
    return CHORE_REGISTRY[name]


@export
@register_chore('copy')
def copy(src: str, dst: str, clobber: bool = True) -> str:
    """Copy file from source to destination

    :param src: source path
    :param dst: destination path
    :param clobber: Should we overwrite (defaults to `True`)
    :raises ChoreSkippedException: If there is missing inputs.
    :return: The destination path
    """
    if src is None or dst is None:
        raise ChoreSkippedException()
    src = os.path.abspath(os.path.expanduser(src))
    dst = os.path.abspath(os.path.expanduser(dst))

    if os.path.isfile(src):
        # If dst is a directory that exists then we make a file in it
        # Not sure if we want this yet, only use cause rn is for dirs
        if os.path.exists(dst) and os.path.isdir(dst):
            dst = os.path.join(dst, os.path.basename(src))
        shutil.copy2(src, dst)
    else:
        dst = os.path.join(dst, os.path.basename(src))
        if clobber and os.path.exists(dst):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            else:
                os.remove(dst)
        shutil.copytree(src, dst)
    return dst


@export
@register_chore('git-add')
def git_add(dir: Path, files: List[str] = None) -> bool:
    """Add a directory to git with an optional list of files

    :param dir: A directory
    :param files: Files (defaults to `None`)
    :raises ChoreSkippedException: If there is missing inputs.
    :return: `True`
    """
    from git import Repo  # pylint: disable=import-outside-toplevel

    if files is None or any(f is None for f in files):
        raise ChoreSkippedException()
    if dir is not None:
        repo = Repo(dir)
    else:
        repo = Repo(files[0], search_parent_directories=True)
    repo = set_repo_creds(repo)
    for filename in files:
        repo.git.add(os.path.expanduser(filename))
    return True


@export
@register_chore('git-commit')
def git_commit(dir: Path, message: str) -> bool:
    """Commit a directory to git

    :param dir: The directory
    :param message: The git message
    :raises ChoreSkippedException: If there is missing inputs.
    :return: `True`
    """
    from git import Repo  # pylint: disable=import-outside-toplevel

    if dir is None or message is None:
        raise ChoreSkippedException()
    repo = Repo(dir)
    repo = set_repo_creds(repo)
    # Check that files have been staged for commit
    if not repo.index.diff("HEAD"):
        raise ChoreSkippedException()
    repo.git.commit(m=message)
    return True


def _repo_version_match(repo: git.Repo) -> bool:
    master = str(git.repo.fun.rev_parse(repo, 'origin/master'))
    head = str(git.repo.fun.rev_parse(repo, 'HEAD'))
    return master == head


def _stash_pull_pop(repo: git.Repo) -> None:
    do_stash = False
    if repo.is_dirty():
        do_stash = True
        repo.git.stash()
    if not _repo_version_match(repo):
        repo.git.pull('--rebase', 'origin', 'master')
    if do_stash:
        repo.git.stash('pop')


@export
@register_chore('git-push')
def git_push(dir: Path) -> bool:
    """Push a directory to git

    :param dir: Directory
    :raises ChoreSkippedException: If there is missing inputs.
    :return: `True`
    """
    from git import Repo  # pylint: disable=import-outside-toplevel

    if dir is None:
        raise ChoreSkippedException()
    repo = Repo(dir)
    repo = set_repo_creds(repo)
    _stash_pull_pop(repo)
    repo.git.push()
    return True


@export
@register_chore('git-pull')
def git_pull(dir: Path) -> bool:
    """Pull a git repo.

    :param dir: The directory where the git repo lives
    :raises ChoreSkippedException: If there is missing inputs.
    :returns: True
    """
    from git import Repo  # pylint: disable=import-outside-toplevel

    if dir is None:
        raise ChoreSkippedException()
    repo = Repo(dir)
    repo = set_repo_creds(repo)
    repo.git.pull()
    return True


@export
@register_chore('bump-version')
def bump_version(file_name: Path) -> str:
    """Bump the version with the ruamel round trip loader to preserve formatting."""
    import ruamel.yaml  # pylint: disable=import-outside-toplevel

    if file_name is None:
        raise ChoreSkippedException()
    with open(file_name) as rf:
        config = ruamel.yaml.load(rf, Loader=ruamel.yaml.RoundTripLoader)
    metadata = config.setdefault('metadata', {})
    labels = metadata.setdefault('labels', {})
    labels['version'] = str(int(labels.get('version', 0)) + 1)
    with open(file_name, 'w') as out:
        ruamel.yaml.dump(config, out, Dumper=ruamel.yaml.RoundTripDumper)
    return file_name


@export
@register_chore('bump-k8s')
def bump_k8s(base_dir: Path, deployment: str, client: str) -> List[str]:
    """Bump the version in the deployment and service yaml.

    :param base_dir: `str` The root path of all the orchestration files.
    :param deployment: `str` which deployment to bump, research, local, etc
    :param client: `str` which client to bump.
    :raises ChoreSkippedException: If there is missing inputs.

    :returns: List[str] A list of all files updated
    """
    if base_dir is None or deployment is None or client is None:
        raise ChoreSkippedException()
    types = ('deployments', 'services')
    return [bump_version(os.path.join(base_dir, deployment, kind, f"{client}.yml")) for kind in types]


@export
@register_chore('slack-message')
def slack_webhook(parent_details: Dict, webhook: str, template: str) -> None:
    """Substitute a template message and post to slack

    :param parent_details: The context to use to replace values in the template.
    :param webhook: The webhook key
    :param template: The message.
    """
    import requests  # pylint: disable=import-outside-toplevel
    from string import Template  # pylint: disable=import-outside-toplevel

    message: str = Template(template).substitute(parent_details)
    requests.post(webhook, json={"text": message})


def run_chores(config: Dict, results: Dict) -> Dict:
    """Execute a chore graph

    :param config: The list of chores and there deps
    :param results: A set of upstream results that can be used
    :return: The new results, updated with chore output
    """
    graph = create_graph(config['chores'], results)

    # Convert the graph from indices to names so it prints better.
    named_graph = {config['chores'][k]['name']: [config['chores'][v]['name'] for v in vs] for k, vs in graph.items()}
    LOGGER.info(dot_graph(named_graph))

    execution_order = topo_sort(graph)
    # Track nodes that give up and all the nodes that are downstream of them.
    to_skip = set()
    children = find_children(graph)
    LOGGER.info("Topological Sort %s", execution_order)
    for step in execution_order:
        params = config['chores'][step]
        name = params.pop('name')
        if step in to_skip:
            # If an ancestor of yours gave up you should give up.
            LOGGER.debug("Chore %s skipped because of parent", name)
            continue
        chore_type = params.pop('type')
        params.pop(DEPENDENCY_KEY, None)
        LOGGER.debug('Feeding Inputs: %s(%s)', name, _to_kwargs(params))
        LOGGER.debug(results)
        chore = create_chore(chore_type)
        params = wire_inputs(params, results, chore)
        LOGGER.info('Running: %s(%s)', name, _to_kwargs(params))
        try:
            res = chore(**params)
        except ChoreSkippedException:
            # I decided to give up. All my descendants should give up.
            res = None
            LOGGER.debug("Chore %s raised a ChoreSkippedException", name)
            to_skip.add(step)
            to_skip.update(children[step])
        results[name] = format_output(res)
    LOGGER.info("Chores %s skipped running.", to_skip)
    return results


def main():
    """Driver program to execute chores."""
    parser = argparse.ArgumentParser(description='Run chores')
    parser.add_argument('file', help='A chore YAML file.')
    parser.add_argument('--cred', help='cred file', default="/etc/odind/odin-cred.yml")
    parser.add_argument('--label', required=True)
    parser.add_argument('--modules', nargs='+', default=[], help='Addon modules to load')
    args = parser.parse_args()

    for addon in args.modules:
        import_user_module(addon)

    cred_params = read_config_stream(args.cred)
    store = MongoStore(**cred_params['jobs_db'])
    config = read_config_stream(args.file)
    previous = store.get_previous(args.label)
    parent_details = store.get_parent(args.label)
    results = {prev_job_details['name']: prev_job_details for prev_job_details in previous}
    results['parent'] = parent_details
    results = run_chores(config, results)
    results = {'chore_context': results}
    LOGGER.info(results)
    job_details = store.get(args.label)
    job_details.update(results)
    store.set(job_details)


if __name__ == "__main__":
    main()
