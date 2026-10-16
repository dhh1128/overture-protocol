"""A stand-in agent for client developers to build against (this.i 3yr7nvs7).

It runs the whole check order and message set, but decides behind the counter by a script:
per catalog entry, whether to admit, how long to stay pending, and which outcome to report
with which results. It publishes its endpoint the way spec §3 describes: the principal signs
an /end/role/add reply naming the agent in the agent role, and the agent signs a
/loc/scheme reply giving its URL.
"""

import datetime
import json
from pathlib import Path

from keri.kering import Roles

from ..engine import Agent, Plan
from ..store import Store


class ScriptPolicy:
    """Plans by a script: ``{"default": rule, "actions": {title or SAID: rule}}``.

    A rule may say ``admit`` (default true), ``after`` (seconds pending, default 0),
    ``status`` (default "completed"), ``results``, ``reason``, and ``make: "aid"`` to create
    a real AID whose inception seals the overture's SAID (this.i 564x4rgx).
    """

    def __init__(self, script: dict, make_aid=None):
        self.default = script.get("default", {})
        self.actions = script.get("actions", {})
        self.make_aid = make_aid

    def rule(self, entry: dict) -> dict:
        return self.actions.get(entry["$id"], self.actions.get(entry["title"], self.default))

    def plan(self, requester: str, overture: dict, entry: dict) -> Plan | None:
        rule = self.rule(entry)
        if not rule.get("admit", True):
            return None
        results = list(rule.get("results", []))
        if rule.get("make") == "aid":
            results.insert(0, self.make_aid(overture["d"]))
        return Plan(status=rule.get("status", "completed"),
                    after=datetime.timedelta(seconds=rule.get("after", 0)),
                    results=results, reason=rule.get("reason"))


class StandIn:
    """A principal, its agent, and the agent's engine, in one Habery."""

    def __init__(self, hby, url: str, script: dict, store_path: Path | str, *, clock=None, **kwa):
        self.hby = hby
        self.url = url.rstrip("/")
        self.principal = hby.habByName("principal") or hby.makeHab(name="principal")
        self.agent = hby.habByName("agent") or hby.makeHab(name="agent")
        self.replies = bytes(self.principal.makeEndRole(eid=self.agent.pre, role=Roles.agent))
        self.replies += bytes(self.agent.makeLocScheme(url=self.url, scheme=self.url.split(":")[0]))
        hby.psr.parse(ims=bytearray(self.replies))
        self.policy = ScriptPolicy(script, make_aid=self.make_aid)
        self.store = Store(store_path)
        self.engine = Agent(self.agent, self.principal.pre, self.store, self.policy,
                            clock=clock, **kwa)

    def oobi(self) -> str:
        """The URL that resolves the principal, its agent and the agent's location."""
        return f"{self.url}/oobi/{self.principal.pre}/agent/{self.agent.pre}"

    def oobi_stream(self, aid: str) -> bytes | None:
        """KELs and replies for an OOBI of ``aid``, or None for an AID this stand-in lacks."""
        if aid == self.principal.pre:
            return bytes(self.principal.replay()) + bytes(self.agent.replay()) + self.replies
        hab = self.hby.habByPre(aid)
        return bytes(hab.replay()) if hab is not None else None

    def make_aid(self, overture_said: str) -> dict:
        """Create an AID whose inception event seals ``overture_said``."""
        hab = self.hby.makeHab(name=f"relationship-{overture_said}", data=[{"d": overture_said}])
        return {"aid": hab.pre, "oobi": f"{self.url}/oobi/{hab.pre}"}

    def close(self) -> None:
        self.store.close()


def load_script(path: Path | None) -> dict:
    return json.loads(Path(path).read_text()) if path else {}
