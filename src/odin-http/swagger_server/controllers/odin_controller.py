import datetime
import connexion
import glob
import flask
import git
from kubernetes import client, config
from typing import List, Optional
import requests
from werkzeug.exceptions import Unauthorized

from swagger_server.models.error import Error  # noqa: E501
from swagger_server.models.auth_definition import AuthDefinition
from swagger_server.models.auth_response_definition import AuthResponseDefinition
from swagger_server.models.config_definition import ConfigDefinition  # noqa: E501
from swagger_server.models.event_definition import EventDefinition  # noqa: E501
from swagger_server.models.event_results import EventResults
from swagger_server.models.job_definition import JobDefinition  # noqa: E501
from swagger_server.models.job_wrapper_definition import JobWrapperDefinition
from swagger_server.models.job_results import JobResults
from swagger_server.models.pipeline_definition import PipelineDefinition  # noqa: E501
from swagger_server.models.pipeline_wrapper_definition import PipelineWrapperDefinition
from swagger_server.models.pipeline_results import PipelineResults
from swagger_server.models.task_status_definition import TaskStatusDefinition
from swagger_server.models.task_definition import TaskDefinition
from swagger_server.models.pipeline_cleanup_definition import PipelineCleanupDefinition  # noqa: E501
from swagger_server.models.pipeline_cleanup_results import PipelineCleanupResults
from swagger_server.models.upload_definition import UploadDefinition  # noqa: E501
from swagger_server.models.user_definition import UserDefinition
from swagger_server.models.user_wrapper_definition import UserWrapperDefinition
from swagger_server.models.user_results import UserResults

import re
from swagger_server import util
from baseline.utils import read_yaml, write_json
import os
import websockets
import json
import logging
import asyncio
import yaml
import time
from jose import jwt
from swagger_server.models.orm import User

# This indicates what branch we should be looking at in git for its pipelines
PIPELINES_MAIN = os.environ.get('ODIN_PIPELINES_MAIN', 'master')
JWT_ISSUER = os.environ.get('ODIN_AUTH_ISSUER', 'com.interactions')
JWT_SECRET = os.environ.get('ODIN_SECRET')
JWT_LIFETIME_SECONDS = os.environ.get('ODIN_TOKEN_DURATION', 60 * 60 * 12)
JWT_ALGORITHM = os.environ.get('ODIN_AUTH_ALG', 'HS256')
MIDGARD_PORT = os.environ.get('MIDGARD_PORT', 29999)
MIDGARD_API_VERSION = os.environ.get('MIDGARD_API_VERSION', 'v1')
LOGGER = logging.getLogger('odin-http')

def _convert_to_path(resource_id: str) -> str:
    """Convert something like dpressel__ag-news into dpressel/ag-news
    :param resource_id:
    :return:
    """
    return resource_id.replace('__', '/')


class JwtFailedUnauthorized(Unauthorized):
    description = 'JWT authentication failed.  Most likely your token is expired'
    def get_headers(self, environ):
        """Get a list of headers."""
        return [('Content-Type', 'text/html'),
                ('WWW-Authenticate', 'Basic realm="Login required"')]


