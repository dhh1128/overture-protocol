"""Parsing CESR streams into Overture messages with their nests (spec §4.3).

keripy's Parser processes KELs, replies and TEL events in the stream through the Kevery,
Revery and Tevery it is given, and hands each exn, with its signature groups and parsed nests, to an exchanger.
Here that exchanger only collects, so every route keeps its nests (this.i 630f824j).
"""

from dataclasses import dataclass, field

from keri.core.parsing import Parser


@dataclass
class Message:
    """One received exn or nested ACDC, with its signature groups, its source seals, and the
    messages nested in it."""

    serder: object
    tsgs: list = field(default_factory=list)
    cigars: list = field(default_factory=list)
    ssts: list = field(default_factory=list)
    nests: list["Message"] = field(default_factory=list)

    @classmethod
    def from_parsed(cls, parsed: dict) -> "Message":
        return cls(serder=parsed["serder"], tsgs=list(parsed.get("tsgs") or []),
                   cigars=list(parsed.get("cigars") or []),
                   ssts=list(parsed.get("ssts") or []),
                   nests=[cls.from_parsed(n) for n in parsed.get("nests") or []])

    @property
    def ked(self) -> dict:
        return self.serder.sad

    @property
    def said(self) -> str:
        return self.serder.said

    @property
    def route(self) -> str:
        return self.ked.get("r", "")

    @property
    def sender(self) -> str:
        return self.ked.get("i", "")

    @property
    def receiver(self) -> str:
        return self.ked.get("ri", "")

    @property
    def a(self) -> dict:
        return self.ked.get("a", {})


class _Collector:
    """Stands where keripy expects an Exchanger, and keeps what it is given."""

    def __init__(self):
        self.messages = []

    def processEvent(self, **parsed):
        self.messages.append(Message.from_parsed(parsed))


def parse(stream: bytes, *, kvy=None, rvy=None, tvy=None) -> list[Message]:
    """Parse ``stream``, letting ``kvy``, ``rvy`` and ``tvy`` process its KELs, replies and
    TEL events."""
    collector = _Collector()
    Parser(kvy=kvy, rvy=rvy, tvy=tvy, exc=collector).parse(ims=bytearray(stream))
    return collector.messages
