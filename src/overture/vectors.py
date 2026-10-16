"""Test vectors: generated from fixed salts, nonces and times (this.i 8kzvymmy).

``python -m overture.vectors`` writes one JSON file per scenario into vectors/. Each holds
the agent's OOBI stream (its principal's and its own KELs and endpoint replies), and a list
of exchanges: the CESR stream a requester sends at a stated agent time, and what the agent
must answer, either the exact answer stream with its HTTP status or, for a refusal, the
step of the check order (spec §6.1) that refuses it and the reason code this package logs.
The test suite regenerates every file and fails if any byte differs.
"""

import argparse
import datetime
import functools
import json
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path

from keri.app import habbing
from keri.core import eventing
from keri.core.coring import Diger, Number
from keri.core.signing import Salter
from keri.help import helping
from keri.kering import Kinds, Vrsn_2_0

from . import catalog, engine, errors, messages, overtures, wire
from .issuing import Issuer, schema
from .requester import Requester
from .standin import StandIn

T0 = datetime.datetime(2026, 10, 15, 17, 0, tzinfo=datetime.UTC)
URL = "http://agent.example:5642"
SCHEMA = "EBdXt3gIXOf2BBWNHdSXCJnFJL5OuQPyM5K0neuniccM"
CREDENTIAL = "EKMXqyMQmOy0RuEj1VgOK9aD4GYR0D8Dcj0kssQtcY4-"
ISSUEE = "DKxy2sgzfplyr-tgwIxS19f2OchFHtLwPWD3v4oYimBx"
AUTHORITY = schema("Licensing authority", {"region": {"type": "string"}}, required=["region"])
LICENCE = schema("Driving licence", {"class": {"type": "string"}}, required=["class"])
UNKNOWN = schema("A schema the agent was never given")
SETTINGS = {"max_size": "maxSize"}

STEPS = {
    errors.TOO_LARGE: 1, errors.NO_MESSAGE: 2, errors.MALFORMED: 2,
    errors.ROUTE_UNSUPPORTED: 2, errors.KEY_STATE_MISSING: 3, errors.KEYS_ROTATED: 3,
    errors.SIGNATURE_INVALID: 3, errors.NOT_FRESH: 3, errors.REPLAYED: 3,
    errors.WRONG_PRINCIPAL: 4, errors.VERSION_UNSUPPORTED: 5, errors.SHAPE: 6,
    errors.SAID_MISMATCH: 7, errors.ATTACHED_INVALID: 8, errors.TRIGGER_MISMATCH: 8,
    errors.EVIDENCE_MISSING: 8, errors.EVIDENCE_STATE_MISSING: 8, errors.EVIDENCE_INVALID: 8,
    errors.EVIDENCE_REVOKED: 8,
    errors.DUPLICATE: 9, errors.PREREQ_UNKNOWN: 9, errors.MAJOR_CHANGED: 9,
    errors.ACTION_UNKNOWN: 10, errors.PARAMS_INVALID: 10, errors.PRECONDITION_UNKNOWN: 11,
}


def nonce(n: int) -> str:
    """The n-th fixed nonce, so overture SAIDs are the same on every run."""
    return Salter(raw=n.to_bytes(16, "big")).qb64


def action(title: str) -> str:
    return catalog.by_title(title)["$id"]


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t

    def stamp(self, seconds=0) -> str:
        return engine.stamp(self.t + datetime.timedelta(seconds=seconds))


