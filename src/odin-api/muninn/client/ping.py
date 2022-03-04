"""Websocket client to check if odin is running."""

import argparse
import asyncio
from datetime import datetime
import json
import websockets
from muninn import ODIN_URL, ODIN_PORT, ODIN_SCHEME, HttpClient, ODIN_API_LOGGER, APIField, APIStatus


async def ping(uri: str) -> None:
    """Ping odin at uri and send message.

    :param uri: The location of the server
    :raises RuntimeError: If the server returns an error
    """
    async with websockets.connect(uri) as websocket:
        message = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        await websocket.send(json.dumps({APIField.COMMAND: 'PING', APIField.REQUEST: message}))
        resp = json.loads(await websocket.recv())
        if resp[APIField.STATUS] == APIStatus.ERROR:
            print('ERROR', resp)
            raise RuntimeError(resp)
        print(resp[APIField.RESPONSE])

def ping_http(url: str) -> None:
    """Get data for a resource over HTTP

    :param url: The base URL
    :param resource: The resource ID
    """
    try:

        results = HttpClient(url).app_info()
        print(json.dumps(results))
    except Exception as e:
        print('Error pinging server')
        print(e)

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
    args = parser.parse_args()
    url = f'{args.scheme}://{args.host}:{args.port}'

    if args.scheme.startswith('ws'):
        asyncio.get_event_loop().run_until_complete(ping(url))
    else:
        ping_http(url)
    args = parser.parse_args()
    ws = f'{args.scheme}://{args.host}:{args.port}'



if __name__ == "__main__":
    main()
