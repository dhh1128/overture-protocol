"""Currency, signatures and freshness (spec §4.4; this.i 35wllumn, 3j0mdxh4).

A signature is judged against its signer's latest establishment event. A message signed
under keys the signer has since rotated away is refused, and one signed under keys newer
than the agent knows is refused until the agent has that key state.
"""

import datetime

from keri.core.coring import Prefixer

from . import errors
from .errors import Refusal


def signatures(msg, kvy) -> None:
    """Raise Refusal unless ``msg`` is signed by its sender under current keys."""
    sender = msg.sender
    if not Prefixer(qb64=sender).transferable:
        return _cigars(msg, sender)
    groups = [g for g in msg.tsgs if g[0].qb64 == sender]
    if not groups or msg.cigars:
        raise Refusal(errors.SIGNATURE_INVALID, f"No signature group from {sender} is attached.")
    kever = kvy.kevers.get(sender)
    if kever is None:
        raise Refusal(errors.KEY_STATE_MISSING, f"No KEL is known for {sender}.")
    for _, number, diger, sigers in groups:
        sn = number.num if hasattr(number, "num") else number.sn
        last = kever.lastEst
        if sn > last.s:
            raise Refusal(errors.KEY_STATE_MISSING,
                          f"{sender} signed under event {sn}, beyond the known event {last.s}.")
        if (sn, diger.qb64) != (last.s, last.d):
            raise Refusal(errors.KEYS_ROTATED,
                          f"{sender} signed under event {sn}, and its keys are now at {last.s}.")
        indices = []
        for siger in sigers:
            if siger.index >= len(kever.verfers):
                raise Refusal(errors.SIGNATURE_INVALID, f"Signature index {siger.index} is out of range.")
            if not kever.verfers[siger.index].verify(siger.raw, msg.serder.raw):
                raise Refusal(errors.SIGNATURE_INVALID, f"Signature {siger.index} does not verify.")
            indices.append(siger.index)
        if not kever.tholder.satisfy(indices):
            raise Refusal(errors.SIGNATURE_INVALID, "The signatures do not meet the signing threshold.")


def _cigars(msg, sender) -> None:
    for cigar in msg.cigars:
        if cigar.verfer.qb64 == sender and cigar.verfer.verify(cigar.raw, msg.serder.raw):
            return
    raise Refusal(errors.SIGNATURE_INVALID, f"No valid signature by {sender} is attached.")


def parse_time(dt) -> datetime.datetime:
    """Read a time in KERI's dt form, which always carries a UTC offset."""
    try:
        t = datetime.datetime.fromisoformat(dt)
    except (TypeError, ValueError):
        raise Refusal(errors.MALFORMED, f"{dt!r} is not a time in KERI's dt form.") from None
    if t.tzinfo is None:
        raise Refusal(errors.MALFORMED, f"{dt!r} has no UTC offset.")
    return t


def freshness(dt, now: datetime.datetime, window: datetime.timedelta) -> None:
    """Raise Refusal unless ``dt`` is within ``window`` of ``now``."""
    if abs(parse_time(dt) - now) > window:
        raise Refusal(errors.NOT_FRESH, f"The message's time {dt} is outside the window.")
