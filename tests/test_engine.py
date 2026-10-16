"""The agent's engine, end to end through the requester's helper (spec §6)."""

import datetime

import pytest
from keri.core import eventing
from keri.kering import Kinds, Vrsn_2_0

from overture import catalog, engine, errors, messages, overtures, wire
from overture.engine import Agent, Plan
from overture.requester import Requester, admitted, reports, statuses
from overture.store import Record, Store

ISSUE = catalog.by_title("Issue a credential")["$id"]
REVOKE = catalog.by_title("Revoke a credential")["$id"]
SCHEMA = "EAbcdefghijklmnopqrstuvwxyz0123456789_-ABCDE"
CRED = "EBbcdefghijklmnopqrstuvwxyz0123456789_-ABCDE"


class Clock:
    def __init__(self):
        self.t = datetime.datetime.now(datetime.UTC).replace(microsecond=0)

    def __call__(self):
        return self.t

    def tick(self, seconds):
        self.t += datetime.timedelta(seconds=seconds)

    def stamp(self, offset=0):
        return engine.stamp(self.t + datetime.timedelta(seconds=offset))


class Script:
    """A policy that admits everything and plans per action, unless told otherwise."""

    def __init__(self):
        self.plans = {}
        self.refuse = set()

    def plan(self, requester, overture, entry):
        if entry["$id"] in self.refuse:
            return None
        return self.plans.get(entry["$id"], Plan())


@pytest.fixture
def world(parties, tmp_path):
    clock = Clock()
    script = Script()
    store = Store(tmp_path / "agent.sqlite")
    agent = Agent(parties["agent"], parties["principal"].pre, store, script, clock=clock)
    r = Requester(parties["requester"], parties["principal"].pre)
    r.learn(bytes(parties["agent"].replay()))
    yield dict(eng=agent, r=r, clock=clock, script=script, store=store, **parties)
    agent.close()
    store.close()


def issue(**kwa):
    return overtures.make(ISSUE, {"schema": SCHEMA, "issuee": "D" + "A" * 43}, **kwa)


def revoke(**kwa):
    return overtures.make(REVOKE, {"credential": CRED}, **kwa)


def send(w, stream, requester=None):
    ans = w["eng"].receive(stream)
    reader = requester or w["r"]
    msgs = [m for s in ans.streams for m in reader.read(s, agents={w["eng"].hab.pre})]
    return ans, msgs


def poll(w, saids, requester=None, **kwa):
    requester = requester or w["r"]
    return send(w, requester.poll(saids, stamp=w["clock"].stamp(), **kwa), requester)


# --- admission and outcomes --------------------------------------------------------

def test_an_admitted_overture_gets_a_receipt_and_later_its_outcome(world):
    o = issue()
    ans, msgs = send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    got = admitted(msgs)[o["d"]]
    assert got["admittedAt"] == world["clock"].stamp()
    assert got["keptUntil"] == world["clock"].stamp(30 * 86400)
    _, msgs = poll(world, [o["d"]])
    assert statuses(msgs)[o["d"]] == {"said": o["d"], "status": "completed", "results": []}


def test_an_overture_stays_pending_until_its_plan_is_due(world):
    world["script"].plans[ISSUE] = Plan(after=datetime.timedelta(seconds=60),
                                        results=[{"said": CRED}], reason="As asked.")
    o = issue()
    _, msgs = send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    assert msgs[0].a["nextPoll"] == world["clock"].stamp(61)
    _, msgs = poll(world, [o["d"]])
    assert statuses(msgs)[o["d"]]["status"] == "pending" and "nextPoll" in msgs[0].a
    world["clock"].tick(60)
    _, msgs = poll(world, [o["d"]])
    assert statuses(msgs)[o["d"]] == {"said": o["d"], "status": "completed",
                                      "results": [{"said": CRED}], "reason": "As asked."}
    assert "nextPoll" not in msgs[0].a


def test_refusal_costs_nothing_and_says_nothing(world):
    world["script"].refuse.add(ISSUE)
    o = issue()
    ans, msgs = send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    assert ans.streams == [] and ans.refusal is None
    assert world["store"].get(world["requester"].pre, o["d"]) is None
    _, msgs = poll(world, [o["d"]])
    assert statuses(msgs)[o["d"]]["status"] == "unknown"


