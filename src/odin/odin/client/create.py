"""Create a Job on a remote odin server."""

import os
import json
import argparse
from getpass import getuser
from odin.client import ODIN_URL, ODIN_PORT, ODIN_SCHEME, HttpClient
from odin.utils.auth import get_jwt_token


def create_job_http(url: str, jwt_token: str, name: str) -> None:
    """Request the server makes a new job.

    :param url: Base url of the remote odin server
    :param jwt_token: You JWT authentication token
    :param name: The name of the job you want to create
    """
    results = HttpClient(url, jwt_token).create_job(name)
    print(json.dumps(results))


def main():
    """Websocket client for pinging odin."""
    parser = argparse.ArgumentParser(description='Create a job')
    parser.add_argument('job', help="The name of the job you are creating")
    parser.add_argument('--host', default=ODIN_URL, type=str)
    parser.add_argument('--port', default=ODIN_PORT)
    parser.add_argument('--token', help="File where JWT token can reside", default=os.path.expanduser("~/.odin.token"))
    parser.add_argument('--username', '-u', help="Username", default=getuser())
    parser.add_argument('--password', '-p', help="Password")
    parser.add_argument(
        '--scheme', choices={'http', 'https'}, default=ODIN_SCHEME, help='Connection protocol, use `http` for REST.'
    )
    args = parser.parse_args()
    url = f'{args.scheme}://{args.host}:{args.port}'

    jwt_token = get_jwt_token(url, args.token, args.username, args.password)
    try:
        create_job_http(url, jwt_token, args.job)
    except ValueError:
        if os.path.exists(args.token):
            os.remove(args.token)
            jwt_token = get_jwt_token(url, args.token, args.username, args.password)
            create_job_http(url, jwt_token, args.job)


if __name__ == "__main__":
    main()