def check_odinAuth(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception as _:
        raise JwtFailedUnauthorized()

def _get_dao():
    return flask.globals.current_app.dao


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


def generate_token(body):  # noqa: E501
    """Return JWT token

     # noqa: E501

    :param body: An Auth definition
    :type body: dict | bytes

    :rtype: AuthResponseDefinition
    """
    body = AuthDefinition.from_dict(connexion.request.get_json())  # noqa: E501
    user: User = _get_dao().get_user(body.username)
    if not user:
        raise Exception("Bad username!")
    if not user.authenticate(body.password):
        raise Exception("Bad password!")

    timestamp = time.time()
    payload = {
        "iss": JWT_ISSUER,
        "iat": int(timestamp),
        "exp": int(timestamp + JWT_LIFETIME_SECONDS),
        "sub": str(user.username),
    }
    message = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return AuthResponseDefinition(message=message)


def _get_job_repo_sha() -> str:
    repo = git.Repo(flask.globals.current_app.root_path)
    repo = set_repo_creds(repo)
    sha = repo.head.object.hexsha
    return sha


def _repo_version_match(repos: git.Repo) -> bool:
    master_version = str(git.repo.fun.rev_parse(repos, f'origin/{PIPELINES_MAIN}'))
    head_version = str(git.repo.fun.rev_parse(repos, 'HEAD'))
    return master_version == head_version


def _stash_pull_pop(repo: git.Repo):
    do_push_pop = False
    if repo.is_dirty():
        do_push_pop = True
        repo.git.stash()

    if not _repo_version_match(repo):
        repo.git.pull('--rebase', 'origin', f'{PIPELINES_MAIN}')

    if do_push_pop:
        repo.git.stash('pop')


def _update_job_repo() -> None:
    repo = git.Repo(flask.globals.current_app.root_path)
    repo = set_repo_creds(repo)
    _stash_pull_pop(repo)


def _add_to_job_repo(filename: str, message: str = None) -> str:
    """Push a directory to git

    :param dir: Directory
    :raises ChoreSkippedException: If there is missing inputs.
    :return: `True`
    """

    repo = git.Repo(flask.globals.current_app.root_path)
    repo = set_repo_creds(repo)
    _stash_pull_pop(repo)
    repo.git.add([filename])
    if repo.is_dirty():
        repo.git.commit(m=message)
        repo.git.push()
    sha = repo.head.object.hexsha
    return sha


def _get_job_loc(id_):
    return os.path.join(flask.globals.current_app.root_path, id_)


def _get_job_file(id_, filename):
    return os.path.join(_get_job_loc(id_), filename)


class APIField:
    """Keys that we use when communicating between server and clients."""

    STATUS = 'status'
    RESPONSE = 'response'
    COMMAND = 'command'
    REQUEST = 'request'


class APIStatus:
    """Status codes used between the server and client."""

    OK = 'OK'
    ERROR = 'ERROR'
    END = 'END'


def _read_file(file_to_read):
    if not os.path.exists(file_to_read) or not os.path.isfile(file_to_read):
        raise Exception("Invalid filename: {}".format(file_to_read))
    with open(file_to_read, 'r') as rf:
        return rf.read()


def _to_user_def(user: User) -> UserDefinition:
    return UserDefinition(username=user.username, firstname=user.firstname, lastname=user.lastname)


def create_user(body):  # noqa: E501
    """Create a user

     # noqa: E501

    :param body: A user definition
    :type body: dict | bytes

    :rtype: UserWrapperDefinition
    """
    body = UserWrapperDefinition.from_dict(connexion.request.get_json())  # noqa: E501
    user = _get_dao().create_user(body.user)
    return UserWrapperDefinition(_to_user_def(user))


def update_user(body, id_):  # noqa: E501
    """Update a User

     # noqa: E501

    :param body: A User definition
    :type body: dict | bytes
    :param id_: Username
    :type id_: str

    :rtype: UserDefinition
    """
    body = UserDefinition.from_dict(connexion.request.get_json())  # noqa: E501
    if not body.username:
        body.username = id_
    user = _get_dao().update_user(body)
    return UserWrapperDefinition(_to_user_def(user))


def delete_user(id_):  # noqa: E501
    """Delete a user

     # noqa: E501

    :param id_: User ID
    :type id_: str

    :rtype: UserWrapperDefinition
    """
    user = _get_dao().delete_user(id_)
    return UserWrapperDefinition(_to_user_def(user))


def get_user(id_):  # noqa: E501
    """Get a user

     # noqa: E501

    :param id: ID of a user
    :type id: str

    :rtype: UserWrapperDefinition
    """
    user = _get_dao().get_user(id_)
    return UserWrapperDefinition(_to_user_def(user))


def get_ready(q=None):
    return "PONG"


def get_users(q=None):  # noqa: E501
    """Get user info

     # noqa: E501

    :param q: Get users
    :type q: str

    :rtype: UserResults
    """
    users = _get_dao().get_users(q)
    return UserResults(users=[_to_user_def(u) for u in users])


def download_job_file(id_, filename):  # noqa: E501
    """Get a file required for a Job

    Get a file from the server that is used for a Job  # noqa: E501

    :param id_: job ID
    :type id_: str
    :param filename: A basename to use on the server
    :type filename: str

    :rtype: str
    """
    id_ = _convert_to_path(id_)
    _update_job_repo()
    return _read_file(_get_job_file(id_, filename))


def _validate_filename(filename):
    matcher = re.compile(r'^[^<>:;,?"*|/]+$')
    if not matcher.match(filename):
        raise Exception("Invalid file name: {}".format())


def upload_job_file(id_, filename, body=None):  # noqa: E501
    """Upload a file required for a Job

    Uploads a file needed for a Job step.
    Puts the file to the Job location.
    If the file already exists, it will be overwritten    # noqa: E501

    :param id_: Job ID
    :type id_: str
    :param filename: A basename to use on the server
    :type filename: str
    :param body: A config file
    :type body: dict | bytes

    :rtype: UploadDefinition
    """
    id_ = _convert_to_path(id_)
    _validate_filename(filename)
    file_to_write = _get_job_file(id_, filename)

    if connexion.request.is_json:
        body = Object.from_dict(connexion.request.get_json())  # noqa: E501
        write_json(body, file_to_write)

    else:
        body = connexion.request.get_data()
        if os.path.exists(file_to_write):
            logging.warning("Found {}.  Overwriting".format(body))
        with open(file_to_write, 'wb') as wf:
            wf.write(body)

    sha = _add_to_job_repo(file_to_write, "via odin-http upload_job_file")
    ud = UploadDefinition()
    ud.location = f'{file_to_write}@{sha}'
    ud.bytes = os.stat(file_to_write).st_size
    return ud


def get_node_info(q=None):  # noqa: E501
    """Get info for all gpus

     # noqa: E501

    :param q: Get GPU devices by partial name match
    :type q: str

    :rtype: str
    """
    def get_nodes() -> List[str]:
        """Get back all the nodes in the cluster

        :return: The nodes
        """
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            config.load_kube_config()

        core_api = client.CoreV1Api()
        return core_api.list_node().items
    results = []
    for node in get_nodes():
        addresses = node.status.addresses
        internal_address = [a.address for a in addresses if a.type == 'InternalIP'][0]
        host = [a.address for a in addresses if a.type == 'Hostname'][0]
        capacity_dict = node.status.capacity
        midgard_url = f'http://{internal_address}:{MIDGARD_PORT}/{MIDGARD_API_VERSION}/gpus'
        gpu_infos = requests.get(midgard_url).json()['gpus']
        capacity_dict['gpus'] = gpu_infos
        capacity_dict['host'] = host
        capacity_dict['internalIP'] = internal_address
        results.append(capacity_dict)

    return {'nodes': results}


def cleanup_pipeline(id_, db=None, fs=None):  # noqa: E501
    """Delete a Pipeline

    # noqa: E501

    :param id: ID of Pipeline
    :type id: int

    :rtype: PipelineCleanupResults (FIXME!)
    """

    async def _request_cleanup(ws: str, work: str, purge_db: bool = False, purge_fs: bool = False):
        """Request the work is cleaned up by the server."""
        async with websockets.connect(ws) as websocket:
            args = {'work': work, 'purge_db': purge_db, 'purge_fs': purge_fs}
            await websocket.send(json.dumps({APIField.COMMAND: 'CLEANUP', APIField.REQUEST: args}))

            results = json.loads(await websocket.recv())
            if results[APIField.STATUS] == APIStatus.ERROR:
                LOGGER.error(results)
                return []
            if results[APIField.STATUS] == APIStatus.OK:
                cleaned = results[APIField.RESPONSE]
                cleanup_def = [PipelineCleanupDefinition(**c) for c in cleaned]
                return PipelineCleanupResults(cleanup_def)

    ws = flask.globals.current_app.ws_url
    loop = flask.globals.current_app.ws_event_loop
    asyncio.set_event_loop(loop)
    cleanup_info = asyncio.get_event_loop().run_until_complete(_request_cleanup(ws, id_, db, fs))
    return cleanup_info


def create_pipeline(body):  # noqa: E501
    """Run a pipeline

     # noqa: E501

    :param body: A Pipeline definition (really just the name)
    :type body: dict | bytes

    :rtype: PipelineDefinition
    """

    async def _submit_job(ws, work) -> None:
        _pipe_id = None
        async with websockets.connect(ws) as websocket:
            await websocket.send(json.dumps({APIField.COMMAND: 'START', APIField.REQUEST: work}))
            result = json.loads(await websocket.recv())
            if result[APIField.STATUS] == APIStatus.ERROR:
                LOGGER.error(result)
                raise Exception("Invalid response")

            _pipe_id = result[APIField.RESPONSE]
            return _pipe_id

    if connexion.request.is_json:
        body = PipelineWrapperDefinition.from_dict(connexion.request.get_json())  # noqa: E501
        job = _convert_to_path(body.pipeline.job)

        _update_job_repo()
        ws = flask.globals.current_app.ws_url
        loop = flask.globals.current_app.ws_event_loop
        asyncio.set_event_loop(loop)
        pipe_id = asyncio.get_event_loop().run_until_complete(_submit_job(ws, job))
        p = PipelineDefinition()
        p.name = pipe_id
        p.id = pipe_id
        p.job = job
        return PipelineWrapperDefinition(p)
    return None


def create_job(body):  # noqa: E501
    """Create a job definition

     # noqa: E501

    :param body: A Job definition
    :type body: dict | bytes

    :rtype: JobWrapperDefinition
    """
    if connexion.request.is_json:
        body = JobWrapperDefinition.from_dict(connexion.request.get_json())  # noqa: E501
        id_ = _convert_to_path(body.job.name)
        new_job_path = _get_job_loc(id_)
        if os.path.exists(new_job_path):
            raise Exception(f"There is already a job at {id}")
        os.makedirs(new_job_path)
        file_to_write = _get_job_file(id_, 'main.yml')
        task_obj = {'tasks': []}
        with open(file_to_write, 'w') as wf:
            yaml.dump(task_obj, wf)
        sha = _add_to_job_repo(file_to_write, "via odin-http create_job")
        LOGGER.info(f'Updated git {sha}')

        return JobDefinition(id=id_,
                             name=id_,
                             location=new_job_path,
                             creation_time=datetime.datetime.now())


def _to_dict(jid, task):
    """User can put in whatever task name they want, but we will rewrite it"""
    task = task.to_dict()
    task_name = task.get('name')
    task['id'] = f'{jid}--{task_name}'
    return task


def update_job(body, id_):  # noqa: E501
    """Update a JobWrapperDefinition

     # noqa: E501

    :param body: A JobWrapperDefinition
    :type body: dict | bytes
    :param id_: job ID
    :type id_: int

    :rtype: JobWrapperDefinition
    """
    id_ = _convert_to_path(id_)
    if connexion.request.is_json:
        body = JobDefinition.from_dict(connexion.request.get_json()['job'])  # noqa: E501
        tasks = [_to_dict(id_, s) for s in body.tasks]
        # compute the id of the tasks if needed

        task_obj = {'tasks': tasks}
        configs = body.configs
        for config in configs:
            file_to_write = _get_job_file(id_, config.name)
            with open(file_to_write, 'w') as wf:
                wf.write(config.content)
            _add_to_job_repo(file_to_write, 'via odin-http create_job')

        job_loc = _get_job_loc(id_)
        if os.path.exists(job_loc) is False:
            logging.info('Creating job location {}'.format(job_loc))
            os.makedirs(job_loc)

        file_to_write = _get_job_file(id_, 'main.yml')
        with open(file_to_write, 'w') as wf:
            yaml.dump(task_obj, wf)
        sha = _add_to_job_repo(file_to_write, "via odin-http create_job")
        LOGGER.info(f'Updated git {sha}')
        body.tasks = tasks

    return JobWrapperDefinition(body)


def get_resource_data(id_):  # noqa: E501
    """Get resource data

    Get resource data  # noqa: E501

    :param id_: resource ID
    :type id_: str

    :rtype: str
    """
    async def _request_data(ws: str, resource: str, namespace: str = 'default') -> None:
        """Get data for resource as contained in `jobs_db`

        :param uri: The location of the server
        :param pod: The name of the resource you are asking about.
        :param namespace: The namespace of the resource you are asking about.
        :param kind: The kind of resource you are asking about.
        """
        async with websockets.connect(ws) as websocket:
            await websocket.send(
                json.dumps(
                    {
                        APIField.COMMAND: 'DATA',
                        APIField.REQUEST: {'resource': resource, 'namespace': namespace},
                    }
                )
            )
            resp = json.loads(await websocket.recv())
            if resp[APIField.STATUS] == APIStatus.ERROR:
                LOGGER.error(resp)
                return
            if resp[APIField.STATUS] == APIStatus.OK:
                return resp[APIField.RESPONSE]
    ws = flask.globals.current_app.ws_url
    loop = flask.globals.current_app.ws_event_loop
    asyncio.set_event_loop(loop)
    return asyncio.get_event_loop().run_until_complete(_request_data(ws, id_))


def get_events(id_):  # noqa: E501
    """Get events associated with some resource or sub-resource

     # noqa: E501

    :param id_: Get events for ID
    :type id_: str

    :rtype: EventResults
    """

    async def _request_events(ws: str, resource: str, namespace: str = 'default', kind: str = 'Pod') -> None:
        """Get k8s events for some resource.

        :param uri: The location of the server
        :param pod: The name of the resource you are asking about.
        :param namespace: The namespace of the resource you are asking about.
        :param kind: The kind of resource you are asking about.
        """
        async with websockets.connect(ws) as websocket:
            await websocket.send(
                json.dumps(
                    {
                        APIField.COMMAND: 'EVENTS',
                        APIField.REQUEST: {'resource': resource, 'namespace': namespace, 'kind': kind},
                    }
                )
            )
            resp = json.loads(await websocket.recv())
            if resp[APIField.STATUS] == APIStatus.ERROR:
                LOGGER.error(resp)
                return
            if resp[APIField.STATUS] == APIStatus.OK:
                _events = [_event_def(f'evt-{resource}-{i}', r) for i, r in enumerate(resp[APIField.RESPONSE])]

        return EventResults(_events)

    ws = flask.globals.current_app.ws_url
    loop = flask.globals.current_app.ws_event_loop
    asyncio.set_event_loop(loop)
    return asyncio.get_event_loop().run_until_complete(_request_events(ws, id_))


def _event_def(id_, row):
    event_def = EventDefinition()
    event_def.id = id_
    event_def.event_type = row['type']
    event_def.reason = row['reason']
    event_def.source = row['source']
    event_def.message = row['message']
    event_def.timestamp = row['timestamp']

    return event_def


def _step_status(row):
    s = TaskStatusDefinition()
    s.task = row['task']
    s.status = row['status']
    s.command = row['command']
    s.name = row['name']
    s.image = row['image']
    s.resource_type = row['resource_type']
    s.resource_id = row['resource_id']
    s.submit_time = row['submitted']
    s.completion_time = row['completed']
    s.id = s.task
    return s


def _pipeline_status(row):
    p = PipelineDefinition()
    p.name = row['label']
    p.id = p.name
    p.job = row['job']  # get_job(row['job'])
    p.status = row['status']
    p.submit_time = row['submitted']
    p.version = row.get('version')
    p.completion_time = row['completed']
    return p


def _get_job_files(job_loc):
    configs = []
    job_dir = os.path.dirname(job_loc)
    base = os.path.basename(job_loc)
    for f in os.listdir(job_dir):
        if f == base:
            continue
        if (
            f.endswith(".py")
            or f.endswith(".js")
            or f.endswith("txt")
            or f.endswith(".yml")
            or f.endswith(".sh")
            or f.endswith("yaml")
            or f.endswith("json")
            or f.endswith("config")
            or f.endswith("cfg")
        ):
            id_ = os.path.join(job_dir, f)
            content = _read_file(id_)
            configs.append(ConfigDefinition(id=id_, name=f, content=content))
    return configs


def _job_def(id_):
    try:
        job_loc = _get_job_file(id_, 'main.yml')
        object = read_yaml(job_loc)
        job_def = JobDefinition(tasks=[])
        job_def.location = job_loc
        job_def.name = id_
        job_def.id = id_
        for t in object['tasks']:
            if 'mounts' not in t:
                t['mounts'] = t.pop('mount')
            name = t['name']
            t['id'] = f'{id_}--{name}'
            task_def = TaskDefinition(**t)
            job_def.tasks.append(task_def)
        job_def.configs = _get_job_files(job_loc)
        return job_def
    except:
        return None


async def _request_status(ws, work):
    """Request the status of a job from the server."""
    pipe_statuses = []
    async with websockets.connect(ws) as websocket:
        await websocket.send(json.dumps({APIField.COMMAND: 'STATUS', APIField.REQUEST: work}))

        results = json.loads(await websocket.recv())
        if results[APIField.STATUS] == APIStatus.ERROR:
            LOGGER.error(results)
            return
        if results[APIField.STATUS] == APIStatus.OK:
            results = results[APIField.RESPONSE]
            for result in results:
                task_status = [_step_status(r) for r in result['task_statuses']]
                pipe_status = _pipeline_status(result['pipeline_status'])
                pipe_status.tasks = task_status
                pipe_statuses.append(pipe_status)
        return PipelineResults(pipe_statuses)


def get_pipeline(id_):  # noqa: E501
    """Get a Pipeline status

     # noqa: E501

    :param id_: ID of job
    :type id_: str

    :rtype: PipelineWrapperDefinition
    """

    ws = flask.globals.current_app.ws_url
    loop = flask.globals.current_app.ws_event_loop
    asyncio.set_event_loop(loop)
    result = asyncio.get_event_loop().run_until_complete(_request_status(ws, id_))
    if result:
        return PipelineWrapperDefinition(result.pipelines[0])
    raise Exception(f"No such pipeline {id_}")


def get_pipelines(q='*'):  # noqa: E501
    """Get Pipeline info

     # noqa: E501

    :param q: Get jobs by partial name match
    :type q: str

    :rtype: PipelineResults
    """
    ws = flask.globals.current_app.ws_url
    loop = flask.globals.current_app.ws_event_loop
    asyncio.set_event_loop(loop)

    return asyncio.get_event_loop().run_until_complete(_request_status(ws, q))


def get_job(id_):  # noqa: E501
    """Get Job info

     # noqa: E501

    :param id_: Get pipeline by ID
    :type id_: str

    :rtype: JobWrapperDefinition
    """
    id_ = _convert_to_path(id_)
    _update_job_repo()
    return JobWrapperDefinition(_job_def(id_))


def get_jobs(q='*'):  # noqa: E501
    """Get Job info

     # noqa: E501

    :param q: Get jobs by partial name match
    :type q: str

    :rtype: JobResults
    """
    _update_job_repo()
    job_defs = []
    q = _convert_to_path(q)
    file_star = '{}*'.format(q)
    for path_value in glob.glob(os.path.join(flask.globals.current_app.root_path, file_star)):
        id_ = os.path.basename(path_value)
        job_loc = os.path.join(path_value, 'main.yml')
        if os.path.exists(job_loc) and os.path.isfile(job_loc):
            job_def = _job_def(id_)
            if job_def:
                job_defs.append(job_def)
    return JobResults(job_defs)

