"""Checking attached authority evidence at step 8 of the check order (spec §6.1; this.i 2s0z8frg).

Each evidence SAID must have its ACDC attached, and that ACDC and every ACDC its edges reach
must verify against the TEL state the agent holds. keripy's Verifier does most of that, with
two gaps the checks here close: it saves a revoked credential rather than refusing it, and
it never compares a credential's issuer with the controller of the registry that issued it.
"""

import contextlib
import io
from types import SimpleNamespace

from keri import kering
from keri.core import CacheResolver
from keri.core.serdering import SerderACDC
from keri.kering import Ilks
from keri.vdr.eventing import Reger, Tevery
from keri.vdr.verifying import Verifier

from . import errors
from .errors import Refusal


class Evidence:
    def __init__(self, db, *, reger=None):
        self.db = db
        self.reger = reger if reger is not None else Reger(name=db.name, temp=True)
        self.tvy = Tevery(reger=self.reger, db=db, local=False)
        self.vry = Verifier(hby=SimpleNamespace(name=db.name, temp=True, inited=False, db=db),
                            reger=self.reger)
        self.vry.tvy = self.tvy
        self.vry.resolver = CacheResolver(db=db)
        self.vry.inited = True

    def learn_schema(self, schemer) -> None:
        """Let the agent check credentials of this schema."""
        self.db.schema.pin(keys=(schemer.said,), val=schemer)

    def check(self, saids, nests) -> None:
        """Raise Refusal unless each SAID's chain is attached among ``nests`` and verifies."""
        acdcs = {n.said: n for n in nests if isinstance(n.serder, SerderACDC)}
        done = set()
        for said in saids:
            self._chain(said, acdcs, done)

    def _chain(self, said, acdcs, done) -> None:
        if said in done:
            return
        nest = acdcs.get(said)
        if nest is None:
            raise Refusal(errors.EVIDENCE_MISSING, f"No ACDC with SAID {said} is attached.")
        for far in _edges(nest.serder):
            self._chain(far, acdcs, done)
        self._one(nest)
        done.add(said)

    def _one(self, nest) -> None:
        creder = nest.serder
        if not nest.ssts:
            raise Refusal(errors.EVIDENCE_INVALID, f"ACDC {creder.said} carries no source seal.")
        if creder.regid is None:
            raise Refusal(errors.EVIDENCE_INVALID, f"ACDC {creder.said} names no registry.")
        if creder.regid not in self.reger.tevers:
            raise Refusal(errors.EVIDENCE_STATE_MISSING, f"Registry {creder.regid} is not known.")
        tever = self.reger.tevers[creder.regid]
        if tever.pre != creder.israid:
            raise Refusal(errors.EVIDENCE_INVALID,
                          f"ACDC {creder.said} names {creder.israid} as issuer, but registry "
                          f"{creder.regid} is controlled by {tever.pre}.")
        state = tever.vcState(creder.said)
        if state is None:
            raise Refusal(errors.EVIDENCE_STATE_MISSING, f"No issuance of {creder.said} is known.")
        if state.et in (Ilks.rev, Ilks.brv):
            raise Refusal(errors.EVIDENCE_REVOKED, f"ACDC {creder.said} is revoked.")
        prefixer, number, diger = nest.ssts[-1]
        try:
            with contextlib.redirect_stdout(io.StringIO()):  # keripy prints what it raises
                self.vry.processCredential(creder, prefixer, number, diger)
        except kering.MissingSchemaError as ex:
            raise Refusal(errors.EVIDENCE_STATE_MISSING, str(ex)) from None
        except Exception as ex:
            raise Refusal(errors.EVIDENCE_INVALID, str(ex)) from None
        finally:
            self.vry.cues.clear()

    def close(self) -> None:
        self.reger.close(clear=True)


def _edges(creder):
    """The SAIDs of the credentials this one's edges point to."""
    blocks = creder.edge if isinstance(creder.edge, list) else [creder.edge or {}]
    for block in blocks:
        for label, node in block.items():
            if label not in ("d", "o") and isinstance(node, dict) and "n" in node:
                yield node["n"]
