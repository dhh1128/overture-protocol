"""The JSON Schemas for each route's `a` block (spec §5, §9; this.i 2uvl4uuz)."""

import copy

import pytest

from overture import schemas

SAID1 = "EAbcdefghijklmnopqrstuvwxyz0123456789_-ABCDE"
SAID2 = "EBbcdefghijklmnopqrstuvwxyz0123456789_-ABCDE"
SAID3 = "ECbcdefghijklmnopqrstuvwxyz0123456789_-ABCDE"
AID = "DKxy2sgzfplyr-tgwIxS19f2OchFHtLwPWD3v4oYimBx"
NONCE = "0AB3abcdefghijklmnopqrst"
T1 = "2026-10-15T17:05:00.000000+00:00"


def overture(**over):
    o = {"d": SAID1, "u": NONCE, "action": SAID2, "params": {}}
    o.update(over)
    return o


def batch(*overtures, **extra):
    a = {"version": "1.0", "overtures": list(overtures) or [overture()]}
    a.update(extra)
    return a


def ok(route, a):
    assert schemas.errors(route, a) == []


def bad(route, a):
    assert schemas.errors(route, a) != []


# --- batch -----------------------------------------------------------------

def test_spec_batch_example_validates():
    ok("batch", batch(
        overture(params={"credential": SAID3}),
        overture(d=SAID3, prereqs=[SAID1], purpose="Replace my lost license."),
    ))


def test_batch_with_every_optional_field_validates():
    ok("batch", batch(overture(
        prereqs=[SAID3],
        preconditions={"startBy": T1, "finishBy": T1, "signer": "principal",
                       "audience": {"aid": AID, "nonce": "anything at all"}},
        purpose="why",
        triggeredBy={"said": SAID3, "exn": SAID2},
        evidence=[SAID3],
    ), waitUntil=T1))


@pytest.mark.parametrize("field", ["d", "u", "action", "params"])
def test_overture_requires_its_four_fields(field):
    o = overture()
    del o[field]
    bad("batch", batch(o))


def test_batch_requires_at_least_one_overture():
    bad("batch", {"version": "1.0", "overtures": []})


def test_batch_requires_version():
    a = batch()
    del a["version"]
    bad("batch", a)


@pytest.mark.parametrize("version", ["1", "2.0", "1.0.0", "01.0", "1.01", 1.0])
def test_version_must_be_major_one_as_major_dot_minor(version):
    bad("batch", batch(version=version) | {"version": version})


def test_minor_versions_validate():
    ok("batch", batch() | {"version": "1.7"})


def test_unknown_fields_are_allowed_outside_closed_sets():
    ok("batch", batch(overture(futureField=1), futureTop=True))


def test_unknown_precondition_key_passes_shape_check():
    # Refused at check step 11 for not being understood, not at step 6 for shape.
    ok("batch", batch(overture(preconditions={"notYetDefined": 1})))


def test_signer_is_a_closed_set():
    bad("batch", batch(overture(preconditions={"signer": "anyone"})))


def test_audience_needs_aid_and_nonce():
    bad("batch", batch(overture(preconditions={"audience": {"aid": AID}})))
    bad("batch", batch(overture(preconditions={"audience": {"nonce": "n"}})))


def test_triggered_by_needs_said_and_exn():
    bad("batch", batch(overture(triggeredBy={"said": SAID3})))
    bad("batch", batch(overture(triggeredBy={"exn": SAID3})))


@pytest.mark.parametrize("said", ["", "notasaid", "E" + "a" * 10, 7])
def test_saids_are_qb64_digests(said):
    bad("batch", batch(overture(d=said)))
    bad("batch", batch(overture(action=said)))
    bad("batch", batch(overture(prereqs=[said])))


def test_nonce_must_be_a_128_bit_salt():
    bad("batch", batch(overture(u="0Ashort")))
    bad("batch", batch(overture(u=SAID1)))


@pytest.mark.parametrize("dt", ["2026-10-15", "2026-10-15T17:05:00Z", "yesterday"])
def test_times_use_keri_dt_form(dt):
    bad("batch", batch(waitUntil=dt))
    bad("batch", batch(overture(preconditions={"startBy": dt})))


def test_prereqs_and_evidence_are_nonempty_unique_lists():
    bad("batch", batch(overture(prereqs=[])))
    bad("batch", batch(overture(prereqs=[SAID3, SAID3])))
    bad("batch", batch(overture(evidence=[])))


