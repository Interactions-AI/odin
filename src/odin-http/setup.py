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

REQUIRES = ["connexion"]

setup(
    name=NAME,
    version=VERSION,
    description="odin API",
    author_email="mead.baseline@gmail.com",
    url="",
    keywords=["Swagger", "odin API"],
    install_requires=REQUIRES,
    packages=find_packages(),
    package_data={'': ['specs/odin.yaml']},
    include_package_data=True,
    entry_points={
        'console_scripts': ['odin-http=swagger_server.__main__:main']},
    long_description="""\
    This spec defines the odin API, which is used to communicate with the odin server.
    """
)
