"""Client to push files to the server."""

import os
import json
import argparse
from getpass import getuser
import requests
from odin.client import ODIN_URL, ODIN_PORT, encode_path
from odin.utils.auth import get_jwt_token


def push_file(url: str, jwt_token: str, job: str, file_name: str, file_contents: str) -> None:
    """Push a file to update a remove pipeline.

    :param url: The odin-http endpoint
    :param jwt_token: The jwt token used to auth with odin
    :param job: The job definition that will be updated
    :param file_name: The name to save the file as on the remove server
    :param file_contents: The content of the file we want to upload
    """
    job = encode_path(job)
    response = requests.post(
        f'{url}/v1/jobs/{job}/files/{file_name}',
        data=file_contents,
        headers={'Content-Type': 'text/plain', 'Authorization': f'Bearer {jwt_token}'},
    )
    if response.status_code == 401:
        raise ValueError("Invalid login")
    result = response.json()
    print(json.dumps(result))


def main():
    """This should have auth around it."""
    parser = argparse.ArgumentParser(description="Upload a file to odin")
    parser.add_argument('work', help='The Job to push the file to')
    parser.add_argument('file', help='The data to upload')
    parser.add_argument('--file_name', help='The name for the file on remote, defaults to the local file name')
    parser.add_argument('--host', default=ODIN_URL, type=str, help="The odin http rul")
    parser.add_argument('--port', default=ODIN_PORT, help="The odin http port")
    parser.add_argument('--token', help="File where JWT token can reside", default=os.path.expanduser("~/.odin.token"))
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
        push_file(url, jwt_token, args.work, file_name, file_contents)
    except ValueError:
        # Try deleting the token file and start again
        if os.path.exists(args.token):
            os.remove(args.token)
            jwt_token = get_jwt_token(url, args.token, args.username, args.password)
            push_file(url, jwt_token, args.work, file_name, file_contents)


if __name__ == "__main__":
    main()
