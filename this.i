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
    Proposals ride in fresh non-transactioned exn carriers = decision:
      nid: 5nrmfwk0
      why: >-
        The proposal is its own signed, self-addressing artifact, nested inside an exn carrier that is built fresh for each send, with x empty and no xip. KRAM caches each message by sender and SAID and requires a strictly later dt inside a short window, so if the proposal itself were the exn, resubmitting it unchanged after an unknown poll result (R16) would be dropped as a replay. A fresh carrier lets KRAM judge only the carrier, which gives replay protection with no new mechanism, and agents can tune windows per /overture/ route. We rejected xip/x transactions, because their windows expire while a proposal is still pending, which R2 forbids. Threading goes by proposal SAID inside the payload. Tradeoff accepted: we give up the duplicity-evident p chain of a transaction, which Overture does not need, since the agent's first signed final disposition fixes the outcome (R15).
    Ship first as a stand-alone package that plugs into keripy = decision:
      nid: 630f824j
      why: >-
        The reference code is a separate package that registers Overture route handlers into any keripy Exchanger, and the stand-in agent runs on it. Both ends need the code: requesters are often Signify edge clients (signify-ts) or keripy users, and the agent role matches what KERIA hosts. We rejected building it inside keripy or KERIA from the start, because that makes the design wait on upstream review before it has been exercised, and a plug-in needs nobody's fork or approval. Upstreaming to keripy (building and checking messages), KERIA (hosting) and signify-ts (requesters) follows once the design has held up. Tradeoff accepted: for a while, Overture is a dependency adopters add themselves rather than something already in their stack.