class Scenario:
    """One agent, one requester and one other party, all from fixed salts."""

    def __init__(self, stack: ExitStack, script: dict, clock: Clock, settings: dict):
        self.clock = clock
        self.stack = stack
        self.settings = settings
        work = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        hby = stack.enter_context(habbing.openHby(
            name="vector-agent", temp=True, salt=Salter(raw=b"vector-agent-000").qb64))
        self.standin = StandIn(hby, URL, script, work / "agent.sqlite", clock=self.clock,
                               stamp=self.clock.stamp(), **settings)
        stack.callback(self.standin.close)
        self.principal = self.standin.principal.pre
        self.requester = self.party("vector-requester", b"vector-requester")
        self.other = self.party("vector-other-000", b"vector-other-000")
        self.schemas = []
        self.exchanges = []

    def party(self, name, raw, **kwa) -> Requester:
        hby = self.stack.enter_context(habbing.openHby(name=name, temp=True,
                                                       salt=Salter(raw=raw).qb64))
        r = Requester(hby.makeHab(name=name, **kwa), self.principal)
        r.learn(self.standin.oobi_stream(self.principal))
        return r

    @functools.cached_property
    def issuer(self) -> Issuer:
        """A credential issuer with one registry, made the first time a scenario needs it."""
        return Issuer(self.party("vector-issuer-00", b"vector-issuer-00").hab, nonce(900))

    def learn(self, schemer) -> None:
        """Give the agent a credential schema; the vector lists it under agent.schemas."""
        self.standin.engine.learn_schema(schemer)
        self.schemas.append(json.loads(schemer.raw))

    def send(self, stream: bytes, note: str, reader: Requester | None = None) -> list[wire.Message]:
        """Send ``stream`` at the current agent time, and record the exchange."""
        when = self.clock.stamp()
        answer = self.standin.engine.receive(bytes(stream))
        streams = list(answer.streams)
        if answer.wait is not None and self.standin.engine.has_news(answer.wait):
            streams.append(self.standin.engine.status_report(answer.wait.requester, answer.wait.saids))
        record = {"note": note, "agentTime": when, "send": bytes(stream).decode()}
        if answer.unsupported_major:
            record["expect"] = {"status": 400, "supportedMajors": list(self.standin.engine.majors),
                                "refused": self._refused(answer.refusal)}
        elif streams:
            record["expect"] = {"status": 200, "answer": b"".join(streams).decode()}
        elif answer.refusal is not None:
            record["expect"] = {"status": 204, "refused": self._refused(answer.refusal)}
        else:
            record["expect"] = {"status": 204}
        self.exchanges.append(record)
        return (reader or self.requester).read(b"".join(streams)) if streams else []

    @staticmethod
    def _refused(refusal) -> dict:
        return {"step": STEPS[refusal.code], "code": refusal.code.code}

    def tick(self, seconds: int) -> None:
        self.clock.t += datetime.timedelta(seconds=seconds)

    def vector(self, description: str, spec: str) -> dict:
        agent = {"principal": self.principal, "agent": self.standin.agent.pre, "url": URL,
                 "oobi": self.standin.oobi_stream(self.principal).decode()}
        if self.settings:
            agent["settings"] = {SETTINGS[k]: v for k, v in self.settings.items()}
        if self.schemas:
            agent["schemas"] = self.schemas
        parties = {"requester": self.requester.hab.pre, "other": self.other.hab.pre}
        if "issuer" in self.__dict__:
            parties["issuer"] = self.issuer.hab.pre
        return {"description": description, "spec": spec, "agent": agent, **parties,
                "exchanges": self.exchanges}


def issue(n: int, **kwa) -> dict:
    return overtures.make(action("Issue a credential"), {"schema": SCHEMA, "issuee": ISSUEE},
                          u=nonce(n), **kwa)


def revoke(n: int, **kwa) -> dict:
    return overtures.make(action("Revoke a credential"), {"credential": CREDENTIAL}, u=nonce(n), **kwa)


# --- scenarios ---------------------------------------------------------------------

def admit_and_complete(s: Scenario):
    o = issue(1)
    s.send(s.requester.batch([o], stamp=s.clock.stamp()), "A batch with one overture is admitted.")
    s.tick(1)
    s.send(s.requester.poll([o["d"]], stamp=s.clock.stamp()), "A poll returns its outcome.")
    return "An overture is admitted, then completed.", "§5.1, §5.2, §5.3, §5.5, §6.4"


def pending_then_complete(s: Scenario):
    o = issue(2)
    s.send(s.requester.batch([o], stamp=s.clock.stamp()), "The receipt carries nextPoll.")
    s.tick(10)
    s.send(s.requester.poll([o["d"]], stamp=s.clock.stamp()), "Still pending.")
    s.tick(50)
    s.send(s.requester.poll([o["d"]], stamp=s.clock.stamp()), "Completed, with its result.")
    return "An overture stays pending until its outcome.", "§6.3, §6.7"


def held_batch(s: Scenario):
    o = revoke(3)
    s.send(s.requester.batch([o], waitUntil=s.clock.stamp(30), stamp=s.clock.stamp()),
           "A batch with waitUntil is answered by its receipt, then a status report.")
    return "A held batch is answered with its receipt and then its outcome.", "§6.4, §6.7, §10"


