"""Issuing ACDCs in a credential registry, for tests, vectors and the stand-in's examples.

An Issuer keeps one registry for one Hab and anchors each TEL event in the Hab's KEL. It
gives back what a requester sends to rely on a credential as evidence (spec §4.3): the KEL
and the TEL events, which go before the batch at top level, and each credential as a nested
group to attach to the batch.
"""

from keri.core import coring, eventing, scheming
from keri.core.coring import Diger, Number, Prefixer
from keri.core.structing import SealEvent, SealSource
from keri.kering import Vrsn_1_0, Vrsn_2_0
from keri.vc import proving
from keri.vdr import eventing as tel


def schema(title: str, properties: dict | None = None, required=()) -> scheming.Schemer:
    """A SAIDified JSON Schema for credentials whose a block has ``properties``."""
    sed = {"$id": "", "$schema": "http://json-schema.org/draft-07/schema#", "title": title,
           "type": "object", "required": ["v", "d", "i", "s", "a"],
           "properties": {"a": {"type": "object", "properties": properties or {},
                                "required": list(required)}}}
    _, sed = coring.Saider.saidify(sad=sed, label="$id")
    return scheming.Schemer(sed=sed)


class Issuer:
    def __init__(self, hab, nonce: str):
        self.hab = hab
        self.events: list[bytes] = []
        self.anchors = {}
        self.latest = {}
        vcp = tel.incept(hab.pre, baks=[], toad=0, nonce=nonce, cnfg=["NB"], version=Vrsn_1_0)
        self.registry = vcp.pre
        self._anchor(vcp, self.registry, 0)

    def _anchor(self, event, i: str, sn: int):
        self.hab.interact(data=[dict(i=i, s=f"{sn:x}", d=event.said)])
        ixn = self.hab.kever.serder
        self.events.append(bytes(eventing.messagize(
            event, bonds=[SealSource(s=Number(num=ixn.sn), d=Diger(qb64=ixn.said))])))
        return ixn

    def issue(self, schemer, data: dict, *, recipient=None, edges=None, registry=True,
              dt=None):
        """Issue a credential; ``edges`` maps each label to an edge, or is a list of such maps."""
        source = None
        if isinstance(edges, list):
            source = [coring.Saider.saidify(sad={"d": "", **e})[1] for e in edges]
        elif edges is not None:
            source = coring.Saider.saidify(sad={"d": "", **edges})[1]
        cred = proving.credential(schema=schemer.said, issuer=self.hab.pre,
                                  data=dict(data, **({"dt": dt} if dt else {})),
                                  recipient=recipient, source=source,
                                  status=self.registry if registry else None, version=Vrsn_1_0)
        iss = tel.issue(vcdig=cred.said, regk=self.registry, version=Vrsn_1_0, dt=dt)
        self.anchors[cred.said] = self._anchor(iss, cred.said, 0)
        self.latest[cred.said] = iss.said
        return cred

    def revoke(self, cred, *, dt=None) -> None:
        rev = tel.revoke(vcdig=cred.said, regk=self.registry, dig=self.latest[cred.said],
                         version=Vrsn_1_0, dt=dt)
        self._anchor(rev, cred.said, 1)
        self.latest[cred.said] = rev.said

    def stream(self) -> bytes:
        """The issuer's KEL and the registry's TEL events, to send before the batch."""
        return bytes(self.hab.replay()) + b"".join(self.events)

    def nest(self, cred) -> bytes:
        """``cred`` as a nested group with its source seal, to attach to a batch."""
        ixn = self.anchors[cred.said]
        bonds = [SealEvent(i=Prefixer(qb64=self.hab.pre), s=Number(num=ixn.sn),
                           d=Diger(qb64=ixn.said))]
        return bytes(eventing.messagize(cred, bonds=bonds, nested=True, gvrsn=Vrsn_2_0))
