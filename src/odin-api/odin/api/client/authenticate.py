"""Client to authenticate a user and cache a new JWT token"""
import argparse
from getpass import getuser
import os
from odin.api import ODIN_URL, ODIN_PORT, ODIN_SCHEME, ODIN_API_LOGGER
from odin.api.auth import get_jwt_token


def authenticate_user(url: str, token_path: str, username: str, password: str) -> None:
    """Authenticate a user over HTTP
    :param url: the base URL
    :param token_path: The file location of the JWT token
    :param username: The user ID
    :param password: The password
    """
    if os.path.exists(token_path):
        os.remove(token_path)
    jwt_token = get_jwt_token(url, token_path, username, password)
    ODIN_API_LOGGER.info(jwt_token)


def main():
    """Authenticate a user and give back a JWT token
    """
    parser = argparse.ArgumentParser(description='Create or update an odin user.  Requires valid JWT token to run')
    parser.add_argument('--host', default=ODIN_URL, type=str)
    parser.add_argument('--port', default=ODIN_PORT)
    parser.add_argument('--token', help="File where JWT token can reside", default=os.path.expanduser("~/.odin.token"))
    parser.add_argument('--username', '-u', help="Create or update a username", default=getuser())
    parser.add_argument('--password', '-p', help="New or updated password")
    parser.add_argument('--scheme', choices={'http', 'https'}, default=ODIN_SCHEME, help='The protocol to communicate over')
    args = parser.parse_args()
    url = f'{args.scheme}://{args.host}:{args.port}'
    authenticate_user(url, args.token, args.username, args.password)


if __name__ == '__main__':
    main()