def revoke_and_reissue(s: Scenario):
    first = revoke(4)
    second = issue(5, prereqs=[first["d"]], purpose="Replace my lost license.")
    s.send(s.requester.batch([first, second], stamp=s.clock.stamp()), "Both are admitted.")
    s.tick(60)
    s.send(s.requester.poll([first["d"], second["d"]], stamp=s.clock.stamp()),
           "The reissue completes after the revocation.")
    return "Revoke and reissue a license, linked as a prerequisite.", "§6.5, Appendix A"


def precluded(s: Scenario):
    first = revoke(6)
    second = issue(7, prereqs=[first["d"]])
    s.send(s.requester.batch([first, second], stamp=s.clock.stamp()), "Both are admitted.")
    s.tick(1)
    s.send(s.requester.poll([first["d"], second["d"]], stamp=s.clock.stamp()),
           "The revocation is declined, so the reissue is precluded.")
    return "A prerequisite that does not succeed precludes its dependant.", "§6.3, §6.5"


def resend(s: Scenario):
    o = issue(8)
    s.send(s.requester.batch([o], stamp=s.clock.stamp()), "Admitted.")
    s.tick(5)
    s.send(s.requester.batch([o], stamp=s.clock.stamp(), with_kel=False),
           "A resend is answered with the original admission time and keptUntil.")
    return "A resend repeats the original admission.", "§6.6"


def abort(s: Scenario):
    o = issue(9)
    s.send(s.requester.batch([o], stamp=s.clock.stamp()), "Admitted, pending for a minute.")
    s.tick(5)
    s.send(s.requester.abort([o["d"]], stamp=s.clock.stamp()), "The abort is honored.")
    return "An abort ends a pending overture.", "§5.4, §6.7"


def seen(s: Scenario):
    o = revoke(10)
    s.send(s.requester.batch([o], stamp=s.clock.stamp()), "Admitted.")
    s.tick(1)
    msgs = s.send(s.requester.poll([o["d"]], stamp=s.clock.stamp()), "Completed.")
    s.tick(1)
    s.send(s.requester.seen(msgs[0].said, stamp=s.clock.stamp()),
           "The requester's seen lets the agent forget the outcome.")
    s.tick(1)
    s.send(s.requester.poll([o["d"]], stamp=s.clock.stamp()), "Now unknown.")
    return "A requester's seen lets the agent forget early.", "§5.2, §6.6"


def pass_on(s: Scenario):
    original = messages.batch(s.other.hab, s.requester.hab.pre,
                              [overtures.make(action("Introduce me"), {"to": ISSUEE}, u=nonce(11))],
                              stamp=s.clock.stamp(-3600))
    orig = wire.parse(bytes(original))[0]
    o = overtures.make(action("Accept an introduction"), {"from": s.other.hab.pre}, u=nonce(12),
                       triggeredBy={"said": orig.a["overtures"][0]["d"], "exn": orig.said})
    stream = s.other.kel() + s.requester.batch([o], nests=[original], stamp=s.clock.stamp())
    s.send(stream, "A hop's own overture, with the original attached unaltered an hour later.")
    s.tick(1)
    wrong = overtures.make(action("Accept an introduction"), {"from": s.other.hab.pre}, u=nonce(14),
                           triggeredBy={"said": CREDENTIAL, "exn": orig.said})
    s.send(s.requester.batch([wrong], nests=[original], stamp=s.clock.stamp(), with_kel=False),
           "A triggeredBy whose said is not an overture in the attached message.")
    return "Passing an overture on by attaching the original.", "§6.8, Appendix A"


def relationship_aid(s: Scenario):
    o = overtures.make(action("Create a relationship AID"), {}, u=nonce(13))
    s.send(s.requester.batch([o], stamp=s.clock.stamp()), "Admitted.")
    s.tick(1)
    s.send(s.requester.poll([o["d"]], stamp=s.clock.stamp()),
           "Completed: the new AID's inception event seals the overture's SAID.")
    return "A relationship AID states it is a result of the overture.", "§6.11, §8"


