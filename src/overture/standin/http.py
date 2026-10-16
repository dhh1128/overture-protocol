"""The stand-in's HTTP app: the binding of spec §10 at /, and OOBIs for discovery."""

import falcon

from ..http import CESR, Ingress


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
    api.add_route("/", Ingress(standin.engine, **kwa))
    oobi = Oobi(standin)
    api.add_route("/oobi/{aid}", oobi)
    api.add_route("/oobi/{aid}/{role}/{eid}", oobi)
    return api
