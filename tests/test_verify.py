"""Signatures judged against the signer's latest establishment event (spec §4.4; this.i
35wllumn, 3j0mdxh4)."""

import datetime

import pytest
from keri.core.eventing import Kevery

from overture import errors, messages, overtures, verify, wire

ACTION = "EHw9ruBZDJ6mlLw5sJFcOfqQqVzHJerbenb34rUG70dF"


def receive(hab, stream, kvy=None):
    kvy = kvy or Kevery(db=hab.db, lax=False, local=False)
    return wire.parse(stream, kvy=kvy), kvy


def a_batch(sender, to):
    return messages.batch(sender, to.pre, [overtures.make(ACTION, {})])


def refused(code, fn, *args, **kwa):
    with pytest.raises(errors.Refusal) as info:
        fn(*args, **kwa)
    assert info.value.code is code
    return info.value


def test_a_current_signature_verifies(parties):
    r, a, p = parties["requester"], parties["agent"], parties["principal"]
    (msg,), kvy = receive(a, bytes(r.replay()) + bytes(a_batch(r, p)))
    verify.signatures(msg, kvy)


def test_a_signature_over_other_content_is_refused(parties):
    r, a, p = parties["requester"], parties["agent"], parties["principal"]
    (one, two), kvy = receive(a, bytes(r.replay()) + bytes(a_batch(r, p)) + bytes(a_batch(r, p)))
    forged = wire.Message(serder=two.serder, tsgs=one.tsgs)
    refused(errors.SIGNATURE_INVALID, verify.signatures, forged, kvy)


def test_no_signature_from_the_sender_is_refused(parties):
    r, a, p, s = (parties[k] for k in ("requester", "agent", "principal", "stranger"))
    (mine,), kvy = receive(a, bytes(r.replay()) + bytes(a_batch(r, p)))
    (theirs,), _ = receive(a, bytes(s.replay()) + bytes(a_batch(s, p)), kvy)
    refused(errors.SIGNATURE_INVALID, verify.signatures,
            wire.Message(serder=mine.serder, tsgs=theirs.tsgs), kvy)
    refused(errors.SIGNATURE_INVALID, verify.signatures, wire.Message(serder=mine.serder), kvy)


def test_an_unknown_signer_needs_its_key_state(parties):
    r, a, p = parties["requester"], parties["agent"], parties["principal"]
    (msg,), kvy = receive(a, bytes(r.replay()) + bytes(a_batch(r, p)))
    empty = Kevery(db=parties["stranger"].db, lax=False, local=False)
    e = refused(errors.KEY_STATE_MISSING, verify.signatures, msg, empty)
    assert e.code.code.endswith(".r")


def test_a_signer_that_rotated_since_signing_is_refused(parties):
    r, a, p = parties["requester"], parties["agent"], parties["principal"]
    old = bytes(a_batch(r, p))
    r.rotate()
    (msg,), kvy = receive(a, bytes(r.replay()) + old)
    refused(errors.KEYS_ROTATED, verify.signatures, msg, kvy)


def test_a_signature_under_keys_newer_than_known_needs_key_state(parties):
    r, a, p = parties["requester"], parties["agent"], parties["principal"]
    kvy = Kevery(db=a.db, lax=False, local=False)
    receive(a, bytes(r.replay()), kvy)
    r.rotate()
    (msg,), _ = receive(a, bytes(a_batch(r, p)), kvy)
    refused(errors.KEY_STATE_MISSING, verify.signatures, msg, kvy)


def test_a_bad_index_or_unmet_threshold_is_refused(parties):
    r, a, p = parties["requester"], parties["agent"], parties["principal"]
    (msg,), kvy = receive(a, bytes(r.replay()) + bytes(a_batch(r, p)))
    prefixer, number, diger, sigers = msg.tsgs[0]
    refused(errors.SIGNATURE_INVALID, verify.signatures,
            wire.Message(serder=msg.serder, tsgs=[(prefixer, number, diger, [])]), kvy)
    from keri.core.indexing import Siger
    moved = Siger(raw=sigers[0].raw, code=sigers[0].code, index=5)
    refused(errors.SIGNATURE_INVALID, verify.signatures,
            wire.Message(serder=msg.serder, tsgs=[(prefixer, number, diger, [moved])]), kvy)


