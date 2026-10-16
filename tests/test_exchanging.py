"""Overture messages arriving through a keripy host's parser (spec §4.3; tick 2z4c)."""

import pytest
from keri.core import eventing
from keri.core.parsing import Parser
from keri.kering import Kinds, Vrsn_2_0
from keri.peer import exchanging as keri_exchanging

from overture import errors, messages, overtures, wire
from overture.engine import Agent
from overture.exchanging import Exchanger
from overture.requester import Requester, admitted
from overture.store import Store

from conftest import party
from test_engine import REVOKE, CRED, Clock, Script, issue


@pytest.fixture
def host(parties, tmp_path):
    cm, hby, hab = party("host", b"host-agent-salt0")
    clock = Clock()
    store = Store(tmp_path / "host.sqlite")
    agent = Agent(hab, parties["principal"].pre, store, Script(), clock=clock)
    exc = Exchanger(hby, [], agent)
    psr = Parser(kvy=hby.kvy, rvy=hby.rvy, exc=exc, framed=True, version=Vrsn_2_0)
    r = Requester(parties["requester"], parties["principal"].pre)
    r.learn(bytes(hab.replay()))
    yield dict(exc=exc, psr=psr, eng=agent, r=r, clock=clock, hab=hab, **parties)
    agent.close()
    store.close()
    cm.__exit__(None, None, None)


def test_a_batch_through_the_hosts_parser_is_admitted_and_its_receipt_kept(host):
    o = issue()
    host["psr"].parse(ims=bytearray(host["r"].batch([o], stamp=host["clock"].stamp())))
    ((requester, streams),) = host["exc"].answers
    assert requester == host["requester"].pre
    assert o["d"] in admitted(host["r"].read(b"".join(streams)))


def test_a_passed_on_original_keeps_its_nests(host):
    """keripy hands nests only to /multisig, /ipex and /fwd; Overture needs them too."""
    s = host["stranger"]
    original = messages.batch(s, host["requester"].pre, [issue()], stamp=host["clock"].stamp(-60))
    orig = wire.parse(bytes(original))[0]
    o = overtures.make(REVOKE, {"credential": CRED}, triggeredBy={
        "said": orig.a["overtures"][0]["d"], "exn": orig.said})
    stream = bytes(s.replay()) + host["r"].batch([o], nests=[original], stamp=host["clock"].stamp())
    host["psr"].parse(ims=bytearray(stream))
    ((_, streams),) = host["exc"].answers
    assert o["d"] in admitted(host["r"].read(b"".join(streams)))


def test_a_refused_message_leaves_no_answer(host, monkeypatch):
    refused = []
    monkeypatch.setattr(host["eng"], "receive_parsed",
                        lambda found, real=host["eng"].receive_parsed: refused.append(
                            real(found)) or refused[-1])
    stale = host["r"].batch([issue()], stamp=host["clock"].stamp(-3600))
    host["psr"].parse(ims=bytearray(stale))
    assert not host["exc"].answers
    assert refused[0].refusal.code is errors.NOT_FRESH


def test_other_routes_go_to_keripys_exchanger(host, monkeypatch):
    seen = []
    monkeypatch.setattr(keri_exchanging.Exchanger, "processEvent",
                        lambda self, serder, **kwa: seen.append(serder.ked["r"]))
    serder = eventing.exchange(sender=host["requester"].pre, receiver=host["hab"].pre,
                               route="/challenge/response", attributes={"words": ["a"]},
                               pvrsn=Vrsn_2_0, kind=Kinds.json)
    stream = host["r"].kel() + bytes(host["requester"].endorse(serder=serder, nested=True,
                                                               gvrsn=Vrsn_2_0))
    host["psr"].parse(ims=bytearray(stream))
    assert seen == ["/challenge/response"] and not host["exc"].answers
