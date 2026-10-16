"""An agent's Overture engine: the check order, admission, outcomes and answers (spec §6).

The engine takes one received CESR stream and returns what the agent answers. Everything it
decides is in the spec except the decision behind the counter, which a Policy makes: whether
to admit an overture, and what its outcome will be and when.
"""

import datetime
import re
from dataclasses import dataclass, field
from typing import Protocol

from keri.core.eventing import Kevery
from keri.help.helping import toIso8601

from . import catalog as catalogs
from . import errors, messages, overtures, schemas, verify, wire
from .errors import Refusal
from .store import Record, Store

PRECONDITIONS = {"startBy", "finishBy", "signer", "audience"}
REQUESTER_ROUTES = {"batch", "poll", "abort", "receipt"}
VERSION = re.compile(r"^([0-9]+)\.([0-9]+)$")


@dataclass
class Plan:
    """What the principal will do with an admitted overture, decided behind the counter."""

    status: str = "completed"
    after: datetime.timedelta = datetime.timedelta(0)
    results: list = field(default_factory=list)
    reason: str | None = None


class Policy(Protocol):
    def plan(self, requester: str, overture: dict, entry: dict) -> Plan | None:
        """Return a plan to admit the overture, or None to refuse it."""


@dataclass
class Wait:
    """An exchange the agent may hold open until ``until`` (spec §6.7)."""

    requester: str
    saids: list[str]
    until: datetime.datetime


@dataclass
class Answer:
    """What the agent sends back: CESR streams in order, and whether it may hold for more."""

    streams: list[bytes] = field(default_factory=list)
    wait: Wait | None = None
    refusal: Refusal | None = None

    @property
    def unsupported_major(self) -> bool:
        return self.refusal is not None and self.refusal.code is errors.VERSION_UNSUPPORTED


def stamp(t: datetime.datetime) -> str:
    return toIso8601(t)


def major_of(a: dict) -> int:
    m = VERSION.match(a.get("version", "")) if isinstance(a.get("version"), str) else None
    if m is None:
        raise Refusal(errors.SHAPE, "The a block carries no version of the form major.minor.")
    return int(m.group(1))


