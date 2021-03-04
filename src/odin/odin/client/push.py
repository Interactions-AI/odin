"""Client to push files to the server."""

import os
import json
import argparse
from getpass import getuser
from odin.client import ODIN_URL, ODIN_PORT, HttpClient
from odin.utils.auth import get_jwt_token
from baseline.utils import color, Colors


def push_file_maybe_create_job(url: str, jwt_token: str, job: str, file_name: str, file_contents: str, create_job: bool) -> None:
    """Push a file to update a remove pipeline.

    :param url: The odin-http endpoint
    :param jwt_token: The jwt token used to auth with odin
    :param job: The job definition that will be updated
    :param file_name: The name to save the file as on the remove server
    :param file_contents: The content of the file we want to upload
    """
    client = HttpClient(url, jwt_token=jwt_token)
    if create_job:
        results = client.create_job(job)
        if 'status' in results:
            status = color('Failed tor create a new job. If the job already exists, do not try to create', Colors.RED)
            print(json.dumps(results))
            print(status)
            return
    results = client.push_file(job, file_name, file_contents)
    print(json.dumps(results))


def main():
    """This should have auth around it."""
    parser = argparse.ArgumentParser(description="Upload a file to odin")
    parser.add_argument('job', help='The Job to push the file to')
    parser.add_argument('file', help='The data to upload')
    parser.add_argument('--file_name', help='The name for the file on remote, defaults to the local file name')
    parser.add_argument('--host', default=ODIN_URL, type=str, help="The odin http host")
    parser.add_argument('--port', default=ODIN_PORT, help="The odin http port")
    parser.add_argument('--token', help="File where JWT token can reside", default=os.path.expanduser("~/.odin.token"))
    parser.add_argument('--create', '-c', action='store_true', help="If this is given, we will attempt to create a job with this name")
    parser.add_argument('--username', '-u', help="Username", default=getuser())
    parser.add_argument('--password', '-p', help="Password")
    parser.add_argument(
        '--scheme',
        choices={'https', 'http'},
        default='https',
        help="Use https for remote connections and http for local",
    )
    args = parser.parse_args()

    url = f'{args.scheme}://{args.host}:{args.port}'
    file_name = args.file_name if args.file_name is not None else args.file
    with open(args.file) as rf:
        file_contents = rf.read()

    jwt_token = get_jwt_token(url, args.token, args.username, args.password)
    try:
        push_file_maybe_create_job(url, jwt_token, args.job, file_name, file_contents, args.create)
    except ValueError:
        # Try deleting the token file and start again
        if os.path.exists(args.token):
            os.remove(args.token)
            jwt_token = get_jwt_token(url, args.token, args.username, args.password)
            push_file_maybe_create_job(url, jwt_token, args.job, file_name, file_contents, args.create)


if __name__ == "__main__":
    main()