def test_params_must_be_an_object():
    bad("batch", batch(overture(params=[])))


# --- receipt ---------------------------------------------------------------

def test_spec_receipt_example_validates():
    ok("receipt", {"version": "1.0", "receipts": [
        {"meaning": "admitted", "said": SAID1, "keptUntil": T1},
        {"meaning": "admitted", "said": SAID2, "keptUntil": T1},
    ], "nextPoll": T1})


def test_seen_receipt_validates_without_kept_until():
    ok("receipt", {"version": "1.0", "receipts": [{"meaning": "seen", "said": SAID1}]})


def test_admitted_requires_kept_until():
    bad("receipt", {"version": "1.0", "receipts": [{"meaning": "admitted", "said": SAID1}]})


def test_seen_forbids_kept_until():
    bad("receipt", {"version": "1.0", "receipts": [
        {"meaning": "seen", "said": SAID1, "keptUntil": T1}]})


def test_receipt_meaning_is_a_closed_set():
    bad("receipt", {"version": "1.0", "receipts": [
        {"meaning": "accepted", "said": SAID1, "keptUntil": T1}]})


def test_receipt_needs_at_least_one_receipt():
    bad("receipt", {"version": "1.0", "receipts": []})


# --- poll and abort --------------------------------------------------------

def test_spec_poll_example_validates():
    ok("poll", {"version": "1.0", "saids": [SAID1, SAID2], "waitUntil": T1})


def test_poll_needs_saids():
    bad("poll", {"version": "1.0", "saids": []})
    bad("poll", {"version": "1.0"})
    bad("poll", {"version": "1.0", "saids": [SAID1, SAID1]})


def test_spec_abort_example_validates():
    ok("abort", {"version": "1.0", "saids": [SAID2]})


def test_abort_carries_no_wait_until():
    bad("abort", {"version": "1.0", "saids": [SAID2], "waitUntil": T1})


# --- status ----------------------------------------------------------------

def test_spec_status_example_validates():
    ok("status", {"version": "1.0", "statuses": [
        {"said": SAID1, "status": "completed", "results": [{"said": SAID3}]},
        {"said": SAID2, "status": "pending"},
        {"said": SAID3, "status": "unknown"},
    ], "nextPoll": T1})


@pytest.mark.parametrize("status", ["completed", "declined", "expired", "failed",
                                    "aborted", "precluded"])
def test_every_outcome_may_carry_results_and_reason(status):
    ok("status", {"version": "1.0", "statuses": [
        {"said": SAID1, "status": status, "reason": "because",
         "results": [{"said": SAID3, "registry": SAID2},
                     {"aid": AID, "oobi": "http://example.com/oobi/" + AID}]}]})


@pytest.mark.parametrize("status", ["pending", "unknown"])
def test_results_only_with_an_outcome(status):
    bad("status", {"version": "1.0", "statuses": [
        {"said": SAID1, "status": status, "results": [{"said": SAID3}]}]})


def test_status_is_a_closed_set():
    bad("status", {"version": "1.0", "statuses": [{"said": SAID1, "status": "agreed"}]})


def test_a_result_is_an_artifact_or_an_identifier_not_both():
    bad("status", {"version": "1.0", "statuses": [{"said": SAID1, "status": "completed",
        "results": [{"said": SAID3, "aid": AID, "oobi": "http://x/"}]}]})
    bad("status", {"version": "1.0", "statuses": [{"said": SAID1, "status": "completed",
        "results": [{"aid": AID}]}]})
    bad("status", {"version": "1.0", "statuses": [{"said": SAID1, "status": "completed",
        "results": [{}]}]})


def test_status_needs_statuses():
    bad("status", {"version": "1.0", "statuses": []})


# --- the module ------------------------------------------------------------

def test_unknown_route_is_refused():
    with pytest.raises(KeyError):
        schemas.errors("teleport", {})


def test_errors_do_not_mutate_input():
    a = batch()
    before = copy.deepcopy(a)
    schemas.errors("batch", a)
    assert a == before


def test_errors_are_readable_sentences():
    errs = schemas.errors("batch", {"version": "1.0"})
    assert errs and all(isinstance(e, str) and e for e in errs)


def test_every_schema_is_valid_2020_12():
    for route in schemas.ROUTES:
        schemas.check_schema(route)


def test_routes_match_the_spec():
    assert set(schemas.ROUTES) == {"batch", "receipt", "poll", "abort", "status"}
