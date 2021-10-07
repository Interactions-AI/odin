import os
import logging
import websockets
import git
import json
import re
from odin import *

LOGGER = logging.getLogger('odin-http')


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


def _event_def(id_, row):
    event_def = EventDefinition(
        id=id_,
        event_type=row['type'],
        reason=row['reason'],
        source=row['source'],
        message=row['message'],
        timestamp=row['timestamp'],
    )

    return event_def


def _step_status(row):
    s = TaskStatusDefinition(
        task=row['task'],
        status=row['status'],
        command=row['command'],
        name=row['name'],
        image=row['image'],
        resource_type=row['resource_type'],
        submit_time=row['submitted'],
        completion_time=row['completed'],
        id=row['task'],
        resource_id=row['task']
    )

    return s


def _pipeline_status(row):
    p = PipelineDefinition(
        name=row['label'],
        id=row['label'],
        job=row['job'],
        status=row['status'],
        submit_time=row['submitted'],
        version=row.get('version'),
        completion_time=row['completed']
    )
    return p


def _convert_to_path(resource_id: str) -> str:
    """Convert something like dpressel__ag-news into dpressel/ag-news
    :param resource_id:
    :return:
    """
    return resource_id.replace('__', '/')


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
        return PipelineResults(pipelines=pipe_statuses)


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
            return PipelineCleanupResults(cleanups=cleanup_def)


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

        return EventResults(events=_events)


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

def _validate_filename(filename):
    matcher = re.compile(r'^[^<>:;,?"*|/]+$')
    if not matcher.match(filename):
        raise Exception("Invalid file name: {}".format())


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