@pytest.mark.parametrize("o, code", [
    (overtures.make(CRED, {}), errors.ACTION_UNKNOWN),
    (overtures.make(ISSUE, {"schema": SCHEMA}), errors.PARAMS_INVALID),
    (overtures.make(REVOKE, {"credential": CRED}, preconditions={"colour": "red"}),
     errors.PRECONDITION_UNKNOWN),
])
def test_an_overture_the_agent_cannot_read_is_refused_alone(world, o, code):
    good = revoke()
    ans, msgs = send(world, world["r"].batch([o, good], stamp=world["clock"].stamp()))
    assert set(admitted(msgs)) == {good["d"]}
    ans, _ = send(world, world["r"].batch([o], stamp=world["clock"].stamp(1)))
    assert ans.refusal.code is code and ans.streams == []


def test_a_start_by_already_past_is_not_admitted(world):
    o = issue(preconditions={"startBy": world["clock"].stamp(-1)})
    ans, msgs = send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    assert msgs == []


def test_a_start_by_that_passes_before_acting_ends_expired(world):
    world["script"].plans[ISSUE] = Plan(after=datetime.timedelta(seconds=60))
    o = issue(preconditions={"startBy": world["clock"].stamp(30)})
    send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    world["clock"].tick(31)
    _, msgs = poll(world, [o["d"]])
    assert statuses(msgs)[o["d"]]["status"] == "expired"


# --- batches and dependencies --------------------------------------------------------

def test_revoke_and_reissue_acts_in_order(world):
    world["script"].plans[REVOKE] = Plan(after=datetime.timedelta(seconds=10))
    first = revoke()
    second = issue(prereqs=[first["d"]])
    _, msgs = send(world, world["r"].batch([first, second], stamp=world["clock"].stamp()))
    assert set(admitted(msgs)) == {first["d"], second["d"]}
    _, msgs = poll(world, [first["d"], second["d"]])
    assert [s["status"] for s in msgs[0].a["statuses"]] == ["pending", "pending"]
    world["clock"].tick(10)
    _, msgs = poll(world, [first["d"], second["d"]])
    assert [s["status"] for s in msgs[0].a["statuses"]] == ["completed", "completed"]


def test_a_failed_prerequisite_precludes_its_dependant_only(world):
    world["script"].plans[REVOKE] = Plan(status="declined")
    first, second, other = revoke(), issue(), issue()
    second = issue(prereqs=[first["d"]])
    send(world, world["r"].batch([first, second, other], stamp=world["clock"].stamp()))
    _, msgs = poll(world, [first["d"], second["d"], other["d"]])
    assert [s["status"] for s in msgs[0].a["statuses"]] == ["declined", "precluded", "completed"]


def test_a_prerequisite_may_be_admitted_earlier_from_the_same_requester(world):
    world["script"].plans[REVOKE] = Plan(after=datetime.timedelta(seconds=5))
    first = revoke()
    send(world, world["r"].batch([first], stamp=world["clock"].stamp()))
    second = issue(prereqs=[first["d"]])
    _, msgs = send(world, world["r"].batch([second], stamp=world["clock"].stamp(1)))
    assert second["d"] in admitted(msgs)


def test_a_prerequisite_from_another_requester_makes_the_batch_malformed(world):
    first = revoke()
    send(world, world["r"].batch([first], stamp=world["clock"].stamp()))
    s = Requester(world["stranger"], world["principal"].pre)
    ans, _ = send(world, s.batch([issue(prereqs=[first["d"]])], stamp=world["clock"].stamp(1)), s)
    assert ans.refusal.code is errors.PREREQ_UNKNOWN


def test_a_refused_prerequisite_in_the_batch_refuses_its_dependant(world):
    world["script"].refuse.add(REVOKE)
    bad = overtures.make(CRED, {})
    first, second = bad, issue(prereqs=[bad["d"]])
    ans, msgs = send(world, world["r"].batch([first, second], stamp=world["clock"].stamp()))
    assert msgs == [] and ans.refusal.code is errors.ACTION_UNKNOWN


def test_a_duplicate_overture_makes_the_batch_malformed(world):
    o = issue()
    ans, _ = send(world, world["r"].batch([o, o], stamp=world["clock"].stamp()))
    assert ans.refusal.code is errors.DUPLICATE


def test_one_bad_said_refuses_the_whole_batch(world):
    good, bad = issue(), dict(issue(), purpose="changed after hashing")
    ans, msgs = send(world, world["r"].batch([good, bad], stamp=world["clock"].stamp()))
    assert ans.refusal.code is errors.SAID_MISMATCH and msgs == []
    assert world["store"].get(world["requester"].pre, good["d"]) is None


