"""Building and parsing Overture messages (spec §4, §5)."""

import pytest
from keri.core.eventing import Kevery

from overture import messages, overtures, wire

ACTION = "EHw9ruBZDJ6mlLw5sJFcOfqQqVzHJerbenb34rUG70dF"
T1 = "2026-10-15T17:05:00.000000+00:00"


def receive(hab, stream):
    kvy = Kevery(db=hab.db, lax=False, local=False)
    return wire.parse(stream, kvy=kvy), kvy


def test_a_batch_is_a_v2_exn_under_its_route(parties):
    r, a, p = parties["requester"], parties["agent"], parties["principal"]
    o = overtures.make(ACTION, {})
    stream = messages.batch(r, p.pre, [o], stamp=T1)
    assert bytes(stream[:2]) == b"-B"
    (msg,), _ = receive(a, bytes(r.replay()) + bytes(stream))
    assert msg.route == "/overture/batch"
    assert msg.serder.pvrsn.major == 2
    assert msg.sender == r.pre and msg.receiver == p.pre
    assert msg.a == {"version": "1.0", "overtures": [o]}
    ked = msg.serder.ked
    assert ked["x"] == "" and ked["p"] == "" and ked["q"] == {} and ked["dt"] == T1


def test_wait_until_is_carried_when_given(parties):
    r, p = parties["requester"], parties["principal"]
    (msg,), _ = receive(parties["agent"], bytes(r.replay()) + bytes(
        messages.batch(r, p.pre, [overtures.make(ACTION, {})], waitUntil=T1)))
    assert msg.a["waitUntil"] == T1


def test_each_route_builds(parties):
    r, a, p = parties["requester"], parties["agent"], parties["principal"]
    said = overtures.make(ACTION, {})["d"]
    built = [
        messages.poll(r, p.pre, [said], waitUntil=T1),
        messages.abort(r, p.pre, [said]),
        messages.receipt(a, r.pre, [{"meaning": "admitted", "said": said, "keptUntil": T1}],
                         nextPoll=T1),
        messages.status(a, r.pre, [{"said": said, "status": "pending"}], nextPoll=T1),
    ]
    stream = bytes(r.replay()) + bytes(a.replay()) + b"".join(bytes(b) for b in built)
    got, _ = receive(parties["stranger"], stream)
    assert [m.route for m in got] == ["/overture/poll", "/overture/abort",
                                      "/overture/receipt", "/overture/status"]
    assert got[0].a == {"version": "1.0", "saids": [said], "waitUntil": T1}
    assert got[2].a["nextPoll"] == T1 and got[3].a["nextPoll"] == T1


def test_an_attached_message_arrives_as_a_nest_with_its_signatures(parties):
    r, a, p, s = (parties[k] for k in ("requester", "agent", "principal", "stranger"))
    original = messages.batch(s, p.pre, [overtures.make(ACTION, {})], stamp=T1)
    (orig,), _ = receive(a, bytes(s.replay()) + bytes(original))
    hop = overtures.make(ACTION, {}, triggeredBy={"said": orig.a["overtures"][0]["d"],
                                                 "exn": orig.said})
    stream = messages.batch(r, p.pre, [hop], nests=[original])
    (msg,), kvy = receive(a, bytes(s.replay()) + bytes(r.replay()) + bytes(stream))
    assert [n.said for n in msg.nests] == [orig.said]
    assert msg.nests[0].tsgs and msg.nests[0].a == orig.a


def test_parse_skips_non_exn_messages_and_reports_none_for_garbage(parties):
    r = parties["requester"]
    got, kvy = receive(parties["agent"], bytes(r.replay()))
    assert got == [] and r.pre in kvy.kevers


def test_a_non_transferable_sender_signs_with_a_cigar(parties):
    e, p = parties["ephemeral"], parties["principal"]
    (msg,), _ = receive(parties["agent"], bytes(
        messages.batch(e, p.pre, [overtures.make(ACTION, {})])))
    assert msg.cigars and not msg.tsgs
