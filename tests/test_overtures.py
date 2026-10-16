"""Overture objects and their SAIDs (spec §5.1, §6.2; this.i 48tfl3xj)."""

import json

import pytest
from keri.core.coring import Saider

from overture import overtures, schemas

ACTION = "EHw9ruBZDJ6mlLw5sJFcOfqQqVzHJerbenb34rUG70dF"
AID = "DKxy2sgzfplyr-tgwIxS19f2OchFHtLwPWD3v4oYimBx"
NONCE = "0AB3abcdefghijklmnopqrst"


def test_make_fills_d_with_the_said_of_the_object():
    o = overtures.make(ACTION, {"issuee": AID}, u=NONCE)
    assert list(o)[:4] == ["d", "u", "action", "params"]
    dummy = dict(o, d="#" * 44)
    ser = json.dumps(dummy, separators=(",", ":"), ensure_ascii=False).encode()
    from keri.core.coring import Diger
    assert o["d"] == Diger(ser=ser).qb64


def test_make_includes_only_given_optional_fields_in_spec_order():
    o = overtures.make(ACTION, {}, u=NONCE, purpose="why", prereqs=["E" + "A" * 43],
                       evidence=["E" + "B" * 43])
    assert list(o) == ["d", "u", "action", "params", "prereqs", "purpose", "evidence"]


def test_make_draws_a_fresh_nonce_when_none_is_given():
    a = overtures.make(ACTION, {})
    b = overtures.make(ACTION, {})
    assert a["u"] != b["u"] and a["d"] != b["d"]
    assert a["u"].startswith("0A") and len(a["u"]) == 24


def test_made_overtures_pass_the_shape_check():
    o = overtures.make(ACTION, {}, preconditions={"signer": "principal"},
                       triggeredBy={"said": "E" + "A" * 43, "exn": "E" + "B" * 43})
    assert schemas.errors("batch", {"version": "1.0", "overtures": [o]}) == []


def test_verify_accepts_a_made_overture():
    assert overtures.verify(overtures.make(ACTION, {}))


def test_verify_refuses_any_change():
    o = overtures.make(ACTION, {"issuee": AID})
    assert not overtures.verify(dict(o, params={"issuee": AID, "x": 1}))


def test_verify_refuses_reordered_fields():
    o = overtures.make(ACTION, {}, purpose="why")
    reordered = {k: o[k] for k in reversed(list(o))}
    assert not overtures.verify(reordered)


@pytest.mark.parametrize("bad", [{}, {"d": ""}, {"d": "not qb64"}, {"d": 5}])
def test_verify_refuses_missing_or_malformed_d(bad):
    assert not overtures.verify(dict(bad, u=NONCE))


def test_identical_asks_are_different_overtures():
    assert overtures.make(ACTION, {})["d"] != overtures.make(ACTION, {})["d"]


def test_make_refuses_a_field_overtures_do_not_have():
    with pytest.raises(TypeError, match="no field 'colour'"):
        overtures.make(ACTION, {}, colour="red")