class Agent:
    def __init__(self, hab, principal: str, store: Store, policy: Policy, *,
                 entries: dict | None = None, majors=(1,),
                 window=datetime.timedelta(seconds=300), max_size=1_000_000,
                 keep=datetime.timedelta(days=30), clock=None):
        self.hab = hab
        self.principal = principal
        self.store = store
        self.policy = policy
        self.entries = entries if entries is not None else catalogs.entries()
        self.majors = tuple(majors)
        self.window = window
        self.max_size = max_size
        self.keep = keep
        self.clock = clock or (lambda: datetime.datetime.now(datetime.UTC))
        self.kvy = Kevery(db=hab.db, lax=False, local=False, rvy=getattr(hab, "rvy", None))

    # --- receiving ------------------------------------------------------------------

    def receive(self, stream: bytes) -> Answer:
        """Check one stream in the order of spec §6.1, act on it, and return the answer."""
        try:
            msg = self._check_message(stream)
        except Refusal as refusal:
            return Answer(refusal=refusal)
        name = msg.route.removeprefix(messages.PREFIX)
        return getattr(self, f"_on_{name}")(msg)

    def _check_message(self, stream: bytes) -> wire.Message:
        now = self.clock()
        if len(stream) > self.max_size:                                   # 1. bound
            raise Refusal(errors.TOO_LARGE)
        try:                                                              # 2. parse
            found = wire.parse(stream, kvy=self.kvy, rvy=getattr(self.hab, "rvy", None))
        except Exception as ex:
            raise Refusal(errors.MALFORMED, f"The stream does not parse: {ex}.") from None
        found = [m for m in found if m.route.startswith(messages.PREFIX)]
        if len(found) != 1:
            raise Refusal(errors.NO_MESSAGE if not found else errors.MALFORMED,
                          "A stream must carry exactly one Overture message.")
        msg = found[0]
        name = msg.route.removeprefix(messages.PREFIX)
        if name not in REQUESTER_ROUTES or msg.serder.pvrsn.major != 2:
            raise Refusal(errors.ROUTE_UNSUPPORTED, f"This agent does not answer {msg.route}.")
        ked = msg.ked
        if ked.get("x") or ked.get("p") or ked.get("q"):
            raise Refusal(errors.MALFORMED, "x, p and q must be empty in an Overture message.")
        verify.signatures(msg, self.kvy)                                  # 3. currency
        verify.freshness(ked.get("dt"), now, self.window)
        if not self.store.accept_once(msg.said, verify.parse_time(ked["dt"])):
            raise Refusal(errors.REPLAYED)
        self.store.prune_accepted(now - 2 * self.window)
        if msg.receiver != self.principal:                                # 4. address
            raise Refusal(errors.WRONG_PRINCIPAL)
        if major_of(msg.a) not in self.majors:                            # 5. version
            raise Refusal(errors.VERSION_UNSUPPORTED,
                          f"Supported major versions: {', '.join(map(str, self.majors))}.")
        problems = schemas.errors(name, msg.a)                            # 6. shape
        if problems:
            raise Refusal(errors.SHAPE, " ".join(problems))
        if name == "batch":
            self._check_saids(msg)                                        # 7. SAIDs
            self._check_attached(msg)                                     # 8. attached
            self._check_batch(msg)                                        # 9. integrity
        return msg

    def _check_saids(self, msg: wire.Message) -> None:
        for o in msg.a.get("overtures", []):
            if not overtures.verify(o):
                raise Refusal(errors.SAID_MISMATCH, f"Overture {o.get('d')} does not verify.")
        for nest in msg.nests:
            if nest.route == messages.route("batch"):
                self._check_saids(nest)

    def _check_attached(self, msg: wire.Message) -> None:
        for nest in msg.nests:
            if nest.serder.ilk != "exn":
                continue  # evidence ACDCs are verified by their own means, not here
            try:
                verify.signatures(nest, self.kvy)
            except Refusal as refusal:
                raise Refusal(errors.ATTACHED_INVALID, refusal.detail) from None
            if nest.route.startswith(messages.PREFIX) and major_of(nest.a) not in self.majors:
                raise Refusal(errors.VERSION_UNSUPPORTED, "An attached message has an unsupported version.")
            self._check_attached(nest)
        by_said = {n.said: n for n in msg.nests}
        for o in msg.a["overtures"]:
            trigger = o.get("triggeredBy")
            if trigger is None:
                continue
            nest = by_said.get(trigger["exn"])
            carried = [] if nest is None else [x.get("d") for x in nest.a.get("overtures", [])]
            if nest is None or nest.route != messages.route("batch") or trigger["said"] not in carried:
                raise Refusal(errors.TRIGGER_MISMATCH,
                              f"triggeredBy of {o['d']} does not match an attached batch.")

    def _check_batch(self, msg: wire.Message) -> None:
        saids = [o["d"] for o in msg.a["overtures"]]
        if len(set(saids)) != len(saids):
            raise Refusal(errors.DUPLICATE)
        major = major_of(msg.a)
        for o in msg.a["overtures"]:
            known = self.store.get(msg.sender, o["d"])
            if known is not None and known.major != major:
                raise Refusal(errors.MAJOR_CHANGED)
            for p in o.get("prereqs", []):
                if p not in saids and self.store.get(msg.sender, p) is None:
                    raise Refusal(errors.PREREQ_UNKNOWN, f"Prerequisite {p} is not known.")

    def _check_overture(self, o: dict) -> dict:
        entry = self.entries.get(o["action"])                             # 10. catalog
        if entry is None:
            raise Refusal(errors.ACTION_UNKNOWN)
        problems = catalogs.param_errors(entry, o["params"])
        if problems:
            raise Refusal(errors.PARAMS_INVALID, " ".join(problems))
        unknown = set(o.get("preconditions", {})) - PRECONDITIONS          # 11. preconditions
        if unknown:
            raise Refusal(errors.PRECONDITION_UNKNOWN, f"Not understood: {sorted(unknown)}.")
        return entry

    # --- routes -------------------------------------------------------------------

    def _on_batch(self, msg: wire.Message) -> Answer:
        now = self.clock()
        requester = msg.sender
        admitted: list[Record] = []
        refusals: dict[str, Refusal] = {}
        accepted: set[str] = set()
        for o in msg.a["overtures"]:
            known = self.store.get(requester, o["d"])
            if known is not None:
                admitted.append(known)  # a resend: answered with the original admission
                accepted.add(o["d"])
                continue
            try:
                entry = self._check_overture(o)
                if any(p not in accepted and self.store.get(requester, p) is None
                       for p in o.get("prereqs", [])):
                    raise Refusal(errors.PREREQ_UNKNOWN, "A prerequisite in the batch was refused.")
            except Refusal as refusal:
                refusals[o["d"]] = refusal
                continue
            start_by = o.get("preconditions", {}).get("startBy")
            plan = self.policy.plan(requester, o, entry)
            if plan is None or (start_by and verify.parse_time(start_by) < now):
                continue
            record = Record(requester=requester, said=o["d"], major=major_of(msg.a),
                            admitted=now, kept_until=now + self.keep, overture=o,
                            batch_exn=msg.said, due=now + plan.after,
                            plan={"status": plan.status, "results": plan.results,
                                  "reason": plan.reason})
            self.store.admit(record)
            admitted.append(record)
            accepted.add(o["d"])
        if not admitted:
            first = next(iter(refusals.values()), None)
            return Answer(refusal=first)
        self.advance()
        streams = self._receipts(requester, admitted)
        wait = None
        if "waitUntil" in msg.a:
            wait = Wait(requester, [r.said for r in admitted], verify.parse_time(msg.a["waitUntil"]))
        return Answer(streams=streams, wait=wait)

    def _receipts(self, requester: str, records: list[Record]) -> list[bytes]:
        by_time: dict[datetime.datetime, list[Record]] = {}
        for r in records:
            by_time.setdefault(r.admitted, []).append(r)
        streams = []
        for when, group in sorted(by_time.items()):
            items = [{"meaning": "admitted", "said": r.said, "keptUntil": stamp(r.kept_until)}
                     for r in group]
            streams.append(bytes(messages.receipt(
                self.hab, requester, items, nextPoll=self._next_poll(requester, [r.said for r in group]),
                stamp=stamp(when))))
        return streams

    def _on_poll(self, msg: wire.Message) -> Answer:
        self.advance()
        saids = msg.a["saids"]
        wait = None
        if "waitUntil" in msg.a:
            wait = Wait(msg.sender, saids, verify.parse_time(msg.a["waitUntil"]))
            if not self.has_news(wait):
                return Answer(wait=wait)
        return Answer(streams=[self.status_report(msg.sender, saids)])

    def _on_abort(self, msg: wire.Message) -> Answer:
        self.advance()
        for said in msg.a["saids"]:
            record = self.store.get(msg.sender, said)
            if record is not None and record.status == "pending":
                self.store.end(msg.sender, said, "aborted", self.clock())
        self.advance()
        return Answer(streams=[self.status_report(msg.sender, msg.a["saids"])])

    def _on_receipt(self, msg: wire.Message) -> Answer:
        if "nextPoll" in msg.a or any(r["meaning"] != "seen" for r in msg.a["receipts"]):
            return Answer(refusal=Refusal(errors.MALFORMED, "A requester signs only seen receipts."))
        protected = {p for r in self.store.pending(msg.sender) for p in r.overture.get("prereqs", [])}
        for r in msg.a["receipts"]:
            covered = self.store.reported(r["said"], msg.sender)
            self.store.forget(msg.sender, [s for s in covered if s not in protected])
        return Answer()

    # --- outcomes and status ------------------------------------------------------

    def advance(self) -> None:
        """Apply every outcome that is due, until nothing more changes (spec §6.3, §6.5)."""
        now = self.clock()
        self.store.expire(now)
        changed = True
        while changed:
            changed = False
            for r in self.store.pending():
                outcome = self._outcome(r, now)
                if outcome is not None:
                    status, results, reason = outcome
                    self.store.end(r.requester, r.said, status, now, results=results, reason=reason)
                    changed = True

    def _outcome(self, r: Record, now: datetime.datetime):
        prereqs = [self.store.get(r.requester, p) for p in r.overture.get("prereqs", [])]
        if any(p is None or p.status not in ("pending", "completed") for p in prereqs):
            return "precluded", [], None
        if any(p.status == "pending" for p in prereqs):
            return None
        start_by = r.overture.get("preconditions", {}).get("startBy")
        if now < r.due:
            if start_by and verify.parse_time(start_by) < now:
                return "expired", [], None
            return None
        return r.plan["status"], r.plan.get("results", []), r.plan.get("reason")

    def statuses(self, requester: str, saids: list[str]) -> list[dict]:
        out = []
        for said in saids:
            r = self.store.get(requester, said)
            if r is None:
                out.append({"said": said, "status": "unknown"})
                continue
            item = {"said": said, "status": r.status}
            if r.status != "pending":
                item["results"] = r.results
                if r.reason:
                    item["reason"] = r.reason
            out.append(item)
        return out

    def _next_poll(self, requester: str, saids: list[str]) -> str | None:
        dues = [r.due for s in saids if (r := self.store.get(requester, s)) is not None
                and r.status == "pending"]
        if not dues:
            return None
        now = self.clock()
        soonest = max(min(dues), now + datetime.timedelta(seconds=1))
        return stamp(soonest.replace(microsecond=0) + datetime.timedelta(seconds=1))

    def status_report(self, requester: str, saids: list[str]) -> bytes:
        statuses = self.statuses(requester, saids)
        stream = messages.status(self.hab, requester, statuses,
                                 nextPoll=self._next_poll(requester, saids),
                                 stamp=stamp(self.clock()))
        exn = wire.parse(bytes(stream))[0].said
        ended = [s["said"] for s in statuses if s["status"] not in ("pending", "unknown")]
        if ended:
            self.store.report(exn, requester, ended)
        return bytes(stream)

    def has_news(self, wait: Wait) -> bool:
        """True when a held exchange should be answered now (spec §6.7)."""
        self.advance()
        if self.clock() >= wait.until:
            return True
        return any(s["status"] != "pending" for s in self.statuses(wait.requester, wait.saids))
