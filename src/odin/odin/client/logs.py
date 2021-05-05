"""A websocket client to get or stream logs from a container."""

import json
import asyncio
import argparse
import signal
from typing import Optional
import websockets
from odin import LOGGER, APIField, APIStatus
from odin.client import ODIN_URL, ODIN_PORT, ODIN_SCHEME, HttpClient


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
    :param lines: How many lines to grab

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


def log_all_children_http(url, resource, namespace):
    client = HttpClient(url=url)
    try:
        print(client.request_logs(resource, namespace))
    except:
        head = find_head(resource)
        data = client.request_data(head)
        for job in data['jobs']['jobs']:
            rid = client.request_data(job)['jobs']['resource_id']
            print('================')
            print(rid)
            print('----------------')
            try:
                logs = client.request_logs(rid, namespace)
                print(logs)
            except:
                try:
                    # If everything still fails, it could be a Kubeflow job child
                    logs = client.request_logs(f'{rid}-master-0', namespace)
                    print(logs)
                except:
                    print('Failed to get log')


def find_head(resource):
    # Lets try and find this resource
    head = resource.split('j--')[0]
    if not head.endswith('j'):
        head += 'j'
    return head


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
        choices={'http', 'https', 'wss', 'ws'},
        default=ODIN_SCHEME,
        help='Websocket connection protocol, use `wss` for remote connections and `ws` for localhost',
    )
    args = parser.parse_args()

    endpoint = f'{args.scheme}://{args.host}:{args.port}'

    if args.scheme.startswith('http'):
        log_all_children_http(endpoint, args.resource, args.namespace)

    else:

        asyncio.get_event_loop().run_until_complete(
            request_logs(endpoint, args.resource, args.namespace, args.container, args.follow, args.lines)
        )


if __name__ == "__main__":
    main()
