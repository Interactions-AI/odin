"""Websocket client to check if odin is running."""

import argparse
import asyncio
from datetime import datetime
import json
import websockets
from odin import LOGGER, APIField, APIStatus
from odin.client import ODIN_URL, ODIN_PORT, ODIN_SCHEME


async def ping(uri: str, message: str) -> None:
    """Ping odin at uri and send message.

    :param uri: The location of the server
    :param message: The message you expect to see back
    :raises RuntimeError: If the server returns an error
    """
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({APIField.COMMAND: 'PING', APIField.REQUEST: message}))
        resp = json.loads(await websocket.recv())
        if resp[APIField.STATUS] == APIStatus.ERROR:
            LOGGER.error(resp)
            raise RuntimeError(resp)
        LOGGER.info(resp[APIField.RESPONSE])


def main():
    """Websocket client for pinging odin."""
    parser = argparse.ArgumentParser(description='Websocket-based health check')
    parser.add_argument('--host', default=ODIN_URL, type=str)
    parser.add_argument('--port', default=ODIN_PORT)
    parser.add_argument(
        '--scheme',
        choices={'wss', 'ws'},
        default=ODIN_SCHEME,
        help='Websocket connection protocol, use `wss` for remote connections and `ws` for localhost',
    )
    parser.add_argument('--message', default=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    args = parser.parse_args()
    ws = f'{args.scheme}://{args.host}:{args.port}'
    asyncio.get_event_loop().run_until_complete(ping(ws, args.message))


if __name__ == "__main__":
    main()
