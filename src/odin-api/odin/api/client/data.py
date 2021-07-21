"""HTTP client to get job data."""

import json
import asyncio
import argparse
import websockets
from odin.api import ODIN_URL, ODIN_PORT, ODIN_SCHEME, HttpClient, ODIN_API_LOGGER, APIField, APIStatus


async def request_data(url: str, resource: str) -> None:
    """Get k8s data for some resource.

    :param url: The location of the server
    :param resource: The name of the resource you are asking about.
    :param namespace: The namespace of the resource you are asking about.
    """
    async with websockets.connect(url) as websocket:
        await websocket.send(json.dumps({APIField.COMMAND: 'DATA', APIField.REQUEST: {'resource': resource}}))
        resp = json.loads(await websocket.recv())
        if resp[APIField.STATUS] == APIStatus.ERROR:
            ODIN_API_LOGGER.error(resp)
            return
        if resp[APIField.STATUS] == APIStatus.OK:
            print(json.dumps(resp[APIField.RESPONSE]))


def request_data_http(url: str, resource: str) -> None:
    """Get data for a resource over HTTP

    :param url: The base URL
    :param resource: The resource ID
    """
    results = HttpClient(url).request_data(resource)
    print(json.dumps(results))


def main():
    """Websocket client for pinging odin."""
    parser = argparse.ArgumentParser(description='Websocket-based health check')
    parser.add_argument('--host', default=ODIN_URL, type=str)
    parser.add_argument('--port', default=ODIN_PORT)
    parser.add_argument(
        '--scheme',
        choices={'wss', 'ws', 'http', 'https'},
        default=ODIN_SCHEME,
        help='Connection protocol, use `http` for REST, use `wss` for remote connections and `ws` for localhost',
    )
    parser.add_argument('resource', help="The name of the resource to describe")
    args = parser.parse_args()
    url = f'{args.scheme}://{args.host}:{args.port}'

    if args.scheme.startswith('ws'):
        asyncio.get_event_loop().run_until_complete(request_data(url, args.resource))
    else:
        request_data_http(url, args.resource)


if __name__ == "__main__":
    main()
