"""Overture messages that reach a keripy host through its own parser (tick 2z4c; this.i
630f824j).

keripy's Exchanger passes parsed nests only to /multisig, /ipex and /fwd handlers, and
verifies an exn against the establishment event it cites, with no freshness check. An
Overture message needs its nests and the stricter checks of spec §4.4, so this Exchanger
hands each /overture/ message whole to an Agent, which runs the check order from step 3,
and passes every other route to keripy as before.

Such a transport has no reply channel, so what the agent answers is kept in ``answers``, as
(requester AID, streams), for the host to send where it can. Outcomes also reach the
requester by push (spec §6.9) or by its polling over HTTP. For attached evidence, construct
the Agent with the host's Reger, so the TEL events the host's parser processes are the ones
the agent checks against.
"""

from collections import deque

from keri.peer import exchanging

from . import messages, wire


class Exchanger(exchanging.Exchanger):
    def __init__(self, hby, handlers, agent, **kwa):
        super().__init__(hby, handlers, **kwa)
        self.agent = agent
        self.answers = deque()

    def processEvent(self, serder, **kwa):
        if not serder.ked.get("r", "").startswith(messages.PREFIX):
            return super().processEvent(serder=serder, **kwa)
        with self.agent.lock:
            answer = self.agent.receive_parsed([wire.Message.from_parsed(dict(kwa, serder=serder))])
        if answer.streams:
            self.answers.append((serder.ked["i"], answer.streams))