# --- resends and memory --------------------------------------------------------------

def test_a_resend_repeats_the_original_admission(world):
    o = issue()
    _, first = send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    world["clock"].tick(5)
    _, again = send(world, world["r"].batch([o], stamp=world["clock"].stamp(), with_kel=False))
    assert admitted(again)[o["d"]] == admitted(first)[o["d"]]


def test_receipts_with_different_admission_times_are_separate_messages(world):
    old = issue()
    send(world, world["r"].batch([old], stamp=world["clock"].stamp()))
    world["clock"].tick(5)
    new = issue()
    _, msgs = send(world, world["r"].batch([old, new], stamp=world["clock"].stamp()))
    assert [m.ked["dt"] for m in msgs] == [world["clock"].stamp(-5), world["clock"].stamp()]


def test_a_resend_under_another_major_version_is_malformed(world):
    o = issue()
    t = world["clock"]()
    world["store"].admit(Record(requester=world["requester"].pre, said=o["d"], major=2,
                                admitted=t, kept_until=t, overture=o, batch_exn="E",
                                due=t, plan={"status": "completed"}))
    ans, _ = send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    assert ans.refusal.code is errors.MAJOR_CHANGED


def test_seen_lets_the_agent_forget_but_keeps_a_pending_dependants_prerequisite(world):
    world["script"].plans[ISSUE] = Plan(after=datetime.timedelta(seconds=60))
    first = revoke()
    second = issue(prereqs=[first["d"]])
    lone = revoke()
    send(world, world["r"].batch([first, second, lone], stamp=world["clock"].stamp()))
    _, msgs = poll(world, [first["d"], lone["d"]])
    ans, _ = send(world, world["r"].seen(reports(msgs)[0], stamp=world["clock"].stamp()))
    assert ans.streams == [] and ans.refusal is None
    world["clock"].tick(1)
    _, msgs = poll(world, [first["d"], lone["d"]])
    assert [s["status"] for s in msgs[0].a["statuses"]] == ["completed", "unknown"]


def test_seen_of_an_unknown_report_forgets_nothing(world):
    o = revoke()
    send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    send(world, world["r"].seen(CRED, stamp=world["clock"].stamp()))
    _, msgs = poll(world, [o["d"]])
    assert statuses(msgs)[o["d"]]["status"] == "completed"


def test_an_outcome_is_forgotten_after_kept_until(world):
    o = revoke()
    send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    world["clock"].tick(30 * 86400 + 1)
    _, msgs = poll(world, [o["d"]])
    assert statuses(msgs)[o["d"]]["status"] == "unknown"


@pytest.mark.parametrize("receipt", [
    {"meaning": "admitted", "said": CRED, "keptUntil": "2026-10-15T17:05:00.000000+00:00"},
])
def test_a_requester_may_sign_only_seen(world, receipt):
    stream = world["r"].kel() + bytes(messages.receipt(world["requester"], world["principal"].pre, [receipt],
                                    stamp=world["clock"].stamp()))
    ans, _ = send(world, stream)
    assert ans.refusal.code is errors.MALFORMED


def test_a_requester_receipt_carries_no_next_poll(world):
    stream = world["r"].kel() + bytes(messages.receipt(world["requester"], world["principal"].pre,
                                    [{"meaning": "seen", "said": CRED}],
                                    nextPoll=world["clock"].stamp(), stamp=world["clock"].stamp()))
    ans, _ = send(world, stream)
    assert ans.refusal.code is errors.MALFORMED


# --- visibility, aborts and waiting --------------------------------------------------

def test_only_the_sender_sees_an_overtures_status(world):
    o = revoke()
    send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    s = Requester(world["stranger"], world["principal"].pre)
    s.learn(bytes(world["eng"].hab.replay()))
    world["eng"].receive(s.kel())
    _, msgs = poll(world, [o["d"]], requester=s)
    assert statuses(msgs)[o["d"]]["status"] == "unknown"


def test_an_abort_ends_a_pending_overture_and_not_an_ended_one(world):
    world["script"].plans[ISSUE] = Plan(after=datetime.timedelta(seconds=60))
    pending, done = issue(), revoke()
    send(world, world["r"].batch([pending, done], stamp=world["clock"].stamp()))
    _, msgs = send(world, world["r"].abort([pending["d"], done["d"]], stamp=world["clock"].stamp()))
    assert [s["status"] for s in msgs[0].a["statuses"]] == ["aborted", "completed"]


