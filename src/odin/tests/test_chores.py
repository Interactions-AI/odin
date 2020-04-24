import yaml
from getpass import getuser

from odin.chores import register_chore, run_chores
from odin.version import __version__


@register_chore('say-hello')
def hello(user) -> bool:
    return 'Hello, {}'.format(user)


@register_chore('say-goodbye')
def goodbye(previous):
    return previous.replace('Hello', 'Goodbye')


@register_chore('noop')
def dummy():
    return "nothing"


@register_chore('get-username')
def get_user():
    return getuser()


YAML_CONFIG = """
chores:
- name: user
  type:
    get-username
- name: hi
  type:
    say-hello
  user: ^user
- name: bye
  type:
    say-goodbye
  previous: ^hi
"""


def test_chores():
    results = run_chores(yaml.load(YAML_CONFIG, Loader=yaml.FullLoader), {})
    print(results)
    assert results['user'] == getuser()
    assert results['hi'] == 'Hello, {}'.format(getuser())
    assert results['bye'] == 'Goodbye, {}'.format(getuser())


@register_chore('get-from-external')
def get_username_and_version(username, version):
    assert username == getuser()
    assert version == __version__


YAML_CONFIG2 = """
chores:
- name: external-test
  type: get-from-external
  username: ^something.username
  version: ^something.version
"""


def test_external():

    user = getuser()
    results = run_chores(
        yaml.load(YAML_CONFIG2, Loader=yaml.FullLoader), {"something": {"version": __version__, "username": user}}
    )
