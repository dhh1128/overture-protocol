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
  children:
    Overture messages are KERI v2 exn routes = decision:
      nid: 7cw0yhrk
      why: >-
        Every Overture message is a KERI v2 exn whose route sits under /overture/. The KERI spec defines exn as a generic exchange whose route names the transaction type and step, and IPEX already lives this way, so a route is the intended extension point. In keripy a new route is one handler registered with Exchanger.addHandler, and it inherits signing, CESR attachments, sender authentication, evidence hooks, transport neutrality and KRAM replay protection. We rejected a dedicated message family (a new ilk), because it needs a KERI spec change and parser changes in every implementation, which puts adoption on someone else's timeline; its only gain, top-level fields shaped to Overture, the a block already gives. We chose v2 over v1 for the ri recipient field and KRAM's v2 handling. Tradeoff accepted: a bet on v2 exn adoption while parts of the ecosystem still speak v1.