def refusals(s: Scenario):
    r = s.requester
    good = issue(20)
    s.send(r.batch([dict(issue(21), purpose="changed after hashing"), good], stamp=s.clock.stamp()),
           "One overture's SAID does not verify, so the whole batch is malformed.")
    s.tick(1)
    s.send(r.batch([good, good], stamp=s.clock.stamp(), with_kel=False), "The same overture twice.")
    s.tick(1)
    s.send(r.batch([issue(22, prereqs=[CREDENTIAL])], stamp=s.clock.stamp(), with_kel=False),
           "A prerequisite that is neither admitted nor in the batch.")
    s.tick(1)
    s.send(r.batch([overtures.make(CREDENTIAL, {}, u=nonce(23))], stamp=s.clock.stamp(),
                   with_kel=False), "An action the agent does not know.")
    s.tick(1)
    s.send(r.batch([issue(24, preconditions={"notYetDefined": True})], stamp=s.clock.stamp(),
                   with_kel=False), "A precondition the agent does not understand.")
    s.tick(1)
    s.send(r.batch([overtures.make(action("Issue a credential"), {"schema": SCHEMA}, u=nonce(25))],
                   stamp=s.clock.stamp(), with_kel=False), "params that fail the catalog entry.")
    s.tick(1)
    s.send(Requester(r.hab, r.hab.pre).batch([issue(26)], stamp=s.clock.stamp(), with_kel=False),
           "Addressed to a principal this agent does not act for.")
    s.tick(1)
    s.send(messages.build(r.hab, "poll", s.principal, {"saids": [CREDENTIAL], "version": "2.0"},
                          stamp=s.clock.stamp()), "A major version the agent does not support.")
    s.tick(1)
    s.send(messages.build(r.hab, "poll", s.principal, {"saids": []}, stamp=s.clock.stamp()),
           "An a block that fails its schema.")
    s.tick(1)
    s.send(r.batch([issue(27)], stamp=s.clock.stamp(-301), with_kel=False),
           "A message outside the freshness window.")
    s.tick(1)
    stale = r.poll([CREDENTIAL], stamp=s.clock.stamp())
    s.send(stale, "Accepted once.")
    s.send(stale, "The same message again is a replay.")
    return "Each step of the check order refusing.", "§4.4, §6.1"


def rotated_original(s: Scenario):
    original = messages.batch(s.other.hab, s.requester.hab.pre,
                              [overtures.make(action("Introduce me"), {"to": ISSUEE}, u=nonce(30))],
                              stamp=s.clock.stamp(-60))
    orig = wire.parse(bytes(original))[0]
    s.other.hab.rotate()
    o = overtures.make(action("Accept an introduction"), {"from": s.other.hab.pre}, u=nonce(31),
                       triggeredBy={"said": orig.a["overtures"][0]["d"], "exn": orig.said})
    stream = s.other.kel() + s.requester.batch([o], nests=[original], stamp=s.clock.stamp())
    s.send(stream, "The original's signer rotated after signing, so the hop's batch is refused.")
    return "A passed-on message whose signer has since rotated.", "§4.4, §11"


def evidence(s: Scenario):
    s.learn(AUTHORITY)
    s.learn(LICENCE)
    authority = s.issuer
    root = authority.issue(AUTHORITY, {"region": "North"}, recipient=s.requester.hab.pre,
                           dt=s.clock.stamp(-86400))
    own = Issuer(s.requester.hab, nonce(901))
    leaf = own.issue(LICENCE, {"class": "B"}, recipient=ISSUEE, dt=s.clock.stamp(-3600),
                     edges={"authority": {"n": root.said, "s": AUTHORITY.said, "o": "I2I"}})
    o = revoke(40, evidence=[leaf.said])
    stream = authority.stream() + own.stream() + s.requester.batch(
        [o], nests=[own.nest(leaf), authority.nest(root)], stamp=s.clock.stamp(), with_kel=False)
    s.send(stream, "Each issuer's KEL then its TEL, the requester being the leaf's issuer, then "
                   "the batch with both links of the chain attached; the leaf's edge requires I2I.")
    return "An overture relying on a two-link credential chain.", "§4.3, §5.1, §6.1 step 8"