def test_a_non_transferable_sender_verifies_by_its_prefix(parties):
    e, a, p = parties["ephemeral"], parties["agent"], parties["principal"]
    (msg,), kvy = receive(a, bytes(a_batch(e, p)))
    verify.signatures(msg, kvy)


def test_a_cigar_from_another_key_is_refused(parties):
    e, a, p, s = (parties[k] for k in ("ephemeral", "agent", "principal", "stranger"))
    (msg,), kvy = receive(a, bytes(a_batch(e, p)))
    other = s.sign(ser=msg.serder.raw, indexed=False)
    refused(errors.SIGNATURE_INVALID, verify.signatures,
            wire.Message(serder=msg.serder, cigars=other), kvy)
    tampered = msg.cigars[0]
    (two,), _ = receive(a, bytes(a_batch(e, p)), kvy)
    refused(errors.SIGNATURE_INVALID, verify.signatures,
            wire.Message(serder=two.serder, cigars=[tampered]), kvy)


def test_a_transferable_sender_may_not_sign_with_a_cigar(parties):
    r, a, p = parties["requester"], parties["agent"], parties["principal"]
    (msg,), kvy = receive(a, bytes(r.replay()) + bytes(a_batch(r, p)))
    cigars = r.sign(ser=msg.serder.raw, indexed=False)
    refused(errors.SIGNATURE_INVALID, verify.signatures,
            wire.Message(serder=msg.serder, cigars=cigars), kvy)


# --- freshness ----------------------------------------------------------------

NOW = datetime.datetime(2026, 10, 15, 17, 5, tzinfo=datetime.UTC)
WINDOW = datetime.timedelta(seconds=300)


@pytest.mark.parametrize("dt", ["2026-10-15T17:05:00.000000+00:00",
                                "2026-10-15T17:00:00.000000+00:00",
                                "2026-10-15T17:10:00.000000+00:00",
                                "2026-10-15T19:05:00.000000+02:00"])
def test_a_time_inside_the_window_is_fresh(dt):
    verify.freshness(dt, NOW, WINDOW)


@pytest.mark.parametrize("dt", ["2026-10-15T16:59:59.999999+00:00",
                                "2026-10-15T17:10:00.000001+00:00"])
def test_a_time_outside_the_window_is_refused(dt):
    refused(errors.NOT_FRESH, verify.freshness, dt, NOW, WINDOW)


@pytest.mark.parametrize("dt", ["", "soon", "2026-10-15T17:05:00", 7])
def test_an_unreadable_time_is_refused(dt):
    refused(errors.MALFORMED, verify.freshness, dt, NOW, WINDOW)


def test_parse_time_reads_keri_dt():
    assert verify.parse_time("2026-10-15T17:05:00.000000+00:00") == NOW


def test_a_repeated_signature_does_not_count_twice_toward_a_threshold(parties):
    from keri.app import habbing
    from keri.core.signing import Salter
    a, p = parties["agent"], parties["principal"]
    with habbing.openHby(name="multi", temp=True, salt=Salter(raw=b"multisig-salt-00").qb64) as hby:
        m = hby.makeHab(name="multi", icount=2, isith="2", ncount=2, nsith="2")
        (msg,), kvy = receive(a, bytes(m.replay()) + bytes(a_batch(m, p)))
        verify.signatures(msg, kvy)
        prefixer, number, diger, sigers = msg.tsgs[0]
        doubled = [sigers[0], sigers[0]]
        e = refused(errors.SIGNATURE_INVALID, verify.signatures,
                    wire.Message(serder=msg.serder, tsgs=[(prefixer, number, diger, doubled)]), kvy)
        assert "repeated" in e.detail
