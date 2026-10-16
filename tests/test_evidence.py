"""Step 8 verifies attached authority evidence as ordinary ACDCs (spec §6.1; this.i 2s0z8frg)."""

import pytest
from keri.core import eventing
from keri.core.serdering import SerderACDC
from keri.core.signing import Salter
from keri.kering import Vrsn_1_0, Vrsn_2_0
from keri.vdr import eventing as tel

from overture import errors, messages, overtures, wire
from overture.issuing import Issuer, schema
from overture.requester import admitted

from test_engine import REVOKE, CRED, issue, refusal, send, world  # noqa: F401

ROOT = schema("Root", {"name": {"type": "string"}})
LEAF = schema("Leaf", {"role": {"type": "string"}}, required=["role"])


def registry(hab, n=0):
    return Issuer(hab, Salter(raw=n.to_bytes(16, "big")).qb64)


@pytest.fixture
def chain(world):
    """The stranger issues a root credential to the requester, who issues a leaf under it."""
    for s in (ROOT, LEAF):
        world["eng"].learn_schema(s)
    root_issuer = registry(world["stranger"], 1)
    leaf_issuer = registry(world["requester"], 2)
    root = root_issuer.issue(ROOT, {"name": "x"}, recipient=world["requester"].pre)
    leaf = leaf_issuer.issue(LEAF, {"role": "clerk"}, recipient=world["agent"].pre,
                             edges={"auth": {"n": root.said, "s": ROOT.said, "o": "I2I"}})
    return dict(world=world, root_issuer=root_issuer, leaf_issuer=leaf_issuer, root=root, leaf=leaf)


def batch(c, *, evidence, nests, before=None):
    w = c["world"]
    o = overtures.make(REVOKE, {"credential": CRED}, **({"evidence": evidence} if evidence else {}))
    head = c["root_issuer"].stream() + c["leaf_issuer"].stream() if before is None else before
    return o, head + w["r"].batch([o], nests=nests, stamp=w["clock"].stamp())


def nests(c, *creds):
    by = {c["root"].said: c["root_issuer"], c["leaf"].said: c["leaf_issuer"]}
    return [by[x.said].nest(x) for x in creds]


def test_a_verified_chain_is_admitted(chain):
    c = chain
    o, stream = batch(c, evidence=[c["leaf"].said], nests=nests(c, c["leaf"], c["root"]))
    _, msgs = send(c["world"], stream)
    assert o["d"] in admitted(msgs)


def test_an_evidence_said_without_its_acdc_is_malformed(chain):
    c = chain
    _, stream = batch(c, evidence=[c["leaf"].said], nests=[])
    assert refusal(c["world"], stream) is errors.EVIDENCE_MISSING


def test_a_chain_missing_a_link_is_malformed(chain):
    c = chain
    _, stream = batch(c, evidence=[c["leaf"].said], nests=nests(c, c["leaf"]))
    assert refusal(c["world"], stream) is errors.EVIDENCE_MISSING


def test_a_revoked_leaf_is_malformed(chain):
    c = chain
    c["leaf_issuer"].revoke(c["leaf"])
    _, stream = batch(c, evidence=[c["leaf"].said], nests=nests(c, c["leaf"], c["root"]))
    assert refusal(c["world"], stream) is errors.EVIDENCE_REVOKED


def test_a_revoked_link_is_malformed(chain):
    c = chain
    c["root_issuer"].revoke(c["root"])
    _, stream = batch(c, evidence=[c["leaf"].said], nests=nests(c, c["leaf"], c["root"]))
    assert refusal(c["world"], stream) is errors.EVIDENCE_REVOKED


def test_evidence_whose_tel_was_not_sent_is_refused_for_retry(chain):
    c = chain
    w = c["world"]
    _, stream = batch(c, evidence=[c["root"].said], nests=nests(c, c["root"]),
                      before=bytes(w["stranger"].replay()))
    code = refusal(w, stream)
    assert code is errors.EVIDENCE_STATE_MISSING and code.code.endswith(".r")


def test_evidence_issued_after_the_tel_sent_is_refused_for_retry(chain):
    c = chain
    w = c["world"]
    w["eng"].receive(c["root_issuer"].stream())
    late = c["root_issuer"].issue(ROOT, {"name": "late"})
    _, stream = batch(c, evidence=[late.said], nests=[c["root_issuer"].nest(late)], before=b"")
    assert refusal(w, stream) is errors.EVIDENCE_STATE_MISSING


def test_evidence_whose_schema_the_agent_lacks_is_refused_for_retry(chain):
    c = chain
    other = schema("Unknown to the agent")
    cred = c["root_issuer"].issue(other, {})
    _, stream = batch(c, evidence=[cred.said], nests=[c["root_issuer"].nest(cred)])
    assert refusal(c["world"], stream) is errors.EVIDENCE_STATE_MISSING


def test_evidence_that_fails_its_schema_is_malformed(chain):
    c = chain
    cred = c["root_issuer"].issue(LEAF, {"name": "no role"})
    _, stream = batch(c, evidence=[cred.said], nests=[c["root_issuer"].nest(cred)])
    assert refusal(c["world"], stream) is errors.EVIDENCE_INVALID


