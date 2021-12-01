"""Client to create or update odin user"""
import argparse
import os
import json
import signal
import requests
from prompt_toolkit import prompt
from muninn import ODIN_URL, ODIN_PORT, ODIN_SCHEME, ODIN_API_LOGGER
from muninn.auth import get_jwt_token


def create_user_http(url: str, jwt_token: str, username: str, password: str, firstname: str, lastname: str) -> None:
    """Create or update a user over HTTP
    :param url: the base URL
    :param jwt_token: The JWT token representing this authentication
    :param username: The user ID
    :param password: The updated password
    :param firstname: The firstname
    :param lastname: The lastname
    """
    user = {"username": username, "password": password}
    if firstname:
        user['firstname'] = firstname
    if lastname:
        user['lastname'] = lastname
    headers = {'Authorization': f'Bearer {jwt_token}'}

    try:
        response = requests.get(f'{url}/v1/users/{username}')
        if response.status_code == 401:
            raise ValueError("Invalid login")
        if response.status_code != 200:
            # No such user exists so do a POST
            response = requests.post(f'{url}/v1/users', headers=headers, json={"user": user})
            if response.status_code != 200:
                raise Exception(f"Failed to create user: {username}")
            results = response.json()
            ODIN_API_LOGGER.info("Created new user")
            ODIN_API_LOGGER.info(json.dumps(results))
            return

        results = response.json()
        ODIN_API_LOGGER.info("Found existing user")
        ODIN_API_LOGGER.info(json.dumps(results))
    except Exception as ex:
        ODIN_API_LOGGER.error(ex)
        return

    response = requests.put(f'{url}/v1/users/{username}', json=user, headers=headers)
    results = response.json()
    ODIN_API_LOGGER.info(json.dumps(results))


def main():
    """Create a new user or update an existing one.

    This requires a valid JWT token which you can get with `odin-auth`, or if it doesnt exist, it will prompt you
    for these
    """
    signal.signal(signal.SIGINT, lambda *args, **kwargs: exit(0))

    parser = argparse.ArgumentParser(description='Create or update an odin user')
    parser.add_argument('--host', default=ODIN_URL, type=str)
    parser.add_argument('--port', default=ODIN_PORT)
    parser.add_argument('--token', help="File where JWT token can reside", default=os.path.expanduser("~/.odin.token"))
    parser.add_argument('--username', '-u', help="Create or update a username")
    parser.add_argument('--password', '-p', help="New or updated password")
    parser.add_argument('--firstname', '-f', help="First name")
    parser.add_argument('--lastname', '-l', help="Last name")
    parser.add_argument('--scheme', choices={'http', 'https'}, default=ODIN_SCHEME, help='The protocol to communicate over')
    args = parser.parse_args()

    if not args.username:
        args.username = prompt('create username: ', is_password=False)
    if not args.password:
        args.password = prompt('new password: ', is_password=True)

    url = f'{args.scheme}://{args.host}:{args.port}'
    jwt_token = get_jwt_token(url, args.token, None, None)
    try:
        create_user_http(url, jwt_token, args.username, args.password, args.firstname, args.lastname)
    except ValueError:
        # Try deleting the token file and start again
        if os.path.exists(args.token):
            os.remove(args.token)
            jwt_token = get_jwt_token(url, args.token, None, None)
            create_user_http(url, jwt_token, args.username, args.password, args.firstname, args.lastname)


if __name__ == '__main__':
    main()
