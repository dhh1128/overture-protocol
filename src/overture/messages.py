"""Building signed Overture messages (spec §4, §5).

Every message is a KERI v2 exn with a JSON body under an /overture/ route, framed as a CESR
v2 message + attachments group (-B) whose attachments carry the sender's signatures and any
attached messages as nested -B groups (spec §4.3; this.i 0xc2dqvw).
"""

from keri.core import eventing
from keri.kering import Kinds, Vrsn_2_0

VERSION = "1.0"
PREFIX = "/overture/"


def route(name: str) -> str:
    return PREFIX + name


def build(hab, name: str, receiver: str, a: dict, *, stamp: str | None = None,
          nests=()) -> bytearray:
    """Return the framed, signed exn from ``hab`` under route ``name`` with ``a``."""
    serder = eventing.exchange(sender=hab.pre, receiver=receiver, route=route(name),
                               attributes={"version": VERSION, **a}, stamp=stamp,
                               pvrsn=Vrsn_2_0, gvrsn=Vrsn_2_0, kind=Kinds.json)
    nests = [bytes(n) for n in nests] or None
    if hab.kever.prefixer.transferable:
        return hab.endorse(serder=serder, nested=True, gvrsn=Vrsn_2_0, nests=nests)
    cigars = hab.sign(ser=serder.raw, indexed=False)
    return eventing.messagize(serder, cigars=cigars, nested=True, gvrsn=Vrsn_2_0, nests=nests)


def _opt(**fields) -> dict:
    return {k: v for k, v in fields.items() if v is not None}


def batch(hab, principal, overtures, *, waitUntil=None, nests=(), stamp=None):
    """A requester's batch of overtures to a principal's agent (spec §5.1)."""
    return build(hab, "batch", principal, {"overtures": list(overtures), **_opt(waitUntil=waitUntil)},
                 stamp=stamp, nests=nests)


def receipt(hab, to, receipts, *, nextPoll=None, stamp=None):
    """Receipts signed by an agent (admitted) or a requester (seen) (spec §5.2)."""
    return build(hab, "receipt", to, {"receipts": list(receipts), **_opt(nextPoll=nextPoll)},
                 stamp=stamp)


def poll(hab, principal, saids, *, waitUntil=None, stamp=None):
    """A requester's poll about overtures it sent (spec §5.3)."""
    return build(hab, "poll", principal, {"saids": list(saids), **_opt(waitUntil=waitUntil)},
                 stamp=stamp)


def abort(hab, principal, saids, *, stamp=None):
    """A requester's withdrawal of overtures it sent (spec §5.4)."""
    return build(hab, "abort", principal, {"saids": list(saids)}, stamp=stamp)


def status(hab, to, statuses, *, nextPoll=None, nests=(), stamp=None):
    """An agent's status report (spec §5.5)."""
    return build(hab, "status", to, {"statuses": list(statuses), **_opt(nextPoll=nextPoll)},
                 stamp=stamp, nests=nests)
