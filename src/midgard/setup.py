# coding: utf-8

import sys
from setuptools import setup, find_packages

NAME = "midgard-server"
VERSION = "1.0.0"
# To install the library, run the following
#
# python setup.py install
#
# prerequisite: setuptools
# http://pypi.python.org/pypi/setuptools

REQUIRES = ["connexion", "pynvml"]

setup(
    name=NAME,
    version=VERSION,
    description="midgard API",
    author_email="mead.baseline@gmail.com",
    url="",
    keywords=["Swagger", "midgard API"],
    install_requires=REQUIRES,
    packages=find_packages(),
    package_data={'': ['swagger/swagger.yaml']},
    include_package_data=True,
    entry_points={
        'console_scripts': ['swagger_server=midgard.server.__main__:main']},
    long_description="""\
    This spec defines the midgard API, which is a daemonset used to communicate hardware resource info
    """
)
