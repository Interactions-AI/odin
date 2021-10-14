"""Websocket client to get the k8s events that act on some resource."""

import json
import asyncio
import argparse
import websockets
from collections import namedtuple
from muninn import ODIN_URL, ODIN_PORT, ODIN_SCHEME, HttpClient, ODIN_API_LOGGER, APIField, APIStatus
from muninn.formatting import print_table, Event

async def request_events(url: str, resource: str, namespace: str = 'default') -> None:
    """Get k8s events for some resource.

    :param url: The location of the server
    :param resource: The name of the resource you are asking about.
    :param namespace: The namespace of the resource you are asking about.
    """
    async with websockets.connect(url) as websocket:
        await websocket.send(
            json.dumps({APIField.COMMAND: 'EVENTS', APIField.REQUEST: {'resource': resource, 'namespace': namespace}})
        )
        resp = json.loads(await websocket.recv())
        if resp[APIField.STATUS] == APIStatus.ERROR:
            ODIN_API_LOGGER.error(resp)
            return
        if resp[APIField.STATUS] == APIStatus.OK:
            rows = [Event(**r) for r in resp[APIField.RESPONSE]]
            print_table(rows)


def _result2event(result):
    event = Event(
        type=result.get('eventType'),
        reason=result.get('reason'),
        source=result.get('source'),
        message=result.get('message'),
        timestamp=result.get('timestamp'),
    )
    return event


def request_events_http(url: str, resource: str) -> None:
    """Get events for a resource over HTTP

    :param url: The base URL
    :param resource: The resource ID
    """
    results = HttpClient(url).request_events(resource)
    events = [_result2event(result) for result in results['events']]
    print_table(events)


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
    parser.add_argument('--namespace', default='default', help="The namespace the resource lives in.")
    args = parser.parse_args()
    url = f'{args.scheme}://{args.host}:{args.port}'

    if args.scheme.startswith('ws'):
        asyncio.get_event_loop().run_until_complete(request_events(url, args.resource, args.namespace))
    else:
        request_events_http(url, args.resource)


if __name__ == "__main__":
    main()
