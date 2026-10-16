"""The agent's memory (spec §6.6; this.i 8fwdvgmg, 3yr7nvs7)."""

import datetime

import pytest

from overture.store import Record, Store

T0 = datetime.datetime(2026, 10, 15, 17, 0, tzinfo=datetime.UTC)
R = "EKY_ChXyrkgMvQ4U10--sOJv7oR9VJkOX1r-PSeCsFaZ"
S = "EBbcdefghijklmnopqrstuvwxyz0123456789_-ABCDE"


def record(said="EAbc", requester=R, **kwa):
    base = dict(requester=requester, said=said, major=1, admitted=T0,
                kept_until=T0 + datetime.timedelta(days=30), overture={"d": said},
                batch_exn="Ebatch", due=T0, plan={"status": "completed"})
    base.update(kwa)
    return Record(**base)


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "agent.sqlite")
    yield s
    s.close()


def test_an_admitted_overture_is_remembered_in_its_requesters_scope(store):
    store.admit(record())
    got = store.get(R, "EAbc")
    assert got.status == "pending" and got.admitted == T0 and got.plan == {"status": "completed"}
    assert store.get(S, "EAbc") is None


def test_memory_survives_reopening(tmp_path):
    s = Store(tmp_path / "a.sqlite")
    s.admit(record())
    s.close()
    s = Store(tmp_path / "a.sqlite")
    assert s.get(R, "EAbc").status == "pending"
    s.close()


def test_an_outcome_is_fixed_once_reported(store):
    store.admit(record())
    store.end(R, "EAbc", "completed", T0, results=[{"said": S}], reason=None)
    got = store.get(R, "EAbc")
    assert got.status == "completed" and got.results == [{"said": S}] and got.ended == T0
    with pytest.raises(ValueError, match="already ended"):
        store.end(R, "EAbc", "failed", T0)


def test_pending_lists_only_pending_overtures_of_a_requester(store):
    store.admit(record("E1"))
    store.admit(record("E2"))
    store.admit(record("E3", requester=S))
    store.end(R, "E2", "declined", T0)
    assert [r.said for r in store.pending(R)] == ["E1"]
    assert {r.said for r in store.pending()} == {"E1", "E3"}


def test_forgetting_removes_only_ended_overtures(store):
    store.admit(record("E1"))
    store.admit(record("E2"))
    store.end(R, "E1", "completed", T0)
    store.forget(R, ["E1", "E2", "E9"])
    assert store.get(R, "E1") is None and store.get(R, "E2") is not None


def test_expiring_drops_ended_records_past_kept_until(store):
    store.admit(record("E1", kept_until=T0))
    store.admit(record("E2", kept_until=T0))
    store.end(R, "E1", "completed", T0)
    store.expire(T0 + datetime.timedelta(seconds=1))
    assert store.get(R, "E1") is None and store.get(R, "E2") is not None


def test_status_reports_are_remembered_for_seen(store):
    store.report("Ereport", R, ["E1", "E2"])
    assert store.reported("Ereport", R) == ["E1", "E2"]
    assert store.reported("Ereport", S) == []
    assert store.reported("Eother", R) == []


def test_accepted_messages_are_remembered_for_replay(store):
    assert store.accept_once("Emsg", T0)
    assert not store.accept_once("Emsg", T0)
    store.prune_accepted(T0 + datetime.timedelta(seconds=1))
    assert store.accept_once("Emsg", T0)
