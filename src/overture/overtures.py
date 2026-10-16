"""Overture objects: one request for one action, identified by its own SAID (spec §5.1, §6.2).

The SAID is computed by CESR's SAID protocol over the overture object serialized as JSON
without whitespace, its fields in the order sent (this.i 48tfl3xj), which is what keripy's
Saider does for a dict with no version field.
"""

from keri.core.coring import Saider
from keri.core.signing import Salter
from keri.kering import Kinds

OPTIONAL = ("prereqs", "preconditions", "purpose", "triggeredBy", "evidence")


def nonce() -> str:
    """Return a fresh salty nonce: a qb64 128-bit salt (spec §5.1)."""
    return Salter().qb64


def make(action: str, params: dict, *, u: str | None = None, **optional) -> dict:
    """Return an overture for ``action`` with ``params``, its ``d`` set to its SAID."""
    unknown = set(optional) - set(OPTIONAL)
    if unknown:
        raise TypeError(f"Overtures have no field {sorted(unknown)[0]!r}.")
    o = {"d": "", "u": u if u is not None else nonce(), "action": action, "params": params}
    o.update((k, optional[k]) for k in OPTIONAL if k in optional)
    _, o = Saider.saidify(sad=o, kind=Kinds.json)
    return o


def verify(o: dict) -> bool:
    """Return True if ``o["d"]`` is the SAID of ``o`` as sent."""
    try:
        saider = Saider(qb64=o["d"])
    except Exception:
        return False
    return saider.verify(o, prefixed=True, kind=Kinds.json)
