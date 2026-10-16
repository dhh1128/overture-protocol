"""Delivery on the agent's initiative: pushing outcomes to the requester (spec §6.9; this.i
4yzm2pn6, 97dehty6).

Each pass sends one signed status report per requester, covering its outcomes not yet
delivered, to the first URL it advertised that answers with a 2xx status. An outcome that
no URL took is tried again on the next pass, until it is forgotten at keptUntil.
"""

import threading
import urllib.error
import urllib.request

from .http import CESR


def post(url: str, body: bytes, *, timeout: float = 10) -> bool:
    """POST ``body`` to ``url`` as CESR, and say whether it was taken."""
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": CESR})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError):
        return False


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
    """Runs a pass every ``interval`` seconds on a daemon thread until stopped."""

    def __init__(self, agent, *, interval: float = 2.0, post=post):
        self.agent = agent
        self.interval = interval
        self.post = post
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