def test_a_batch_with_wait_until_can_be_held_for_its_outcome(world):
    world["script"].plans[ISSUE] = Plan(after=datetime.timedelta(seconds=10))
    o = issue()
    ans, _ = send(world, world["r"].batch([o], waitUntil=world["clock"].stamp(30),
                                          stamp=world["clock"].stamp()))
    assert ans.wait.saids == [o["d"]]
    assert not world["eng"].has_news(ans.wait)
    world["clock"].tick(10)
    assert world["eng"].has_news(ans.wait)


def test_a_poll_with_wait_until_is_held_until_news_or_time(world):
    world["script"].plans[ISSUE] = Plan(after=datetime.timedelta(seconds=100))
    o = issue()
    send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    ans, msgs = poll(world, [o["d"]], waitUntil=world["clock"].stamp(30))
    assert msgs == [] and ans.wait is not None
    world["clock"].tick(30)
    assert world["eng"].has_news(ans.wait)


def test_a_poll_with_wait_until_and_news_is_answered_at_once(world):
    o = revoke()
    send(world, world["r"].batch([o], stamp=world["clock"].stamp()))
    _, msgs = poll(world, [o["d"]], waitUntil=world["clock"].stamp(30))
    assert statuses(msgs)[o["d"]]["status"] == "completed"


# --- message-level refusals ------------------------------------------------------------

def refusal(world, stream):
    return world["eng"].receive(stream).refusal.code


def test_a_message_to_another_principal_is_refused(world):
    other = Requester(world["requester"], world["stranger"].pre)
    assert refusal(world, other.batch([issue()], stamp=world["clock"].stamp())) is errors.WRONG_PRINCIPAL


def test_an_unsupported_major_version_is_reported_as_such(world):
    stream = world["r"].kel() + bytes(messages.build(
        world["requester"], "batch", world["principal"].pre,
        {"overtures": [issue()], "version": "2.0"}, stamp=world["clock"].stamp()))
    ans = world["eng"].receive(stream)
    assert ans.unsupported_major and "1" in ans.refusal.detail


@pytest.mark.parametrize("version", [None, "one", 1])
def test_a_missing_or_garbled_version_is_a_shape_failure(world, version):
    a = {"overtures": [issue()], "version": version}
    if version is None:
        del a["version"]
    serder = eventing.exchange(sender=world["requester"].pre, receiver=world["principal"].pre,
                               route="/overture/batch", attributes=a, stamp=world["clock"].stamp(),
                               pvrsn=Vrsn_2_0, kind=Kinds.json)
    stream = world["r"].kel() + bytes(world["requester"].endorse(serder=serder, nested=True,
                                                                 gvrsn=Vrsn_2_0))
    assert refusal(world, stream) is errors.SHAPE


def test_a_shape_failure_is_refused(world):
    stream = world["r"].kel() + bytes(messages.build(
        world["requester"], "poll", world["principal"].pre, {"saids": []},
        stamp=world["clock"].stamp()))
    assert refusal(world, stream) is errors.SHAPE


def test_a_stale_message_is_refused(world):
    assert refusal(world, world["r"].batch([issue()], stamp=world["clock"].stamp(-301))) is errors.NOT_FRESH


def test_a_replayed_message_is_refused(world):
    stream = world["r"].batch([issue()], stamp=world["clock"].stamp())
    world["eng"].receive(stream)
    assert refusal(world, stream) is errors.REPLAYED


def test_an_oversized_stream_is_refused_before_parsing(world):
    world["eng"].max_size = 10
    assert refusal(world, world["r"].batch([issue()])) is errors.TOO_LARGE


def test_a_stream_without_an_overture_message_is_refused(world):
    assert refusal(world, world["r"].kel()) is errors.NO_MESSAGE
    assert refusal(world, b"not cesr at all") is errors.NO_MESSAGE


def test_a_stream_that_does_not_parse_is_refused(world, monkeypatch):
    def broken(*a, **k):
        raise ValueError("boom")
    monkeypatch.setattr(wire, "parse", broken)
    assert refusal(world, world["r"].kel()) is errors.MALFORMED


