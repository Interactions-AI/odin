"""Websocket client"""
import argparse
import asyncio
import json
import websockets
from odin import LOGGER, APIField, APIStatus
from odin.client import ODIN_URL, ODIN_PORT


async def request_pipeline_definitions(ws: str, pipeline: str) -> None:
    """Use async to open a connection to serve.py and get a pipeline definition."""
    async with websockets.connect(ws) as websocket:
        await websocket.send(json.dumps({APIField.COMMAND: 'SHOW', APIField.REQUEST: pipeline}))

        result = json.loads(await websocket.recv())
        if result[APIField.STATUS] == APIStatus.ERROR:
            LOGGER.error(result)
            return
        if result[APIField.STATUS] == APIStatus.OK:
            for file_name, file_contents in result[APIField.RESPONSE].items():
                LOGGER.info(file_name)
                LOGGER.info("=" * 100)
                LOGGER.info(file_contents)
                LOGGER.info("")


def main():
    """Use `asyncio` to connect to a websocket and request a pipeline definition."""
    parser = argparse.ArgumentParser(description='Websocket-based Pipeline finder')
    parser.add_argument('work', help='Job')
    parser.add_argument('--host', default=ODIN_URL, type=str)
    parser.add_argument('--port', default=ODIN_PORT)
    parser.add_argument(
        '--scheme',
        choices={'wss', 'ws'},
        default='wss',
        help='Websocket connection protocol, use `wss` for remote connections and `ws` for localhost',
    )
    args = parser.parse_args()
    ws = f'{args.scheme}://{args.host}:{args.port}'
    asyncio.get_event_loop().run_until_complete(request_pipeline_definitions(ws, args.work))


if __name__ == '__main__':
    main()
