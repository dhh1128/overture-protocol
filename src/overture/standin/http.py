"""The HTTP binding (spec §10; this.i 0y83jfj7, 2mgg0fn7).

A requester POSTs a whole CESR stream to the agent's endpoint URL. The answer travels in the
response: 200 with a CESR stream, 204 when there is nothing to send, including a silent
refusal, or 400 with RFC 9457 problem details when only the major version was the problem.
waitUntil is long polling (RFC 6202) within a cap the agent sets.
"""

import datetime
import json
import threading
import time

import falcon

from .. import engine as engines

CESR = "application/cesr"


class Ingress:
    def __init__(self, standin, *, hold_cap=datetime.timedelta(seconds=30), interval=0.25,
                 sleep=time.sleep):
        self.standin = standin
        self.hold_cap = hold_cap
        self.interval = interval
        self.sleep = sleep
        self.lock = threading.Lock()

    def on_post(self, req, resp):
        if req.get_header("CESR-ATTACHMENT"):
            raise falcon.HTTPBadRequest(
                title="Overture messages travel as one whole CESR stream.",
                description="Send the stream in the body, without a CESR-ATTACHMENT header.")
        body = req.bounded_stream.read(self.standin.engine.max_size + 1)
        eng = self.standin.engine
        with self.lock:
            answer = eng.receive(body)
        if answer.unsupported_major:
            resp.status = falcon.HTTP_400
            resp.content_type = falcon.MEDIA_JSON.replace("json", "problem+json")
            resp.text = json.dumps({"type": "about:blank", "title": "Unsupported major version.",
                                    "status": 400, "detail": answer.refusal.detail,
                                    "supportedMajors": list(eng.majors)})
            return
        streams = list(answer.streams)
        if answer.wait is not None:
            streams.append(self._hold(answer.wait))
        if not streams:
            resp.status = falcon.HTTP_204
            return
        resp.status = falcon.HTTP_200
        resp.content_type = CESR
        resp.data = b"".join(streams)

    def _hold(self, wait: engines.Wait) -> bytes:
        eng = self.standin.engine
        deadline = min(wait.until, eng.clock() + self.hold_cap)
        while True:
            with self.lock:
                if eng.has_news(wait) or eng.clock() >= deadline:
                    return eng.status_report(wait.requester, wait.saids)
            self.sleep(self.interval)


class Oobi:
    def __init__(self, standin):
        self.standin = standin

    def on_get(self, req, resp, aid, role=None, eid=None):
        stream = self.standin.oobi_stream(aid)
        if stream is None:
            raise falcon.HTTPNotFound(title="No such identifier here.")
        resp.status = falcon.HTTP_200
        resp.content_type = CESR
        resp.data = stream


def app(standin, **kwa) -> falcon.App:
    """The stand-in agent's WSGI app: POST / for Overture, GET /oobi/... for discovery."""
    api = falcon.App()
    api.add_route("/", Ingress(standin, **kwa))
    oobi = Oobi(standin)
    api.add_route("/oobi/{aid}", oobi)
    api.add_route("/oobi/{aid}/{role}/{eid}", oobi)
    return api
