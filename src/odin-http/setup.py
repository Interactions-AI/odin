# coding: utf-8

import sys
from setuptools import setup, find_packages

NAME = "odin-http"
VERSION = "1.0.0"
# To install the library, run the following
#
# python setup.py install
#
# prerequisite: setuptools
# http://pypi.python.org/pypi/setuptools

REQUIRES = [
    "fastapi",
    "fastapi_camelcase",
    "uvicorn[standard]",
    "websockets",
    "numpy",
    "pyyaml",
    "GitPython",
    "requests",
    "kubernetes",
    "requests-async",
    "python-jose",
    "bcrypt",
    "SQLAlchemy",
    "psycopg2-binary",
]


setup(
    name=NAME,
    version=VERSION,
    description="odin API",
    author_email="odin@interactions.com",
    url="",
    keywords=["FastAPI", "odin API"],
    install_requires=REQUIRES,
    packages=find_packages(),
    long_description="""\
    odin HTTP API which is used to communicate with the odin server.
    """
)
