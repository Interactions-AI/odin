"""A websocket client to get or stream logs from a container."""

import json
import asyncio
import argparse
import signal
from typing import Optional
import websockets
from odin import LOGGER, APIField, APIStatus
from odin.client import ODIN_URL, ODIN_PORT


async def request_logs(
    ws: str, resource: str, namespace: str, container: str, follow: bool, lines: Optional[int] = None
) -> None:
    """Make the websocket request to get the logs.

    :param ws: The websocket host
    :param resource: The thing to get logs from
    :param namespace: The namespace the pod is in
    :param container: The container to get the logs from, only needed
        when there are multiple containers in a pod
    :param follow: Should you get all the logs available right now or stream
        them as they come in?
    """
    work = {'resource': resource, 'namespace': namespace, 'follow': follow}
    if container is not None:
        work['container'] = container
    if lines is not None:
        work['lines'] = lines
    async with websockets.connect(ws) as websocket:
        await websocket.send(json.dumps({APIField.COMMAND: 'LOGS', APIField.REQUEST: work}))
        line = json.loads(await websocket.recv())
        while line[APIField.STATUS] != APIStatus.END:
            if line[APIField.STATUS] == APIStatus.ERROR:
                LOGGER.error(line)
                break
            LOGGER.info(line[APIField.RESPONSE])
            line = json.loads(await websocket.recv())


def main():
    """Async websocket client to get logs from k8s pods."""

    signal.signal(signal.SIGINT, lambda *args, **kwargs: exit(0))

    parser = argparse.ArgumentParser()
    parser.add_argument('resource', help="The name of pod to get logs from.")
    parser.add_argument('--namespace', default='default', help="The namespace the pod is in.")
    parser.add_argument(
        '--container', help="The container to get logs from, only needed if there are multiple containers."
    )
    parser.add_argument(
        '--follow', '-f', action='store_true', help="Should you stream the logs or just get what is there now?"
    )
    parser.add_argument('--lines', '-l', type=int, help="How many lines from the end of the logs to grab")
    parser.add_argument('--host', default=ODIN_URL, type=str, help="The location of the server")
    parser.add_argument('--port', default=ODIN_PORT, help="The port the server listens on.")
    parser.add_argument(
        '--scheme',
        choices={'wss', 'ws'},
        default='wss',
        help='Websocket connection protocol, use `wss` for remote connections and `ws` for localhost',
    )
    args = parser.parse_args()

    ws = f'{args.scheme}://{args.host}:{args.port}'
    asyncio.get_event_loop().run_until_complete(
        request_logs(ws, args.resource, args.namespace, args.container, args.follow, args.lines)
    )


if __name__ == "__main__":
    main()
