"""Inject our constructors and define some types
"""
from typing import Dict

import yaml

from baseline.utils import get_console_logger
from odin.version import __version__

LOGGER = get_console_logger('odin', env_key='ODIN_LOG_LEVEL')

Metrics = Dict[str, float]
Path = str


class APIField:
    """Keys that we use when communicating between server and clients."""

    STATUS = 'status'
    RESPONSE = 'response'
    COMMAND = 'command'
    REQUEST = 'request'


class APIStatus:
    """Status codes used between the server and client."""

    OK = 'OK'
    ERROR = 'ERROR'
    END = 'END'


ODIN_LOGO = r"""  ____  _____ _____ _   _
 / __ \|  __ \_   _| \ | |
| |  | | |  | || | |  \| |
| |  | | |  | || | | . ` |
| |__| | |__| || |_| |\  |
 \____/|_____/_____|_| \_|
"""