def evidence_refusals(s: Scenario):
    s.learn(AUTHORITY)
    iss = s.issuer
    r = s.requester
    first = iss.issue(AUTHORITY, {"region": "North"}, recipient=r.hab.pre, dt=s.clock.stamp(-60))
    s.send(r.batch([revoke(41, evidence=[first.said])], nests=[iss.nest(first)],
                   stamp=s.clock.stamp()),
           "The issuer's KEL and TEL were not sent, so the agent cannot check the credential yet.")
    s.tick(1)
    s.send(iss.stream() + r.batch([revoke(42, evidence=[first.said])], stamp=s.clock.stamp(),
                                  with_kel=False),
           "An evidence SAID with no ACDC attached.")
    s.tick(1)
    unknown = iss.issue(UNKNOWN, {}, dt=s.clock.stamp(-60))
    s.send(iss.stream() + r.batch([revoke(43, evidence=[unknown.said])], nests=[iss.nest(unknown)],
                                  stamp=s.clock.stamp(), with_kel=False),
           "A credential whose schema the agent was never given.")
    s.tick(1)
    bad = iss.issue(AUTHORITY, {"name": "no region"}, dt=s.clock.stamp(-60))
    s.send(iss.stream() + r.batch([revoke(44, evidence=[bad.said])], nests=[iss.nest(bad)],
                                  stamp=s.clock.stamp(), with_kel=False),
           "A credential that fails its own schema.")
    s.tick(1)
    iss.revoke(first, dt=s.clock.stamp(-1))
    s.send(iss.stream() + r.batch([revoke(45, evidence=[first.said])], nests=[iss.nest(first)],
                                  stamp=s.clock.stamp(), with_kel=False),
           "The same credential as the first exchange, now revoked.")
    return "Attached evidence that is missing, unverifiable or revoked.", "§6.1 step 8"


def under_threshold(hab, stream) -> bytes:
    """``stream``'s message re-signed with only the first of ``hab``'s keys."""
    serder = wire.parse(bytes(stream))[0].serder
    sigers = hab.sign(ser=serder.raw, indexed=True)[:1]
    est = hab.kever.lastEst
    tsg = (hab.kever.prefixer, Number(num=est.s), Diger(qb64=est.d), sigers)
    return bytes(eventing.messagize(serder, tsgs=[tsg], nested=True, gvrsn=Vrsn_2_0))


def tampered(stream: bytes) -> bytes:
    """``stream`` with one character of its last signature changed."""
    out = bytearray(stream)
    out[-20] = ord("B") if out[-20] == ord("A") else ord("A")
    return bytes(out)


def message_refusals(s: Scenario):
    r = s.requester
    s.send(r.batch([issue(50 + n) for n in range(20)], stamp=s.clock.stamp()),
           "Twenty overtures make a stream larger than this agent's maxSize of 4096 bytes.")
    s.send(r.kel(), "The requester's KEL alone, with no Overture message.")
    s.tick(1)
    s.send(r.poll([CREDENTIAL], stamp=s.clock.stamp()) + r.poll([ISSUEE], stamp=s.clock.stamp()),
           "Two Overture messages in one stream.")
    s.tick(1)
    serder = eventing.exchange(sender=r.hab.pre, receiver=s.principal, route=messages.route("poll"),
                               xid=CREDENTIAL, attributes={"version": "1.0", "saids": [CREDENTIAL]},
                               stamp=s.clock.stamp(), pvrsn=Vrsn_2_0, kind=Kinds.json)
    s.send(r.hab.endorse(serder=serder, nested=True, gvrsn=Vrsn_2_0),
           "A message whose x field is not empty.")
    s.tick(1)
    s.send(messages.status(r.hab, s.principal, [{"said": CREDENTIAL, "status": "unknown"}],
                           stamp=s.clock.stamp()), "A route a requester never sends.")
    s.tick(1)
    s.send(s.other.batch([issue(70)], stamp=s.clock.stamp(), with_kel=False),
           "A sender whose KEL the agent has never seen.")
    s.tick(1)
    s.send(tampered(r.poll([CREDENTIAL], stamp=s.clock.stamp())), "A signature that does not verify.")
    s.tick(1)
    old = r.poll([ISSUEE], stamp=s.clock.stamp())
    r.hab.rotate()
    s.send(r.kel() + old, "Signed before the requester rotated, and sent with the rotated KEL.")
    return "Each of steps 1 to 3 refusing.", "§4.4, §6.1"


