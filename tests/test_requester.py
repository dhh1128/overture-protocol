"""The requester's checks on what an agent answers."""

import pytest

from overture import errors, messages, requester
from overture.requester import Requester

SAID = "EAbcdefghijklmnopqrstuvwxyz0123456789_-ABCDE"
T = "2026-10-15T17:05:00.000000+00:00"


@pytest.fixture
def r(parties):
    req = Requester(parties["requester"], parties["principal"].pre)
    for k in ("agent", "stranger"):
        req.learn(bytes(parties[k].replay()))
    return req


def report(hab, to, status="pending"):
    return bytes(messages.status(hab, to, [{"said": SAID, "status": status}]))


def test_a_signed_report_from_an_agent_is_read(r, parties):
    msgs = r.read(report(parties["agent"], parties["requester"].pre),
                  agents={parties["agent"].pre})
    assert requester.statuses(msgs)[SAID]["status"] == "pending"
    assert requester.reports(msgs) == [msgs[0].said]
    assert requester.admitted(msgs) == {}


def test_key_events_in_an_answer_are_skipped(r, parties):
    stream = bytes(parties["agent"].replay()) + report(parties["agent"], parties["requester"].pre)
    assert len(r.read(stream)) == 1


def test_a_report_from_someone_other_than_the_agents_is_refused(r, parties):
    with pytest.raises(errors.Refusal) as e:
        r.read(report(parties["stranger"], parties["requester"].pre), agents={parties["agent"].pre})
    assert e.value.code is errors.SIGNATURE_INVALID


def test_a_report_addressed_to_another_requester_is_refused(r, parties):
    with pytest.raises(errors.Refusal) as e:
        r.read(report(parties["agent"], parties["stranger"].pre))
    assert e.value.code is errors.WRONG_PRINCIPAL


def test_a_misshapen_report_is_refused(r, parties):
    with pytest.raises(errors.Refusal) as e:
        r.read(report(parties["agent"], parties["requester"].pre, status="agreed"))
    assert e.value.code is errors.SHAPE


def test_only_admitted_receipts_are_collected(r, parties):
    stream = bytes(messages.receipt(parties["agent"], parties["requester"].pre, [
        {"meaning": "admitted", "said": SAID, "keptUntil": T},
        {"meaning": "seen", "said": "E" + "B" * 43}], stamp=T))
    msgs = r.read(stream)
    assert set(requester.admitted(msgs)) == {SAID}
    assert requester.admitted(msgs)[SAID]["admittedAt"] == T
    assert requester.statuses(msgs) == {}


def test_an_exn_outside_overture_is_skipped(r, parties):
    from keri.core import eventing
    from keri.kering import Kinds, Vrsn_2_0
    serder = eventing.exchange(sender=parties["agent"].pre, receiver=parties["requester"].pre,
                               route="/other", attributes={}, pvrsn=Vrsn_2_0, kind=Kinds.json)
    other = bytes(parties["agent"].endorse(serder=serder, nested=True, gvrsn=Vrsn_2_0))
    assert r.read(other + report(parties["agent"], parties["requester"].pre))[0].route == "/overture/status"


def delegate(principal, raw, traits):
    """A delegate of ``principal`` with inception ``traits``, as KELs: keripy's Hab cannot
    make one with the DID trait, so its inception is built and signed here."""
    from keri.core import eventing
    from keri.core.coring import Diger, Number
    from keri.core.signing import Salter
    from keri.core.structing import SealSource
    salter = Salter(raw=raw)
    now, nxt = salter.signers(count=2, path="delegate", temp=True)
    dip = eventing.delcept(keys=[now.verfer.qb64], delpre=principal.pre,
                           ndigs=[Diger(ser=nxt.verfer.qb64b).qb64], cnfg=traits)
    principal.interact(data=[dict(i=dip.pre, s="0", d=dip.said)])
    anchor = principal.kever.serder
    stream = bytes(eventing.messagize(dip, sigers=[now.sign(dip.raw, index=0)],
                                      bonds=[SealSource(s=Number(num=anchor.sn),
                                                        d=Diger(qb64=anchor.said))]))
    return dip.pre, bytes(principal.replay()) + stream


@pytest.mark.parametrize("traits,expected", [(["DID"], True), ([], False)])
def test_a_delegate_signs_as_the_principal_only_with_the_did_trait(r, parties, traits, expected):
    aid, kels = delegate(parties["principal"], b"delegate-salt-00", traits)
    r.learn(kels)
    assert r.signs_as_principal(aid) is expected


def test_the_principal_signs_as_itself_and_others_do_not(r, parties):
    assert r.signs_as_principal(parties["principal"].pre)
    assert not r.signs_as_principal(parties["stranger"].pre)
    assert not r.signs_as_principal(SAID)