def test_a_credential_in_another_aids_registry_is_malformed(chain):
    """keripy's Verifier accepts this; the engine checks issuer against registry controller."""
    c = chain
    w = c["world"]
    forged = registry(w["stranger"], 3)
    cred = forged.issue(ROOT, {"name": "x"})
    cred_sad = dict(cred.sad, i=w["requester"].pre)
    fake = SerderACDC(sad=cred_sad, makify=True)
    iss = tel.issue(vcdig=fake.said, regk=forged.registry, version=Vrsn_1_0)
    forged.anchors[fake.said] = forged._anchor(iss, fake.said, 0)
    _, stream = batch(c, evidence=[fake.said], nests=[forged.nest(fake)],
                      before=bytes(w["requester"].replay()) + forged.stream())
    assert refusal(w, stream) is errors.EVIDENCE_INVALID


def test_an_edge_whose_operator_does_not_hold_is_malformed(chain):
    """I2I needs the far node's issuee to be the near node's issuer."""
    c = chain
    root = c["root_issuer"].issue(ROOT, {"name": "x"}, recipient=c["world"]["agent"].pre)
    leaf = c["leaf_issuer"].issue(LEAF, {"role": "r"},
                                  edges={"auth": {"n": root.said, "s": ROOT.said, "o": "I2I"}})
    _, stream = batch(c, evidence=[leaf.said],
                      nests=[c["leaf_issuer"].nest(leaf), c["root_issuer"].nest(root)])
    assert refusal(c["world"], stream) is errors.EVIDENCE_INVALID


def test_edges_given_as_a_list_are_followed(chain):
    c = chain
    leaf = c["leaf_issuer"].issue(LEAF, {"role": "r"},
                                  edges=[{"auth": {"n": c["root"].said, "o": "I2I"}}])
    o, stream = batch(c, evidence=[leaf.said],
                      nests=[c["leaf_issuer"].nest(leaf), c["root_issuer"].nest(c["root"])])
    _, msgs = send(c["world"], stream)
    assert o["d"] in admitted(msgs)


def test_a_malformed_edge_is_malformed(chain):
    c = chain
    leaf = c["leaf_issuer"].issue(LEAF, {"role": "r"}, edges={"auth": "not an edge"})
    _, stream = batch(c, evidence=[leaf.said], nests=[c["leaf_issuer"].nest(leaf)])
    assert refusal(c["world"], stream) is errors.EVIDENCE_INVALID


def test_evidence_without_a_source_seal_is_malformed(chain):
    c = chain
    cigars = c["world"]["ephemeral"].sign(ser=c["root"].raw, indexed=False)
    unsealed = eventing.messagize(c["root"], cigars=cigars, nested=True, gvrsn=Vrsn_2_0)
    _, stream = batch(c, evidence=[c["root"].said], nests=[unsealed])
    assert refusal(c["world"], stream) is errors.EVIDENCE_INVALID


def test_evidence_that_names_no_registry_is_malformed(chain):
    c = chain
    cred = c["root_issuer"].issue(ROOT, {"name": "x"}, registry=False)
    _, stream = batch(c, evidence=[cred.said], nests=[c["root_issuer"].nest(cred)])
    assert refusal(c["world"], stream) is errors.EVIDENCE_INVALID


def test_an_attached_acdc_no_evidence_reaches_is_not_checked(chain):
    c = chain
    c["root_issuer"].revoke(c["root"])
    o, stream = batch(c, evidence=None, nests=nests(c, c["root"]))
    _, msgs = send(c["world"], stream)
    assert o["d"] in admitted(msgs)


@pytest.mark.parametrize("revoked", [False, True])
def test_a_passed_on_overtures_evidence_is_checked_in_its_own_message(chain, revoked):
    c = chain
    w = c["world"]
    if revoked:
        c["root_issuer"].revoke(c["root"])
    s = w["stranger"]
    inner = issue(evidence=[c["root"].said])
    original = messages.batch(s, w["requester"].pre, [inner], nests=nests(c, c["root"]),
                              stamp=w["clock"].stamp(-60))
    orig = wire.parse(bytes(original))[0]
    o = overtures.make(REVOKE, {"credential": CRED},
                       triggeredBy={"said": inner["d"], "exn": orig.said})
    stream = c["root_issuer"].stream() + w["r"].batch([o], nests=[original], stamp=w["clock"].stamp())
    if revoked:
        assert refusal(w, stream) is errors.EVIDENCE_REVOKED
    else:
        _, msgs = send(w, stream)
        assert o["d"] in admitted(msgs)


def test_an_attached_exn_that_carries_no_overtures_is_not_a_batch(chain):
    w = chain["world"]
    nested = messages.poll(w["stranger"], w["requester"].pre, [CRED], stamp=w["clock"].stamp())
    o = overtures.make(REVOKE, {"credential": CRED})
    stream = bytes(w["stranger"].replay()) + w["r"].batch([o], nests=[nested], stamp=w["clock"].stamp())
    _, msgs = send(w, stream)
    assert o["d"] in admitted(msgs)


def test_evidence_shared_by_two_overtures_is_checked_once(chain):
    c = chain
    w = c["world"]
    first = overtures.make(REVOKE, {"credential": CRED}, evidence=[c["leaf"].said])
    second = issue(evidence=[c["leaf"].said])
    stream = c["root_issuer"].stream() + c["leaf_issuer"].stream() + w["r"].batch(
        [first, second], nests=nests(c, c["leaf"], c["root"]), stamp=w["clock"].stamp())
    _, msgs = send(w, stream)
    assert {first["d"], second["d"]} <= set(admitted(msgs))
