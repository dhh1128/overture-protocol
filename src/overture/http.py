"""The HTTP binding (spec §10; this.i 0y83jfj7, 2mgg0fn7), for the stand-in or a keripy host.

A requester POSTs a whole CESR stream to the agent's endpoint URL. The answer travels in the
response: 200 with a CESR stream, 204 when there is nothing to send, including a silent
refusal, or 400 with RFC 9457 problem details when only the major version was the problem.
waitUntil is long polling (RFC 6202) within a cap the agent sets.

Ingress answers from an Agent alone. HttpEnd extends keripy's HttpEnd with it, so a keripy
host mounts one resource at its general ingress, which keripy mounts at /: a request with a
CESR-ATTACHMENT header goes to keripy as before, a whole stream carrying an Overture message
is answered inline, and a whole stream carrying none is queued for the host's parser, as
keripy's PUT queues one (tick 4aqd).

A held answer is an iterable that yields nothing until it has its status report, so a
cooperative server such as keripy's hio serves other requests meanwhile, and a threaded
server sleeps between looks.
"""

import datetime
import json
import time

import falcon
from keri.app import indirecting

from . import engine as engines
from . import errors

CESR = "application/cesr"


class Ingress:
    def __init__(self, agent, *, hold_cap=datetime.timedelta(seconds=30), interval=0.25,
                 sleep=time.sleep):
        self.agent = agent
        self.hold_cap = hold_cap
        self.interval = interval
        self.sleep = sleep
        self.lock = agent.lock

    def on_post(self, req, resp):
        if req.get_header("CESR-ATTACHMENT"):
            return self.on_attachment_header(req, resp)
        body = req.bounded_stream.read(self.agent.max_size + 1)
        with self.lock:
            answer = self.agent.receive(body)
        if answer.refusal is not None and answer.refusal.code is errors.NO_MESSAGE:
            self.on_other(body)
        if answer.unsupported_major:
            resp.status = falcon.HTTP_400
            resp.content_type = falcon.MEDIA_JSON.replace("json", "problem+json")
            resp.text = json.dumps({"type": "about:blank", "title": "Unsupported major version.",
                                    "status": 400, "detail": answer.refusal.detail,
                                    "supportedMajors": list(self.agent.majors)})
            return
        if not answer.streams and answer.wait is None:
            resp.status = falcon.HTTP_204
            return
        resp.status = falcon.HTTP_200
        resp.content_type = CESR
        if answer.wait is None:
            resp.data = b"".join(answer.streams)
        else:
            resp.stream = Held(self, answer.streams, answer.wait)

    def on_attachment_header(self, req, resp):
        raise falcon.HTTPBadRequest(
            title="Overture messages travel as one whole CESR stream.",
            description="Send the stream in the body, without a CESR-ATTACHMENT header.")

    def on_other(self, body: bytes) -> None:
        """A whole stream with no Overture message; the stand-in has no other use for it."""


class Held:
    """The rest of a held answer: what is ready now, then the status report when the agent
    has news or the hold ends."""

    def __init__(self, ingress: Ingress, ready: list[bytes], wait: engines.Wait):
        self.ingress = ingress
        self.ready = list(ready)
        self.wait = wait
        self.deadline = min(wait.until, ingress.agent.clock() + ingress.hold_cap)
        self.done = False

    def __iter__(self):
        return self

    def __next__(self) -> bytes:
        if self.ready:
            return self.ready.pop(0)
        if self.done:
            raise StopIteration
        agent = self.ingress.agent
        with self.ingress.lock:
            if agent.has_news(self.wait) or agent.clock() >= self.deadline:
                self.done = True
                return agent.status_report(self.wait.requester, self.wait.saids)
        if self.ingress.sleep is not None:
            self.ingress.sleep(self.ingress.interval)
        return b""


class HttpEnd(indirecting.HttpEnd, Ingress):
    """keripy's HttpEnd, answering Overture messages inline at the same URL (tick 4aqd).

    Pass ``sleep=None`` under keripy's hio server, which is cooperative: a held answer then
    yields at once and is looked at again on the server's next pass.
    """

    def __init__(self, agent, *, rxbs=None, mbx=None, qrycues=None, **kwa):
        indirecting.HttpEnd.__init__(self, rxbs=rxbs, mbx=mbx, qrycues=qrycues)
        Ingress.__init__(self, agent, **kwa)

    on_post = Ingress.on_post

    def on_attachment_header(self, req, resp):
        indirecting.HttpEnd.on_post(self, req, resp)

    def on_other(self, body: bytes) -> None:
        self.rxbs.extend(body)
