"""Delivery on the agent's initiative: pushing outcomes to the requester (spec §6.9; this.i
4yzm2pn6, 97dehty6).

Each pass sends one signed status report per requester, covering its outcomes not yet
delivered, to the first URL it advertised that answers with a 2xx status. An outcome that
no URL took is tried again on the next pass, until it is forgotten at keptUntil.

The URL comes from a stranger's signed replies, so a push is a request the requester aims.
By default it reaches only public addresses, judged on the socket actually connected, before
any TLS or request bytes are sent, so a name that resolves differently the second time gains
nothing. It follows no redirect and uses no proxy.
"""

import functools
import http.client
import ipaddress
import threading
import urllib.error
import urllib.request

from .http import CESR


def public(address: str) -> bool:
    """True for a globally routable unicast address."""
    ip = ipaddress.ip_address(address.split("%")[0])
    return ip.is_global and not ip.is_multicast


def _guarded(base, allow_private: bool):
    class Connection(base):
        def __init__(self, *a, **kwa):
            super().__init__(*a, **kwa)
            create = self._create_connection

            def connect(address, *args, **kwargs):
                sock = create(address, *args, **kwargs)
                peer = sock.getpeername()[0]
                if not (allow_private or public(peer)):
                    sock.close()
                    raise ConnectionRefusedError(f"{peer} is not a public address.")
                return sock

            self._create_connection = connect
    return Connection


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kwa):
        return None


def _opener(allow_private: bool) -> urllib.request.OpenerDirector:
    plain = _guarded(http.client.HTTPConnection, allow_private)
    secure = _guarded(http.client.HTTPSConnection, allow_private)

    class HTTP(urllib.request.HTTPHandler):
        def http_open(self, req):
            return self.do_open(plain, req)

    class HTTPS(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(secure, req, context=self._context)

    return urllib.request.build_opener(urllib.request.ProxyHandler({}), HTTP, HTTPS, _NoRedirect)


def post(url: str, body: bytes, *, allow_private: bool = False, timeout: float = 10) -> bool:
    """POST ``body`` to ``url`` as CESR, and say whether it was taken."""
    if not url.startswith(("http://", "https://")):
        return False
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": CESR})
    try:
        with _opener(allow_private).open(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError):
        return False


def _post(url: str, body: bytes, *, allow_private: bool) -> bool:
    return post(url, body, allow_private=allow_private)


def deliver(agent, post=post) -> int:
    """Run one pass, and return how many requesters' reports were delivered."""
    done = 0
    with agent.lock:
        deliveries = agent.deliveries()
    for d in deliveries:
        with agent.lock:
            report = agent.status_report(d.requester, d.saids)
        if any(post(url, report) for url in d.urls):
            with agent.lock:
                agent.store.delivered(d.requester, d.saids)
            done += 1
    return done


class Pusher:
    """Runs a pass every ``interval`` seconds on a daemon thread until stopped.
    ``allow_private`` lets pushes reach loopback and private addresses, for an operator
    whose requesters' mailboxes are on its own network."""

    def __init__(self, agent, *, interval: float = 2.0, post=None, allow_private=False):
        self.agent = agent
        self.interval = interval
        self.post = post or functools.partial(_post, allow_private=allow_private)
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="overture-push")

    def _run(self) -> None:
        while not self.stopping.is_set():
            deliver(self.agent, self.post)
            self.stopping.wait(self.interval)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stopping.set()
        self.thread.join()
