"""Client to run odin jobs"""
import argparse
from getpass import getuser
import os
import asyncio
import json
import signal
import requests
import websockets
from odin import LOGGER, APIField, APIStatus
from odin.client import ODIN_URL, ODIN_PORT, HttpClient
from odin.utils.auth import get_jwt_token


async def schedule_pipeline(ws, work) -> None:
    """Use async to open a connection to serve.py and launch work

    Blocks until the job completes (and websocket stays open)
    """
    async with websockets.connect(ws) as websocket:
        await websocket.send(json.dumps({APIField.COMMAND: 'START', APIField.REQUEST: work}))

        result = json.loads(await websocket.recv())
        while result[APIField.STATUS] != APIStatus.END:
            if result[APIField.STATUS] == APIStatus.ERROR:
                LOGGER.error(result)
                return

            if result[APIField.RESPONSE].startswith('PIPE_ID'):
                pipe_id = result.split(' ')[-1]
                LOGGER.info('Started %s', pipe_id)
            else:
                LOGGER.info(result[APIField.RESPONSE])
            result = json.loads(await websocket.recv())


def schedule_pipeline_http(url: str, jwt_token: str, work: str) -> None:
    """Request the status over HTTP
    :param url: the base URL
    :param jwt_token: The JWT token representing this authentication
    :param work: The pipeline ID
    """
    results = HttpClient(url, jwt_token=jwt_token).schedule_pipeline(work)
    print(json.dumps(results))


def main():
    """Use `asyncio` to connect to a websocket and request a pipeline, wait.
    """
    signal.signal(signal.SIGINT, lambda *args, **kwargs: exit(0))

    parser = argparse.ArgumentParser(description='Websocket-based Pipeline scheduler')
    parser.add_argument('work', help='Job')
    parser.add_argument('--host', default=ODIN_URL, type=str)
    parser.add_argument('--port', default=ODIN_PORT)
    parser.add_argument('--token', help="File where JWT token can reside", default=os.path.expanduser("~/.odin.token"))
    parser.add_argument('--username', '-u', help="Username", default=getuser())
    parser.add_argument('--password', '-p', help="Password")
    parser.add_argument(
        '--scheme',
        choices={'http', 'wss', 'ws', 'https'},
        default='https',
        help='Connection protocol, use `http` for REST, use `wss` for remote connections and `ws` for localhost',
    )
    args = parser.parse_args()
    url = f'{args.scheme}://{args.host}:{args.port}'

    if args.scheme.startswith('ws'):
        asyncio.get_event_loop().run_until_complete(schedule_pipeline(url, args.work))
    else:
        jwt_token = get_jwt_token(url, args.token, args.username, args.password)
        try:
            schedule_pipeline_http(url, jwt_token, args.work)
        except ValueError:
            # Try deleting the token file and start again
            if os.path.exists(args.token):
                os.remove(args.token)
                jwt_token = get_jwt_token(url, args.token, args.username, args.password)
                schedule_pipeline_http(url, jwt_token, args.work)


if __name__ == '__main__':
    main()