def test_two_overture_messages_in_one_stream_are_refused(world):
    stream = world["r"].batch([issue()], stamp=world["clock"].stamp()) + world["r"].poll(
        [CRED], stamp=world["clock"].stamp())
    assert refusal(world, stream) is errors.MALFORMED


def test_a_route_the_agent_does_not_answer_is_refused(world):
    stream = world["r"].kel() + bytes(messages.status(world["requester"], world["principal"].pre,
                                                      [{"said": CRED, "status": "unknown"}]))
    assert refusal(world, stream) is errors.ROUTE_UNSUPPORTED


def test_an_exchange_id_or_prior_makes_the_message_malformed(world):
    serder = eventing.exchange(sender=world["requester"].pre, receiver=world["principal"].pre,
                               route="/overture/poll", xid=CRED,
                               attributes={"version": "1.0", "saids": [CRED]},
                               stamp=world["clock"].stamp(), pvrsn=Vrsn_2_0, kind=Kinds.json)
    stream = world["r"].kel() + bytes(world["requester"].endorse(serder=serder, nested=True,
                                                                 gvrsn=Vrsn_2_0))
    assert refusal(world, stream) is errors.MALFORMED


def test_a_non_transferable_requester_is_served(world):
    e = Requester(world["ephemeral"], world["principal"].pre)
    e.learn(bytes(world["eng"].hab.replay()))
    o = revoke()
    _, msgs = send(world, e.batch([o], stamp=world["clock"].stamp(), with_kel=False), e)
    assert o["d"] in admitted(msgs)


# --- passing an overture on ----------------------------------------------------------------

def hop(world, original_stream, original_sender, said=None, exn=None, rotate=False):
    """The stranger sent original_stream; the requester passes one of its overtures on."""
    orig = wire.parse(bytes(original_stream))[0]
    o = overtures.make(REVOKE, {"credential": CRED}, triggeredBy={
        "said": said or orig.a["overtures"][0]["d"], "exn": exn or orig.said})
    if rotate:
        original_sender.rotate()
    head = bytes(original_sender.replay())
    return o, head + world["r"].batch([o], nests=[original_stream], stamp=world["clock"].stamp())


def test_a_hop_attaches_the_original_and_is_admitted(world):
    s = world["stranger"]
    original = messages.batch(s, world["requester"].pre, [issue()], stamp=world["clock"].stamp(-3600))
    o, stream = hop(world, original, s)
    _, msgs = send(world, stream)
    assert o["d"] in admitted(msgs)


@pytest.mark.parametrize("which", ["said", "exn"])
def test_a_trigger_that_does_not_match_the_attachment_is_malformed(world, which):
    s = world["stranger"]
    original = messages.batch(s, world["requester"].pre, [issue()], stamp=world["clock"].stamp())
    _, stream = hop(world, original, s, **{which: CRED})
    assert refusal(world, stream) is errors.TRIGGER_MISMATCH


def test_an_attached_message_whose_signer_rotated_is_refused(world):
    s = world["stranger"]
    original = messages.batch(s, world["requester"].pre, [issue()], stamp=world["clock"].stamp())
    _, stream = hop(world, original, s, rotate=True)
    assert refusal(world, stream) is errors.ATTACHED_INVALID


def test_an_attached_overture_with_a_bad_said_is_refused(world):
    s = world["stranger"]
    original = messages.batch(s, world["requester"].pre, [dict(issue(), purpose="x")],
                              stamp=world["clock"].stamp())
    _, stream = hop(world, original, s)
    assert refusal(world, stream) is errors.SAID_MISMATCH


def test_an_attached_message_of_an_unsupported_version_is_refused(world):
    s = world["stranger"]
    original = messages.build(s, "batch", world["requester"].pre,
                              {"overtures": [issue()], "version": "9.0"}, stamp=world["clock"].stamp())
    _, stream = hop(world, original, s)
    assert refusal(world, stream) is errors.VERSION_UNSUPPORTED


def test_an_attached_key_event_is_not_judged_as_a_message(world):
    s = world["stranger"]
    icp = s.kever.serder
    sigers = s.sign(ser=icp.raw, indexed=True)
    nested_icp = eventing.messagize(icp, sigers=sigers, nested=True, gvrsn=Vrsn_2_0)
    o = revoke()
    stream = world["r"].batch([o], nests=[nested_icp], stamp=world["clock"].stamp())
    _, msgs = send(world, stream)
    assert o["d"] in admitted(msgs)
