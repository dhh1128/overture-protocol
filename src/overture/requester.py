"""The requester's side: send overtures, and check what the agent answers (spec §5, §6).

A Requester signs with its own Hab and keeps the agent's key state in its own Kevery, so
it can verify receipts and status reports against the agent AID that signed them.
"""

from keri.core.eventing import Kevery
from keri.kering import TraitDex

from . import errors, messages, schemas, verify, wire
from .errors import Refusal


class Requester:
    def __init__(self, hab, principal: str):
        self.hab = hab
        self.principal = principal
        self.kvy = Kevery(db=hab.db, lax=False, local=False)

    def learn(self, stream: bytes) -> None:
        """Process KELs and replies, such as the agent's KEL from its OOBI."""
        wire.parse(stream, kvy=self.kvy)

    def signs_as_principal(self, aid: str) -> bool:
        """True when ``aid`` is the principal, or a delegate of it incepted with KERI's
        Delegate-Is-Delegator trait, by the KELs this requester holds (spec §7, signer).
        keripy defines the trait but does not act on it, and its key state keeps only the EO
        and DND traits, so this reads the delegate's inception event, whose SAID is the
        delegate's AID."""
        if aid == self.principal:
            return True
        kever = self.kvy.kevers.get(aid)
        if kever is None or kever.delpre != self.principal:
            return False
        inception = self.kvy.db.evts.get(keys=(aid, aid))
        return TraitDex.DelegateIsDelegator in inception.ked.get("c", [])

    def kel(self) -> bytes:
        """This requester's own KEL, to send before its first message."""
        return bytes(self.hab.replay())

    def batch(self, overtures, *, waitUntil=None, nests=(), stamp=None, with_kel=True) -> bytes:
        msg = messages.batch(self.hab, self.principal, overtures, waitUntil=waitUntil,
                             nests=nests, stamp=stamp)
        return (self.kel() if with_kel else b"") + bytes(msg)

    def poll(self, saids, *, waitUntil=None, stamp=None) -> bytes:
        return bytes(messages.poll(self.hab, self.principal, saids, waitUntil=waitUntil, stamp=stamp))

    def abort(self, saids, *, stamp=None) -> bytes:
        return bytes(messages.abort(self.hab, self.principal, saids, stamp=stamp))

    def seen(self, report_said: str, *, stamp=None) -> bytes:
        return bytes(messages.receipt(self.hab, self.principal,
                                      [{"meaning": "seen", "said": report_said}], stamp=stamp))

    def read(self, stream: bytes, *, agents: set[str] | None = None) -> list[wire.Message]:
        """Parse the agent's answer and check each message's signer, address and shape."""
        out = []
        for msg in wire.parse(stream, kvy=self.kvy):
            if not msg.route.startswith(messages.PREFIX):
                continue
            if agents is not None and msg.sender not in agents:
                raise Refusal(errors.SIGNATURE_INVALID, f"{msg.sender} is not an agent of the principal.")
            verify.signatures(msg, self.kvy)
            if msg.receiver != self.hab.pre:
                raise Refusal(errors.WRONG_PRINCIPAL, "The answer is addressed to someone else.")
            name = msg.route.removeprefix(messages.PREFIX)
            problems = schemas.errors(name, msg.a)
            if problems:
                raise Refusal(errors.SHAPE, " ".join(problems))
            out.append(msg)
        return out


def admitted(msgs: list[wire.Message]) -> dict[str, dict]:
    """The admitted receipts among ``msgs``, by overture SAID, each with its receipt's dt."""
    found = {}
    for m in msgs:
        if m.route == messages.route("receipt"):
            for r in m.a["receipts"]:
                if r["meaning"] == "admitted":
                    found[r["said"]] = dict(r, admittedAt=m.ked["dt"])
    return found


def statuses(msgs: list[wire.Message]) -> dict[str, dict]:
    """The statuses among ``msgs``, by overture SAID; a later report wins."""
    found = {}
    for m in msgs:
        if m.route == messages.route("status"):
            for s in m.a["statuses"]:
                found[s["said"]] = s
    return found


def reports(msgs: list[wire.Message]) -> list[str]:
    """The exn SAIDs of the status reports among ``msgs``, which a seen receipt references."""
    return [m.said for m in msgs if m.route == messages.route("status")]
