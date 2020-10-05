import os
import re
from setuptools import setup, find_packages


def get_version(project_name):
    regex = re.compile(r"""^__version__ = ["'](\d+\.\d+\.\d+-?(?:a|b|rc|dev|alpha)?\.?(?:\d)*?)['"]$""")
    with open(f"{project_name}/version.py") as f:
        for line in f:
            m = regex.match(line.rstrip("\n"))
            if m is not None:
                return m.groups(1)[0]


class About(object):
    NAME = 'odin'
    AUTHOR = 'Interactions, LLC'
    VERSION = get_version(NAME)
    EMAIL = f"{NAME}@interactions.com"


setup(
    name=f"{About.NAME}-ml",
    version=About.VERSION,
    packages=find_packages(),
    install_requires=[
        'numpy',
        'pyyaml>=5.1',
        'websockets',
        'kubernetes',
        'shortid',
        'GitPython',
        'pymongo',
        'SQLAlchemy',
        'psycopg2-binary',
        'ruamel.yaml',
        'cachetools',
        'prompt_toolkit >= 2.0.0',
        'requests-async',
        'requests',
        'pandas',
        'mead-baseline >= 2.0.1',
    ],
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'odin-auth = odin.client.authenticate:main',
            'odin-user = odin.client.user:main',
            'odin-chores = odin.chores:main',
            'odin-cleanup = odin.client.cleanup:main',
            'odin-select-model = odin.model.selector:main',
            'odin-generate = odin.client.generate:main',
            'odin-logs = odin.client.logs:main',
            'odin-events = odin.client.events:main',
            'odin-run = odin.client.run:main',
            'odin-serve = odin.serve:main',
            'odin-status = odin.client.status:main',
            'odin-data = odin.client.data:main',
            'odin-show = odin.client.show:main',
            'odin-template = odin.template:main',
            'odin-ping = odin.client.ping:main',
            'odin-push = odin.client.push:main',
            'odin-create = odin.client.create:main',
            'odin-gpus = odin.client.gpus:main',
            'yaml2json = odin.utils.yaml:main',
            'json2yaml = odin.utils.yaml:json_main',
        ]
    },
)
