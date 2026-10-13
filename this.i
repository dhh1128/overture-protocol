# overture-protocol — Intent Tree (this.i)
#
# Source of truth for why this protocol is shaped the way it is. Record each consequential
# decision here first, in its own commit, before the text or code it justifies.

Let an untrusted party propose actions to a principal's agent = goal:
  nid: 8xxflcz6
  why: >
    Overture lets an external party, authenticated by a key but not necessarily identified,
    propose an action to an agent acting for a named principal, and receive an immediate receipt
    or refusal, pollable status, and a final disposition with verifiable evidence. It is a
    standalone, transport-independent message family. We rejected extending IPEX, because IPEX
    assumes the parties are already connected and covers only credential disclosure. We also
    rejected adopting DIDComm coprotocols (Aries RFC 0478/0482), because they assume caller and
    callee share one trust domain and have no decision step, status or cancel. Tradeoff accepted:
    a new set of messages that the KERI ecosystem must review and adopt, rather than a small
    extension to one it already knows.
