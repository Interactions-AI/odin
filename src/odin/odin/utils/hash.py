"""Tools to hash files."""

import os
from pathlib import Path
from hashlib import sha1
from itertools import chain
from functools import partial
from typing import List, Union, BinaryIO, Any, Optional
from baseline.utils import str_file, listify
from odin import LOGGER


# There is no hashlib base class so create something for typing.
Hash = Any  # pylint: disable=invalid-name


@str_file(f='rb')
def hash_file(f: Union[str, BinaryIO], hasher: Hash, block_size: int = 1024) -> Hash:
    """Update a hash function with the contents for a file.

    :param f: The file to hash.
    :param hasher: The hash object to use.
    :param block_size: The size of chunks used to read the file in. This
        doesn't effect the output of the hash function.

    :returns: The hash object updated with the file contents.
    """
    for block in iter(partial(f.read, block_size), b''):
        hasher.update(block)
    return hasher


def hash_files(files: Union[str, List[str]], hasher: Optional[Hash] = None, block_size: int = 1024) -> str:
    """Hash a list of files.

    :param files: The list of files to hash.
    :param hasher: The hash object. defaults to sha1.
    :param block_size: The size of chunks used to read the files in.

    :returns: The hexdigest of all the files.
    """
    hasher = hasher if hasher is not None else sha1()
    for f in sorted(expand_dirs(listify(files))):
        hasher = hash_file(f, hasher, block_size)
    return hasher.hexdigest()


def expand_dirs(files: List[str]) -> List[str]:
    """Given a list of files and dirs return a list all files in the dir.

    :param files: The list of files and dirs.

    :returns: The list with dirs expanded into the files contained within them.
    """
    new_files = []
    for f in files:
        f = os.path.expanduser(f)
        if not os.path.exists(f):
            LOGGER.warning("Requested hash of %s but file not found.", f)
            continue
        if os.path.isdir(f):
            new_files.extend(expand_dir(f))
        else:
            new_files.append(f)
    return new_files


def expand_dir(dir_name: str) -> List[str]:
    """Get a list of files inside a directory.

    :param dir_name: The dir to find files in.

    :returns: The list of files.
    """
    return map(str, filter(lambda x: not os.path.isdir(x), Path(dir_name).rglob("*")))


def hash_args(command: Union[str, List[str]], args: List[str]) -> str:
    """Hash the command and arguments of a container.

    :param command: The command that k8s will give the container.
    :param args: The arguments the container receives.
    :returns: The hash of the container args.
    """
    return sha1("".join(chain(listify(command), args)).encode('utf-8')).hexdigest()
