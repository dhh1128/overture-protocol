"""The HTTP binding mounted in a keripy host: keripy's HttpEnd, extended (spec §10; tick 4aqd)."""

import datetime
import http.client
import socket
import threading

import falcon
from falcon import testing
from keri.app import httping, indirecting

from overture import overtures
from overture.engine import Plan
from overture.http import HttpEnd
from overture.requester import admitted, statuses

from test_engine import ISSUE, SCHEMA, issue, world  # noqa: F401


def test_a_whole_stream_with_an_overture_is_answered_inline(world):
    end = HttpEnd(world["eng"], rxbs=bytearray())
    client = testing.TestClient(_app(end))
    o = issue()
    resp = client.simulate_post("/", body=world["r"].batch([o], stamp=world["clock"].stamp()),
                                headers={"Content-Type": "application/cesr"})
    assert resp.status_code == 200
    assert o["d"] in admitted(world["r"].read(resp.content))
    assert end.rxbs == bytearray()


def test_a_whole_stream_without_an_overture_is_queued_for_the_hosts_parser(world):
    end = HttpEnd(world["eng"], rxbs=bytearray())
    kel = world["r"].kel()
    resp = testing.TestClient(_app(end)).simulate_post("/", body=kel)
    assert resp.status_code == 204 and bytes(end.rxbs) == kel


def test_the_attachment_header_form_goes_to_keripy_as_before(world):
    end = HttpEnd(world["eng"], rxbs=bytearray())
    icp = world["requester"].kever.serder
    attachments = world["r"].kel()[icp.size:]
    req = testing.create_req(method="POST", path="/", body=bytes(icp.raw), headers={
        "Content-Type": httping.CESR_CONTENT_TYPE,
        httping.CESR_ATTACHMENT_HEADER: attachments.decode()})
    resp = falcon.Response()
    end.on_post(req, resp)  # keripy's own 204 sets Content-Type, which falcon's linter rejects
    assert resp.status == falcon.HTTP_204
    assert bytes(end.rxbs) == bytes(icp.raw) + attachments


def _app(end) -> falcon.App:
    api = falcon.App()
    api.add_route("/", end)
    return api


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_under_keripys_hio_server_a_held_poll_does_not_block_other_requests(world):
    """keripy serves HTTP from one thread; a held answer must yield, not sleep."""
    port = _free_port()
    end = HttpEnd(world["eng"], rxbs=bytearray(), sleep=None,
                  hold_cap=datetime.timedelta(seconds=60))
    server = indirecting.createHttpServer("127.0.0.1", port, _app(end))
    assert server.reopen()
    r, clock = world["r"], world["clock"]
    pending = overtures.make(ISSUE, {"schema": SCHEMA, "issuee": "D" + "B" * 43})
    world["script"].plans[ISSUE] = Plan(after=datetime.timedelta(seconds=30))
    answers = {}

    def post(name, body):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("POST", "/", body=body, headers={"Content-Type": "application/cesr"})
        resp = c.getresponse()
        answers[name] = (resp.status, resp.read())
        c.close()

    def serve_until(done):
        for _ in range(20000):
            server.service()
            if done():
                return
        raise AssertionError("the server did not answer")

    try:
        first = threading.Thread(target=post, args=("batch", r.batch([pending], stamp=clock.stamp())))
        first.start()
        serve_until(lambda: "batch" in answers)
        first.join()
        held = threading.Thread(target=post, args=("held", r.poll(
            [pending["d"]], waitUntil=clock.stamp(40), stamp=clock.stamp())))
        held.start()
        for _ in range(200):
            server.service()
        assert "held" not in answers
        clock.tick(1)
        other = threading.Thread(target=post, args=("other", r.poll([pending["d"]], stamp=clock.stamp())))
        other.start()
        serve_until(lambda: "other" in answers)
        other.join()
        assert "held" not in answers
        clock.tick(30)
        serve_until(lambda: "held" in answers)
        held.join()
    finally:
        server.close()
    assert statuses(r.read(answers["other"][1]))[pending["d"]]["status"] == "pending"
    status, body = answers["held"]
    assert status == 200 and statuses(r.read(body))[pending["d"]]["status"] == "completed"
