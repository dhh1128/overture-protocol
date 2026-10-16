"""The stand-in agent and its HTTP binding (spec §10; this.i 3yr7nvs7)."""

import datetime
import json

import pytest
from falcon import testing
from keri.app import habbing
from keri.core.signing import Salter

from overture import catalog, engine, messages, overtures
from overture.requester import Requester, admitted, statuses
from overture.standin import ScriptPolicy, StandIn, load_script
from overture.standin.http import app

ISSUE = catalog.by_title("Issue a credential")["$id"]
REL = catalog.by_title("Create a relationship AID")["$id"]
SCHEMA = "EAbcdefghijklmnopqrstuvwxyz0123456789_-ABCDE"
URL = "http://agent.example:5642"


class Clock:
    def __init__(self):
        self.t = datetime.datetime.now(datetime.UTC).replace(microsecond=0)

    def __call__(self):
        return self.t

    def stamp(self, s=0):
        return engine.stamp(self.t + datetime.timedelta(seconds=s))


@pytest.fixture
def setup(tmp_path, parties):
    clock = Clock()
    script = {"actions": {"Issue a credential": {"after": 10, "results": [{"said": SCHEMA}]},
                          "Revoke a credential": {"admit": False},
                          REL: {"make": "aid"}}}
    with habbing.openHby(name="standin", temp=True, salt=Salter(raw=b"standin-salt-000").qb64) as hby:
        s = StandIn(hby, URL, script, tmp_path / "s.sqlite", clock=clock)
        slept = []

        def sleep(seconds):
            slept.append(seconds)
            clock.t += datetime.timedelta(seconds=5)

        client = testing.TestClient(app(s, sleep=sleep, hold_cap=datetime.timedelta(seconds=60)))
        r = Requester(parties["requester"], s.principal.pre)
        r.learn(client.simulate_get(f"/oobi/{s.principal.pre}/agent/{s.agent.pre}").content)
        yield dict(s=s, client=client, r=r, clock=clock, slept=slept)
        s.close()


def post(setup, stream, **headers):
    return setup["client"].simulate_post("/", body=stream,
                                         headers={"Content-Type": "application/cesr", **headers})


def issue():
    return overtures.make(ISSUE, {"schema": SCHEMA, "issuee": "D" + "A" * 43})


def test_the_oobi_publishes_the_agent_in_the_agent_role(setup):
    s, r = setup["s"], setup["r"]
    assert s.oobi() == f"{URL}/oobi/{s.principal.pre}/agent/{s.agent.pre}"
    assert s.principal.pre in r.kvy.kevers and s.agent.pre in r.kvy.kevers
    resp = setup["client"].simulate_get(f"/oobi/{s.principal.pre}")
    assert b"/end/role/add" in resp.content and b"/loc/scheme" in resp.content
    assert b'"role":"agent"' in resp.content and URL.encode() in resp.content


def test_an_unknown_oobi_is_not_found(setup):
    assert setup["client"].simulate_get("/oobi/EUnknown").status_code == 404


def test_a_batch_is_answered_inline_with_its_receipt(setup):
    o = issue()
    resp = post(setup, setup["r"].batch([o], stamp=setup["clock"].stamp()))
    assert resp.status_code == 200 and resp.headers["content-type"] == "application/cesr"
    assert o["d"] in admitted(setup["r"].read(resp.content, agents={setup["s"].agent.pre}))


def test_a_silent_refusal_is_204(setup):
    revoke = overtures.make(catalog.by_title("Revoke a credential")["$id"], {"credential": SCHEMA})
    resp = post(setup, setup["r"].batch([revoke], stamp=setup["clock"].stamp()))
    assert resp.status_code == 204 and resp.content == b""


def test_an_unsupported_major_is_400_problem_details(setup):
    stream = setup["r"].kel() + bytes(messages.build(
        setup["r"].hab, "poll", setup["s"].principal.pre, {"saids": [SCHEMA], "version": "3.1"},
        stamp=setup["clock"].stamp()))
    resp = post(setup, stream)
    assert resp.status_code == 400
    assert resp.headers["content-type"] == "application/problem+json"
    assert resp.json["supportedMajors"] == [1] and resp.json["type"] == "about:blank"


def test_the_attachment_header_form_is_refused(setup):
    resp = post(setup, b"{}", **{"CESR-ATTACHMENT": "-AAB"})
    assert resp.status_code == 400


