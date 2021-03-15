"""Auth utils"""
import os
import requests
from prompt_toolkit import prompt
from baseline.utils import str_file
from odin import LOGGER


@str_file(token_file='r')
def _read_jwt_token_from_file(token_file):
    return token_file.read()


def _authenticate(url, username, passwd):
    response = None
    url = f'{url}/v1/auth'
    try:
        response = requests.post(url, data={'username': username, 'password': passwd})
    except Exception as ex:
        try:

            response = requests.post(url, json={'username': username, 'password': passwd})
            results = response.json()
            return results['message']
        except Exception as ex:
            LOGGER.error(url)
            if response:
                LOGGER.error(response.status_code)

            raise ex


@str_file(token_file='w')
def _write_jwt_file(token_file, token):
    token_file.write(token)


def get_jwt_token(url: str, token_file: str = None, username: str = None, passwd: str = None) -> str:
    """Get a JWT token to send to the server

    1. If user and passwd are given, authenticate, and save to `token_file` if not None
    2. If user and passwd are not both given but there is a `token_file`, try and use that (could file)
    3. If no user or passwd and no `token_file`, prompt for user/passwd and authenticate

    :param url: The server to authenticate to
    :param token_file: An optional path to a file containing a JWT token
    :param username: An optional username
    :param passwd: An optional passwd
    :return: A JWT token we can send
    """

    if username and passwd:
        token = _authenticate(url, username, passwd)
        _write_jwt_file(token_file, token)
        return token

    if os.path.isfile(token_file):
        token = _read_jwt_token_from_file(token_file)
        return token

    if not username:
        username = prompt('odin username: ', is_password=False)
    if not passwd:
        passwd = prompt('odin password: ', is_password=True)

    token = _authenticate(url, username, passwd)
    _write_jwt_file(token_file, token)
    return token
