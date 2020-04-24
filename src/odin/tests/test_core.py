from collections import Counter
from copy import deepcopy
from itertools import chain
import random
import string
from typing import Optional
import pytest
from odin.core import wire_inputs

CHARS = list(chain(string.ascii_letters, string.digits))
if '^' in CHARS:
    CHARS.remove('^')


def rand_str(length: Optional[int] = None, min_: int = 3, max_: int = 10):
    if length is None:
        length = random.randint(min_, max_)
    return ''.join([random.choice(CHARS) for _ in range(length)])


def dummy(a, b, c=12):
    pass


def test_wire_inputs_all_inputs_present():
    inputs = {'a': '^first', 'b': '^second', 'c': '^third'}
    og = deepcopy(inputs)
    results = {'first': rand_str(), 'second': rand_str(), 'third': rand_str(), 'last': rand_str()}
    inputs = wire_inputs(inputs, results, dummy)
    for k, v in inputs.items():
        assert v == results[og[k].replace('^', '')]
    assert inputs != results


def test_wire_inputs_missing_inputs():
    inputs = {'a': '^first', 'b': '^second', 'c': '^third'}
    og = deepcopy(inputs)
    results = {'first': rand_str(), 'last': rand_str()}
    inputs = wire_inputs(inputs, results, dummy)
    for k, v in inputs.items():
        if og[k].replace('^', '') in results:
            assert v == results[og[k].replace('^', '')]
        else:
            assert v is None
    assert inputs != results


def test_wire_inputs_index_lookup():
    inputs = {'a': '^first.second'}
    og = deepcopy(inputs)
    results = {'first': {'second': rand_str()}}
    inputs = wire_inputs(inputs, results, lambda a: None)
    for k, v in inputs.items():
        assert v == results['first']['second']


def test_wire_inputs_missing_param():
    inputs = {}
    results = {'first': 'b'}
    inputs = wire_inputs(inputs, results, dummy)
    assert 'a' in inputs
    assert inputs['a'] is None
    assert 'b' in inputs
    assert inputs['b'] is None
    assert 'c' not in inputs


def test_wire_inputs_supply_default_param():
    inputs = {'c': '^first'}
    results = {'first': rand_str()}
    inputs = wire_inputs(inputs, results, dummy)
    assert 'a' in inputs
    assert inputs['a'] is None
    assert 'b' in inputs
    assert inputs['b'] is None
    assert 'c' in inputs
    assert inputs['c'] == results['first']


def test_wire_inputs_list_of_inputs():
    inputs = {'a': ['^first', '^second', '^third']}
    og = deepcopy(inputs)
    results = {'first': rand_str(), 'second': rand_str(), 'third': rand_str(), 'last': rand_str()}
    inputs = wire_inputs(inputs, results, lambda a: None)
    for k, vs in inputs.items():
        for i in range(len(vs)):
            assert vs[i] == results[og[k][i].replace('^', '')]
    assert inputs != results


def test_wire_inputs_input_pass_through():
    for _ in range(100):
        raw_inputs = {rand_str(): rand_str() for _ in range(random.randint(1, 5))}
        gold_inputs = deepcopy(raw_inputs)
        chore = lambda **kwargs: None
        inputs = wire_inputs(raw_inputs, {}, chore)
        assert inputs == gold_inputs


class RecordingDict(dict):
    def __init__(self, *args, top=True, **kwargs):
        self.requested = Counter()
        super().__init__(*args, **kwargs)
        if top:
            self.sub = RecordingDict(top=False)

    def get(self, key, default=None):
        self.requested[key] += 1
        default = self.sub if isinstance(default, dict) else default
        return super().get(key, default)
