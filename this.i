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
    Ship first as a stand-alone package that plugs into keripy = decision:
      nid: 630f824j
      why: >-
        The reference code is a separate package that registers Overture route handlers into any keripy Exchanger, and the stand-in agent runs on it. Both ends need the code: requesters are often Signify edge clients (signify-ts) or keripy users, and the agent role matches what KERIA hosts. We rejected building it inside keripy or KERIA from the start, because that makes the design wait on upstream review before it has been exercised, and a plug-in needs nobody's fork or approval. Upstreaming to keripy (building and checking messages), KERIA (hosting) and signify-ts (requesters) follows once the design has held up. Tradeoff accepted: for a while, Overture is a dependency adopters add themselves rather than something already in their stack.
    Requesters run KERI and CESR; there is no thin-requester profile = decision:
      nid: 0p27s4g9
      why: >-
        A requester must sign a proposal as a v2 exn (KERI version string, Blake3-256 SAID, CESR signatures, v2 nesting), verify the agent's receipts, status and dispositions against the agent's transferable AID, which means resolving its KEL, and often check KERI/ACDC outcome artifacts (R18). So Overture assumes a KERI/CESR stack on both sides. An Ed25519 key of the kind fiki uses can still be the requester's first identity (R23), and RFC 9421 via fiki remains the HTTP binding's transport authentication (R22). We rejected a thin-requester profile that signs with a CESR subset and trusts fiki response signatures for live checks, because the logic a requester must support is too much to carry outside a KERI stack, and verifying the agent without its KEL had no clean answer. We rejected a JSON-only proposal signed with fiki primitives, because it contradicts the exn envelope (7cw0yhrk, 40r080ck) and loses transport-independent non-repudiation. Tradeoff accepted: a party with only fiki cannot be an Overture requester.
    Sameness of a request is a requester-chosen request id, not its bytes = decision:
      nid: 69tz0ngx
      why: >-
        Each send is an ordinary signed exn with its own fresh dt and SAID, and replay protection judges that send directly. Inside it, the request carries a request id that the requester chooses (a UUID, nonce or counter; not cryptographic). The agent scopes the id to the requester's AID, so ids from different requesters never collide, and because every send is signed by the requester, nobody else can reuse its ids. A second send with the same id is the same request sent redundantly, and a new id is a new request; redundancy is not a replay. Polls, aborts and dependency links refer to the request id. KERI's RUN principle, in which each peer creates the identifiers for its own data, is the precedent. This replaces two earlier decisions, 5nrmfwk0 (a fresh carrier per send) and 40r080ck (the proposal as a nested exn), which tried to get sameness from byte identity: a fixed signed body that could be resent, wrapped in a separate message so replay protection would not reject it. We rejected that because it conflated semantic identity with byte identity and could not tell a repeat from a second request. We also rejected sameness by citing the earlier send's SAID, and sameness by equal content, which would make two identical asks for two hamburgers impossible. Tradeoff accepted: an agent must remember the request ids it has receipted.
    The first-seen version of a request id is authoritative = decision:
      nid: 8nyrml77
      why: >-
        Following KERI's first-seen rule, the first version of a request id an agent admits is authoritative, and no later send with the same id changes it. Comparing a later send's content is not required of the agent. One that notices different content refuses the send and never applies it. Whether to compare at all is up to the implementation, so an agent that forgets unreceipted ids at once is not burdened. The receipt commits to the digest of the admitted content, so a requester can always see which version is in force. We rejected BADA's latest-wins rule, under which a later-dated send would replace the earlier one, because that makes every redundant send a potential amendment, and amendment is a capability no use case yet needs. Tradeoff accepted: a requester that changes its mind must abort and send a new request id, rather than edit the one in force.
    A hop passes a request on by attaching it, never by forwarding or wrapping = decision:
      nid: 4uvlnnx4
      why: >-
        When a party passes a request onward (escalation through any number of agent layers, or the double-consent introduction), it sends its own request, signed by itself with its own request id and date, and attaches the original signed request unaltered as a v2 nested substream, committing to it by digest so its own signature covers it. Each hop is the requester of the next, and only each hop's own send is judged for freshness, so a slow layer never makes the request stale, and the original requester's date survives inside the original. keripy already does exactly this kind of nesting: its v2 /fwd envelope carries a whole signed exn as a nest, keeps the child's signatures, and commits to it in a.evt (tests/app/test_forwarding.py). We rejected forwarding the original as a live send, because the next agent would judge it for freshness against the original date and refuse it after any delay, and could not tell who passed it on. We rejected wrapping it in a message that says nothing on its own behalf, because that needs a second date inside the request and makes the relay an anonymous carrier. How agents behind the counter talk is still out of scope; this applies when they choose to speak Overture. Tradeoff accepted: every hop maps its own request id back to the one below it.
