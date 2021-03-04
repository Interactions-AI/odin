"""Websocket client to cleanup a job."""

import os
from getpass import getuser
import json
import asyncio
import argparse
import websockets
from odin import LOGGER, APIField, APIStatus
from odin.client import ODIN_URL, ODIN_PORT, HttpClient
from odin.cleanup import Cleaned
from odin.utils.formatting import print_table
from odin.utils.auth import get_jwt_token


async def request_cleanup(ws: str, work: str, purge_db: bool = False, purge_fs: bool = False):
    """Request the work is cleaned up by the server."""
    async with websockets.connect(ws) as websocket:
        args = {'work': work, 'purge_db': purge_db, 'purge_fs': purge_fs}
        await websocket.send(json.dumps({APIField.COMMAND: 'CLEANUP', APIField.REQUEST: args}))

        results = json.loads(await websocket.recv())
        if results[APIField.STATUS] == APIStatus.ERROR:
            LOGGER.error(results)
            return
        if results[APIField.STATUS] == APIStatus.OK:
            cleaned = results[APIField.RESPONSE]
            print("Results of this request:")
            print_table([Cleaned(**c) for c in cleaned])


def _result2cleanup(result):
    return Cleaned(
        task_id=result.get('taskId'),
        cleaned_from_k8s=result.get('cleanedFromK8s'),
        purged_from_db=result.get('purgedFromDb'),
        removed_from_fs=result.get('removedFromFs'),
    )


def request_cleanup_http(url: str, jwt_token: str, work: str, purge_db: bool = False, purge_fs: bool = False) -> None:
    """Request the status over HTTP
    :param url: the base URL
    :param jwt_token: The token for last user auth
    :param work: The pipeline ID
    :param purge_db: Should we delete the pipeline from the jobs db too?
    :param purge_fs: Should we remove pipeline file system artifacts?
    """
    results = HttpClient(url).delete_pipeline(jwt_token, work, purge_db, purge_fs)
    cleaned = [_result2cleanup(r) for r in results['cleanups']]
    print("Results of this request:")
    print_table(cleaned)


def main():
    """A websocket client to request a job cleanup."""
    parser = argparse.ArgumentParser(description="Websocket-based job clean-up")
    parser.add_argument('work', help='Job')
    parser.add_argument('--host', default=ODIN_URL, type=str)
    parser.add_argument('--port', default=ODIN_PORT)
    parser.add_argument('--token', help="File where JWT token can reside", default=os.path.expanduser("~/.odin.token"))
    parser.add_argument('--username', '-u', help="Username", default=getuser())
    parser.add_argument('--password', '-p', help="Password")
    parser.add_argument(
        '--scheme',
        choices={'wss', 'ws', 'http', 'https'},
        default='https',
        help='Connection protocol, use `http` for REST, use `wss` for remote connections and `ws` for localhost',
    )
    parser.add_argument('--db', '-d', action='store_true', help="Also remove from the job db")
    parser.add_argument('--fs', '-f', action='store_true', help="Also remove from the filesystem")
    args = parser.parse_args()

    url = f'{args.scheme}://{args.host}:{args.port}'

    if args.scheme.startswith('ws'):
        asyncio.get_event_loop().run_until_complete(request_cleanup(url, args.work, args.db, args.fs))
    else:
        jwt_token = get_jwt_token(url, args.token, args.username, args.password)
        try:
            request_cleanup_http(url, jwt_token, args.work, args.db, args.fs)
        except ValueError:
            # Try deleting the token file and start again
            if os.path.exists(args.token):
                os.remove(args.token)
                jwt_token = get_jwt_token(url, args.token, args.username, args.password)
                request_cleanup_http(url, jwt_token, args.work, args.db, args.fs)


if __name__ == "__main__":
    main()
