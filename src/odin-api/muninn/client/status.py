"""Websocket client to get the status a job."""

import json
import asyncio
import argparse
from typing import Set, List, Optional
import websockets
from collections import namedtuple
from eight_mile.utils import listify, read_config_stream
from baseline.utils import exporter, color, Colors

from muninn.formatting import show_status, Row, Pipeline
from muninn import ODIN_URL, ODIN_PORT, ODIN_SCHEME, HttpClient, ODIN_API_LOGGER, APIField, APIStatus




async def request_status(ws: str, work: str, columns: Set[str], all_cols: bool = False) -> None:
    """Request the status of an odin job over web-sockets
    :param ws: The web socket
    :param work: the job name
    :param columns: A set of columns to include in the output
    :param all_cols: Should we just show all columns, If true then columns in ignored
    """
    async with websockets.connect(ws) as websocket:
        await websocket.send(json.dumps({APIField.COMMAND: 'STATUS', APIField.REQUEST: work}))

        results = json.loads(await websocket.recv())
        if results[APIField.STATUS] == APIStatus.ERROR:
            ODIN_API_LOGGER.error(results)
            return
        if results[APIField.STATUS] == APIStatus.OK:
            results = results[APIField.RESPONSE]
            for result in results:
                rows = [Row(**r) for r in result['task_statuses']]
                show_status(Pipeline(**result['pipeline_status']), rows, columns, all_cols)


def _task2row(task):
    row = Row(
        task=task.get('task'),
        status=task.get('status'),
        command=task.get('command'),
        name=task.get('name'),
        image=task.get('image'),
        resource_type=task.get('resourceType'),
        resource_id=task.get('resourceId'),
        submitted=task.get('submitTime'),
        completed=task.get('completionTime'),
    )

    return row


def _result2pipe(result):
    pipe = Pipeline(
        label=result.get('id'),
        job=result.get('job'),
        submitted=result.get('submitTime'),
        completed=result.get('completionTime'),
        status=result.get('status'),
        version=result.get('version'),
    )

    return pipe


def request_status_http(url: str, work: str, columns: Set[str], all_cols: bool = False) -> None:
    """Request the status over HTTP
    :param url: the base URL
    :param work: The pipeline ID
    :param columns: A set of columns to include in the output
    :param all_cols: Should we just show all columns, If true then columns in ignored
    """
    results = HttpClient(url).request_status(work)
    for result in results:
        rows = [_task2row(r) for r in result['tasks']]
        show_status(_result2pipe(result), rows, columns, all_cols)


def main():
    """A websocket client to request a job status."""
    parser = argparse.ArgumentParser(description="Websocket-based job clean-up")
    parser.add_argument('work', help='Job')
    parser.add_argument('--host', default=ODIN_URL, type=str)
    parser.add_argument('--port', default=ODIN_PORT)
    parser.add_argument(
        '--scheme',
        choices={'wss', 'ws', 'http', 'https'},
        default=ODIN_SCHEME,
        help='Connection protocol, use `http` for REST, use `wss` for remote connections and `ws` for localhost',
    )
    parser.add_argument('--columns', nargs="+", default=[], help="Columns of the status to show.")
    parser.add_argument('--all', action='store_true', help="Show all columns of the status message.")
    args = parser.parse_args()

    url = f'{args.scheme}://{args.host}:{args.port}'

    if args.scheme.startswith('ws'):
        asyncio.get_event_loop().run_until_complete(request_status(url, args.work, set(args.columns), args.all))
    else:
        request_status_http(url, args.work, set(args.columns), args.all)


if __name__ == "__main__":
    main()
