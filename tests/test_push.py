"""Delivery on the agent's initiative (spec §6.9; this.i 4yzm2pn6, 97dehty6)."""

import datetime
import http.server
import threading

import pytest
from keri.kering import Roles

from overture import push
from overture.engine import Plan
from overture.requester import reports, statuses

from test_engine import ISSUE, REVOKE, issue, revoke, send, world  # noqa: F401

MBX = "http://mailbox.example:9"


def advertise(world, role=Roles.mailbox, url=MBX, eid=None):
    """The requester's stream prefix naming the stranger as its mailbox at ``url``: the KELs
    come first, so each reply's signer is known when the reply is processed."""
    mbx = world["stranger"]
    st = world["clock"].stamp()
    return (world["r"].kel() + bytes(mbx.replay())
            + bytes(world["requester"].makeEndRole(eid=eid or mbx.pre, role=role, stamp=st))
            + bytes(mbx.makeLocScheme(url=url, scheme=url.split(":")[0], stamp=st)))


class Post:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.sent = []

    def __call__(self, url, body):
        self.sent.append((url, body))
        return self.answers.pop(0) if self.answers else True


def admit(world, overtures, prefix=b""):
    send(world, prefix + world["r"].batch(overtures, stamp=world["clock"].stamp()))


def test_an_outcome_is_pushed_once_to_the_advertised_mailbox(world):
    o = issue()
    admit(world, [o], advertise(world))
    post = Post()
    assert push.deliver(world["eng"], post) == 1
    ((url, body),) = post.sent
    assert url == MBX
    assert statuses(world["r"].read(body))[o["d"]]["status"] == "completed"
    assert push.deliver(world["eng"], post) == 0 and len(post.sent) == 1


def test_a_pending_overture_is_not_pushed_until_its_outcome(world):
    world["script"].plans[ISSUE] = Plan(after=datetime.timedelta(seconds=30))
    o = issue()
    admit(world, [o], advertise(world))
    post = Post()
    assert push.deliver(world["eng"], post) == 0 and post.sent == []
    world["clock"].tick(31)
    assert push.deliver(world["eng"], post) == 1


def test_a_failed_push_is_tried_again(world):
    admit(world, [issue()], advertise(world))
    post = Post(False, True)
    assert push.deliver(world["eng"], post) == 0
    assert push.deliver(world["eng"], post) == 1
    assert len(post.sent) == 2


def test_one_report_covers_every_undelivered_outcome(world):
    a, b = issue(), revoke()
    admit(world, [a, b], advertise(world))
    post = Post()
    push.deliver(world["eng"], post)
    ((_, body),) = post.sent
    assert set(statuses(world["r"].read(body))) == {a["d"], b["d"]}


def test_a_requester_that_advertises_nothing_is_not_pushed_to(world):
    admit(world, [issue()])
    post = Post()
    assert push.deliver(world["eng"], post) == 0 and post.sent == []


@pytest.mark.parametrize("role,pushed", [(Roles.agent, True), (Roles.witness, False)])
def test_only_mailbox_and_agent_roles_receive_pushes(world, role, pushed):
    admit(world, [issue()], advertise(world, role=role))
    post = Post()
    assert push.deliver(world["eng"], post) == (1 if pushed else 0)


def test_a_url_of_another_scheme_is_not_pushed_to(world):
    admit(world, [issue()], advertise(world, url="tcp://mailbox.example:9"))
    assert push.deliver(world["eng"], Post()) == 0


def test_a_pushed_outcome_can_still_be_polled_and_seen(world):
    o = issue()
    admit(world, [o], advertise(world))
    post = Post()
    push.deliver(world["eng"], post)
    report = reports(world["r"].read(post.sent[0][1]))[0]
    send(world, world["r"].seen(report, stamp=world["clock"].stamp()))
    world["clock"].tick(1)
    _, msgs = send(world, world["r"].poll([o["d"]], stamp=world["clock"].stamp()))
    assert statuses(msgs)[o["d"]]["status"] == "unknown"


def test_the_http_post_sends_cesr_and_reads_the_status(tmp_path):
    got = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            got.append((self.headers["Content-Type"],
                        self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(204 if len(got) == 1 else 500)
            self.end_headers()

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert push.post(url, b"-B") is True
        assert push.post(url, b"-B") is False
    finally:
        server.shutdown()
    assert got[0] == ("application/cesr", b"-B")
    assert push.post("http://127.0.0.1:1", b"-B") is False


def test_the_pusher_delivers_in_the_background_until_stopped(world):
    admit(world, [issue()], advertise(world))
    post = Post()
    delivered = threading.Event()

    def recording(url, body):
        post(url, body)
        delivered.set()
        return True

    pusher = push.Pusher(world["eng"], interval=0.01, post=recording)
    pusher.start()
    try:
        assert delivered.wait(5)
    finally:
        pusher.stop()
    assert len(post.sent) == 1
