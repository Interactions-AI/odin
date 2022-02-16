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
        'pymongo <= 3.12.0',
        'SQLAlchemy',
        'psycopg2-binary',
        'ruamel.yaml',
        'cachetools',
        'prompt_toolkit >= 2.0.0',
        'requests-async',
        'requests',
        'pandas',
        'mead-baseline >= 2.0.1',
        'mead-xpctl-client',
    ],
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'odin-chores = odin.chores:main',
            'odin-select-model = odin.model.selector:main',
            'odin-serve = odin.serve:main',
            'yaml2json = odin.utils.yaml_utils:main',
            'render-jinja2 = odin.utils.render:main',
            'json2yaml = odin.utils.yaml_utils:json_main',
        ]
    },
)
