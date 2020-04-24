from unittest.mock import MagicMock
import pytest
from odin.executor import Executor


MAPPING = {
    "^a.b": "first-value",
    "^c": "c-value",
    "^d.r": "dr-vals",
    "^ec": "c",
    "^a.b.c": "a-b-c-value",
    "^z": ".x",
    "^y.x": "b.c",
    "^q": "a",
    "^a.{example}": "a-with-example",
}


@pytest.fixture
def exc():
    e = Executor(None, sched=MagicMock())
    e.extract_outputs = MagicMock(side_effect=lambda x, y: MAPPING[y])
    return e


def test_full_reference(exc):
    reference = "^a.b"
    gold = MAPPING[reference]
    assert exc.rewrite_references(None, reference) == gold


def test_no_reference(exc):
    reference = "missing"
    assert exc.rewrite_references(None, reference) == reference


def test_partial_reference(exc):
    reference = "text-{^c}-text"
    gold = "text-c-value-text"
    assert exc.rewrite_references(None, reference) == gold


def test_multiple_references(exc):
    reference = "text-{^d.r}-more-{^a.b}"
    gold = "text-dr-vals-more-first-value"
    assert exc.rewrite_references(None, reference) == gold


def test_curlies_no_ref(exc):
    reference = "text-{example}-more"
    assert exc.rewrite_references(None, reference) == reference


def test_start_with_ref(exc):
    reference = "{^c}-ex"
    gold = "c-value-ex"
    assert exc.rewrite_references(None, reference) == gold


def test_end_with_ref(exc):
    reference = "ex-{^a.b}"
    gold = "ex-first-value"
    assert exc.rewrite_references(None, reference) == gold


def test_only_sub_ref(exc):
    reference = "{^d.r}"
    gold = "dr-vals"
    assert exc.rewrite_references(None, reference) == gold


def test_sub_reference(exc):
    reference = "text-{^a.b.{^ec}}-example"
    gold = "text-a-b-c-value-example"
    assert exc.rewrite_references(None, reference) == gold


def test_nested_references(exc):
    reference = "example={^a.{^y{^z}}}"
    gold = "example=a-b-c-value"
    assert exc.rewrite_references(None, reference) == gold


def test_multiple_sub_references(exc):
    reference = "example={^{^q}.b.{^ec}}"
    gold = "example=a-b-c-value"
    assert exc.rewrite_references(None, reference) == gold


def test_non_ref_in_sub_ref(exc):
    reference = "example={^a.{example}}"
    gold = "example=a-with-example"
    assert exc.rewrite_references(None, reference) == gold


def test_lone_right_paren(exc):
    reference = "example-}-more"
    assert exc.rewrite_references(None, reference) == reference


def test_lone_left_paren(exc):
    reference = "example={-more"
    assert exc.rewrite_references(None, reference) == reference
