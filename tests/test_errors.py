import re

import pytest

from overture import errors

GRAMMAR = re.compile(r"^[ew]\.(input|id|grant|feature|proof|party|state|env|self|rule)"
                     r"(\.[a-z0-9]+(-[a-z0-9]+)*)+\.[fr]$")


def codes():
    return [v for v in vars(errors).values() if isinstance(v, errors.Code)]


@pytest.mark.parametrize("code", codes(), ids=lambda c: c.code)
def test_every_code_follows_the_grammar_and_has_a_sentence(code):
    assert GRAMMAR.match(code.code)
    assert code.title[0].isupper() and code.title.endswith(".")


def test_codes_are_unique():
    assert len({c.code for c in codes()}) == len(codes())


def test_a_refusal_carries_its_code_and_detail():
    r = errors.Refusal(errors.SHAPE, "At $.x: bad.")
    assert r.code is errors.SHAPE and str(r) == "e.input.format.shape.f: At $.x: bad."
    assert errors.Refusal(errors.SHAPE).detail == errors.SHAPE.title


def test_matching_by_prefix_or_exactly():
    assert errors.matches("e.proof.", "e.proof.message.sig.f")
    assert not errors.matches("e.proof.", "e.input.format.shape.f")
    assert errors.matches("e.input.format.shape.f", "e.input.format.shape.f")
    assert not errors.matches("e.input.format.shape", "e.input.format.shape.f")
