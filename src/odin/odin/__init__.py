"""Inject our constructors and define some types
"""
from typing import Dict

import yaml

from baseline.utils import get_console_logger
from odin.version import __version__

LOGGER = get_console_logger('odin', env_key='ODIN_LOG_LEVEL')

Metrics = Dict[str, float]
Path = str

ODIN_LOGO = r"""  ____  _____ _____ _   _
 / __ \|  __ \_   _| \ | |
| |  | | |  | || | |  \| |
| |  | | |  | || | | . ` |
| |__| | |__| || |_| |\  |
 \____/|_____/_____|_| \_|
"""