def requesters(s: Scenario):
    ephemeral = s.party("vector-ephemeral", b"vector-ephemera0", transferable=False)
    o = issue(80)
    s.send(ephemeral.batch([o], stamp=s.clock.stamp(), with_kel=False),
           "A non-transferable requester needs no KEL; its signature is a receipt couple.",
           ephemeral)
    s.tick(1)
    multi = s.party("vector-multikey", b"vector-multikey0", icount=3, isith="2", ncount=3, nsith="2")
    s.send(multi.batch([issue(81)], stamp=s.clock.stamp()),
           "A requester with three keys and a threshold of two, signing with all three.", multi)
    s.tick(1)
    s.send(under_threshold(multi.hab, multi.poll([CREDENTIAL], stamp=s.clock.stamp())),
           "The same requester signing with one key, below its threshold.")
    return "Requesters other than a single-key transferable AID.", "§4.4, §6.10"


def starts_late(s: Scenario):
    o = issue(90, preconditions={"startBy": s.clock.stamp(10)})
    s.send(s.requester.batch([o], stamp=s.clock.stamp()), "Admitted, to start within ten seconds.")
    s.tick(20)
    s.send(s.requester.poll([o["d"]], stamp=s.clock.stamp()),
           "It did not start by startBy, so it expired.")
    s.tick(1)
    s.send(s.requester.batch([issue(91, preconditions={"startBy": s.clock.stamp(-1)})],
                             stamp=s.clock.stamp(), with_kel=False),
           "An overture whose startBy has already passed is not admitted, silently.")
    return "The startBy precondition.", "§6.3, §7"


def partial_batch(s: Scenario):
    good = revoke(95)
    unknown = overtures.make(CREDENTIAL, {}, u=nonce(96))
    s.send(s.requester.batch([good, unknown], stamp=s.clock.stamp()),
           "One overture names an action the agent does not know; only the other is receipted.")
    s.tick(1)
    s.send(s.requester.poll([good["d"], unknown["d"]], stamp=s.clock.stamp()),
           "The admitted one is declined with a reason; the refused one is unknown.")
    return "A batch refused in part, and a decline with a reason.", "§6.1, §6.3, §6.4"


SCENARIOS = {
    "admit-and-complete": (admit_and_complete, {}),
    "pending-then-complete": (pending_then_complete, {"actions": {
        "Issue a credential": {"after": 60, "results": [{"said": CREDENTIAL, "registry": SCHEMA}]}}}),
    "held-batch": (held_batch, {}),
    "revoke-and-reissue": (revoke_and_reissue, {"actions": {"Revoke a credential": {"after": 30}}}),
    "precluded": (precluded, {"actions": {"Revoke a credential": {"status": "declined"}}}),
    "resend": (resend, {}),
    "abort": (abort, {"actions": {"Issue a credential": {"after": 60}}}),
    "seen": (seen, {}),
    "pass-on": (pass_on, {}),
    "relationship-aid": (relationship_aid, {"actions": {"Create a relationship AID": {"make": "aid"}}}),
    "refusals": (refusals, {}),
    "rotated-original": (rotated_original, {}),
    "evidence": (evidence, {}),
    "evidence-refusals": (evidence_refusals, {}),
    "message-refusals": (message_refusals, {}, {"max_size": 4096}),
    "requesters": (requesters, {}),
    "starts-late": (starts_late, {"actions": {"Issue a credential": {"after": 60}}}),
    "partial-batch": (partial_batch, {"actions": {"Revoke a credential": {
        "status": "declined", "reason": "No such licence is on file."}}}),
}


def generate() -> dict[str, dict]:
    """Run every scenario with keripy's clock pinned to the scenario's own, for first-seen
    times in replayed KELs, and restore it afterwards."""
    out = {}
    wall = helping.nowUTC
    try:
        for name, (run, script, *settings) in SCENARIOS.items():
            clock = Clock()
            helping.nowUTC = clock
            with ExitStack() as stack:
                s = Scenario(stack, script, clock, settings[0] if settings else {})
                description, spec = run(s)
                out[name] = s.vector(description, spec)
    finally:
        helping.nowUTC = wall
    return out


def render(vector: dict) -> str:
    return json.dumps(vector, indent=2, ensure_ascii=True) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m overture.vectors")
    parser.add_argument("--out", type=Path, default=Path("vectors"))
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, vector in generate().items():
        (args.out / f"{name}.json").write_text(render(vector))
        print(f"{args.out / name}.json", file=sys.stdout)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
