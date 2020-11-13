"""Serve pipelines over websockets
"""
import os
import json
import logging
import argparse
import asyncio
import traceback
from datetime import datetime, date
from typing import Dict, Any, Optional
from functools import partial
import websockets
import git
from bson.json_util import dumps as bson_dumps
from eight_mile.utils import read_config_stream
from mead.utils import convert_path
from odin import ODIN_LOGO, APIField, APIStatus
from odin.cleanup import cleanup
from odin.core import read_pipeline_config
from odin.generate import generate_pipeline
from odin.executor import Executor
from odin.status import get_status
from odin.store import create_store_backend, create_cache_backend
from odin.k8s import KubernetesTaskManager, KF_MODULES, ELASTIC_MODULES, CORE_MODULES

LOGGER = logging.getLogger('odin')

STORE = None
CACHE = None
ROOT_PATH = None
DATA_PATH = None


def seralize(obj: Any) -> str:
    """Callable on non-serialize able objects, handles datatimes.

    :param obj: The unserialzable object.
    :raises TypeError: When the object can't be serialized.
    :returns: The serialized object.
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not JSON serializable")


async def send_with_extra(websocket: 'Websocket', extras: Dict, data: Dict) -> None:
    """Send data with extras added encoded as a json string over websocket.

    :param websocket: The connection to send the data over
    :param extras: Extra data to add into the response before you send it
    :param data: The response
    """
    data.update(extras)
    await websocket.send(json.dumps(data, default=seralize))


async def handle_request(websocket, _) -> None:  # pylint: disable=too-many-branches,too-many-statements,too-many-locals
    """Async handler for a websocket, runs the pipeline

    :param websocket: A handle to the socket
    :param _: ?
    """
    global ROOT_PATH
    global DATA_PATH
    request = await websocket.recv()
    LOGGER.info(request)

    try:
        request = json.loads(request)
        cmd = request.pop(APIField.COMMAND)
        work = request.pop(APIField.REQUEST)
        send = partial(send_with_extra, websocket, request)

        if cmd == 'START':
            work = os.path.normpath(work)
            work_path = os.path.join(ROOT_PATH, work)
            context, tasks = read_pipeline_config(work_path, ROOT_PATH, DATA_PATH)
            LOGGER.info(context)
            pipe = Executor(STORE, cache=CACHE, modules=MODULES)
            pipe_id = context['PIPE_ID']
            try:
                repos = git.Repo(ROOT_PATH)
                rev_ver = str(git.repo.fun.rev_parse(repos, 'HEAD'))
            except Exception:
                LOGGER.warning("Failed to get revision version")
                rev_ver = None

            await send({APIField.STATUS: APIStatus.OK, APIField.RESPONSE: pipe_id})
            async for log in pipe.run(pipe_id, os.path.basename(work_path), rev_ver, tasks):
                try:
                    await send({APIField.STATUS: APIStatus.OK, APIField.RESPONSE: log})
                except websockets.exceptions.ConnectionClosed:
                    continue
            try:
                await send({APIField.STATUS: APIStatus.END, APIField.RESPONSE: pipe_id})
            except websockets.exceptions.ConnectionClosed:
                return
        elif cmd == 'SHOW':
            pipeline_loc = os.path.join(ROOT_PATH, work)
            try:
                defs = {f: open(os.path.join(pipeline_loc, f)).read() for f in os.listdir(pipeline_loc)}
                await send({APIField.STATUS: APIStatus.OK, APIField.RESPONSE: defs})
            except FileNotFoundError as exc:
                LOGGER.error(exc)
                await send({APIField.STATUS: APIStatus.ERROR, APIField.RESPONSE: str(exc)})
        elif cmd == 'GENERATE':
            try:
                pipeline_name = generate_pipeline(ROOT_PATH, **work)
                await send({APIField.STATUS: APIStatus.OK, APIField.RESPONSE: pipeline_name})
            except FileExistsError as exc:
                LOGGER.error(exc)
                await send({APIField.STATUS: APIStatus.ERROR, APIField.RESPONSE: str(exc)})
        elif cmd == 'CLEANUP':
            cleaned = [c._asdict() for c in cleanup(**work, store=STORE, data_dir=DATA_PATH)]
            await send({APIField.STATUS: APIStatus.OK, APIField.RESPONSE: cleaned})
        elif cmd == 'STATUS':
            work = STORE.parents_like(work)
            results = [
                {'pipeline_status': {**pipe._asdict()}, 'task_statuses': [r._asdict() for r in rows]}
                for pipe, rows in (get_status(w, STORE) for w in work)
            ]
            await send({APIField.STATUS: APIStatus.OK, APIField.RESPONSE: results})
        elif cmd == 'PING':
            response = f"PONG {work}"
            await send({APIField.STATUS: APIStatus.OK, APIField.RESPONSE: response})
        elif cmd == 'EVENTS':
            task_mgr = KubernetesTaskManager(STORE, modules=MODULES)
            await send(
                {
                    APIField.STATUS: APIStatus.OK,
                    APIField.RESPONSE: [e._asdict() for e in task_mgr.get_events(name=work.get('resource'))],
                }
            )
        elif cmd == 'DATA':
            obj = STORE.get(work.get('resource'))
            obj = json.loads(bson_dumps({'success': True, 'jobs': obj}))
            await send({APIField.STATUS: APIStatus.OK, APIField.RESPONSE: obj})
        elif cmd == 'LOGS':
            task_mgr = KubernetesTaskManager(STORE, modules=MODULES)
            name = work.pop('resource')
            work.pop('namespace')
            work['name'] = name
            if work.pop('follow', False):
                async for log in task_mgr.follow_logs(name):
                    try:
                        await send({APIField.STATUS: APIStatus.OK, APIField.RESPONSE: log})
                    except websockets.exceptions.ConnectionClosed:
                        return
            else:
                await send({APIField.STATUS: APIStatus.OK, APIField.RESPONSE: task_mgr.get_logs(**work)})
            await send({APIField.STATUS: APIStatus.END, APIField.RESPONSE: 'LOGS'})
        else:
            await send({APIField.STATUS: APIStatus.ERROR, APIField.RESPONSE: f"{cmd} not found."})
    except Exception as exc:
        LOGGER.error(traceback.format_exc())
        # Because this error can happen before send is bound and we send the request back anyway there is no need to
        # do the merge and send code.
        await websocket.send(json.dumps({APIField.STATUS: APIStatus.ERROR, APIField.RESPONSE: str(exc)}))


def get_db_config(cred: Optional[str]) -> Dict:
    """

    :param cred:
    :return:
    """
    if cred:
        cred_params = read_config_stream(cred)['jobs_db']

    else:
        cred_params = {}
        cred_params['backend'] = os.environ.get("ODIN_JOBS_BACKEND", "postgres")
        cred_params['host'] = os.environ.get("SQL_HOST", "127.0.0.1")
        cred_params['port'] = os.environ.get("DB_PORT", 5432)
        cred_params['user'] = os.environ.get("DB_USER")
        cred_params['passwd'] = os.environ.get("DB_PASS")
    cred_params['db'] = os.environ.get("DB_NAME", "jobs_db")
    return cred_params


def main():
    """Launch a websocket server that will run forever and serve pipelines
    """
    global STORE
    global CACHE
    global ROOT_PATH
    global DATA_PATH
    global MODULES
    parser = argparse.ArgumentParser(description='Websocket-based Pipeline scheduler')
    parser.add_argument('--root_path', help='Root directory', type=convert_path, required=True)
    parser.add_argument('--host', default='0.0.0.0', type=str)
    parser.add_argument('--port', default='30000')
    parser.add_argument('--cred', help='cred file', type=convert_path)
    parser.add_argument('--data_path', help='data directory')
    parser.add_argument('--modules', default='all', choices=['all', 'kf', 'elastic', 'core'])
    args = parser.parse_args()

    MODULES = CORE_MODULES
    if args.modules in ['kf', 'all']:
        MODULES += KF_MODULES
    if args.modules in ['elastic', 'all']:
        MODULES = ELASTIC_MODULES + CORE_MODULES
    config_params = get_db_config(args.cred)
    STORE = create_store_backend(**config_params)
    CACHE = create_cache_backend(**config_params)
    ROOT_PATH = os.path.normpath(args.root_path)
    args.data_path = args.data_path if args.data_path is not None else args.root_path
    DATA_PATH = os.path.normpath(args.data_path)

    start_server = websockets.serve(handle_request, args.host, args.port)
    asyncio.get_event_loop().run_until_complete(start_server)
    LOGGER.info(ODIN_LOGO)
    LOGGER.info("Ready to serve.")
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
