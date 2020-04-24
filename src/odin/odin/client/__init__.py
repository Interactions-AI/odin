"""Client code specific constants."""
import os

ODIN_URL = os.environ.get('ODIN_URL', 'localhost')
ODIN_PORT = os.environ.get('ODIN_PORT', 9003)


def encode_path(path: str) -> str:
    """Encode a path from `/` to `__`

    :param path: A path to encode
    :return: An encoded vector
    """
    vec = []
    while path:
        head, tail = os.path.split(path)
        vec.append(tail)
        path = head
    return '__'.join(filter(lambda x: x, vec[::-1]))