def test_a_batch_with_wait_until_is_held_then_answered_with_the_outcome(setup):
    o = issue()
    resp = post(setup, setup["r"].batch([o], waitUntil=setup["clock"].stamp(30),
                                        stamp=setup["clock"].stamp()))
    msgs = setup["r"].read(resp.content)
    assert [m.route for m in msgs] == ["/overture/receipt", "/overture/status"]
    assert statuses(msgs)[o["d"]]["status"] == "completed"
    assert setup["slept"] == [0.25, 0.25]


def test_a_held_poll_is_answered_when_the_time_is_reached(setup):
    o = issue()
    post(setup, setup["r"].batch([o], stamp=setup["clock"].stamp()))
    resp = post(setup, setup["r"].poll([o["d"]], waitUntil=setup["clock"].stamp(4),
                                       stamp=setup["clock"].stamp(1)))
    assert statuses(setup["r"].read(resp.content))[o["d"]]["status"] == "pending"


def test_a_relationship_aid_is_real_and_seals_the_overture(setup):
    o = overtures.make(REL, {})
    post(setup, setup["r"].batch([o], stamp=setup["clock"].stamp()))
    resp = post(setup, setup["r"].poll([o["d"]], stamp=setup["clock"].stamp(1)))
    (result,) = statuses(setup["r"].read(resp.content))[o["d"]]["results"]
    assert result["oobi"] == f"{URL}/oobi/{result['aid']}"
    kel = setup["client"].simulate_get(f"/oobi/{result['aid']}").content
    setup["r"].learn(kel)
    icp = setup["r"].kvy.kevers[result["aid"]].serder
    assert icp.ked["a"] == [{"d": o["d"]}]


def test_the_script_falls_back_to_its_default():
    policy = ScriptPolicy({"default": {"status": "declined", "reason": "No."}})
    plan = policy.plan("E", {"d": "E"}, {"$id": "Ex", "title": "Anything"})
    assert plan.status == "declined" and plan.reason == "No." and plan.after == datetime.timedelta(0)


def test_a_script_loads_from_a_file_or_is_empty(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"default": {"admit": False}}))
    assert load_script(path) == {"default": {"admit": False}}
    assert load_script(None) == {}


def test_the_command_starts_a_stand_in_and_keeps_its_identity(tmp_path, capsys):
    from overture.standin import cli
    served = []
    data = tmp_path / "standin"
    cli.main(["--data", str(data), "--port", "5999"], run=lambda api, h, p: served.append((h, p)))
    first = capsys.readouterr().out
    cli.main(["--data", str(data), "--url", "https://agent.example"], run=lambda *a: None)
    second = capsys.readouterr().out
    assert served == [("127.0.0.1", 5999)]
    assert first.splitlines()[:2] == second.splitlines()[:2]
    assert "http://127.0.0.1:5999/oobi/" in first and "https://agent.example/oobi/" in second


def test_the_salt_and_its_directory_are_owner_only(tmp_path):
    import os
    from overture.standin import cli
    data = tmp_path / "standin"
    cli.main(["--data", str(data)], run=lambda *a: None)
    assert os.stat(data).st_mode & 0o777 == 0o700
    assert os.stat(data / "salt").st_mode & 0o777 == 0o600


def test_an_existing_salt_is_tightened_to_owner_only(tmp_path):
    import os
    from overture.standin import cli
    (tmp_path / "salt").write_text("0AAAAAAAAAAAAAAAAAAAAAAA")
    os.chmod(tmp_path / "salt", 0o640)
    assert cli.salt(tmp_path) == "0AAAAAAAAAAAAAAAAAAAAAAA"
    assert os.stat(tmp_path / "salt").st_mode & 0o777 == 0o600


def test_the_script_declines_audience_since_no_entry_can_bind_it_yet():
    policy = ScriptPolicy({})
    o = {"d": "E", "preconditions": {"audience": {"aid": "D" + "A" * 43, "nonce": "n"}}}
    assert policy.plan("E", o, {"$id": "Ex", "title": "Anything"}) is None
    assert ScriptPolicy({"default": {"audience": True}}).plan("E", o, {"$id": "Ex", "title": "x"})


def test_the_command_loads_the_credential_schemas_it_is_given(tmp_path, capsys):
    from overture.issuing import schema
    from overture.standin import cli
    schemer = schema("Licence")
    folder = tmp_path / "schemas"
    folder.mkdir()
    (folder / "licence.json").write_bytes(schemer.raw)
    (folder / "notes.txt").write_text("not a schema")
    known = []
    cli.main(["--data", str(tmp_path / "s"), "--schemas", str(folder)],
             run=lambda api, h, p: known.append(api))
    out = capsys.readouterr().out
    assert f"Schema    {schemer.said}" in out
