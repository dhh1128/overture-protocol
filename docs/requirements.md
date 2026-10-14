# Overture Protocol: requirements

*Approved requirements only. Each one is moved here from [`requirements-draft.md`](requirements-draft.md) when Daniel Hardman approves it, in the reviewed wording. Terms are defined in [`this.i`](../this.i) term nodes (render them with `i glossary`), and the reasons for design choices are in its decision nodes; this file states only what the protocol must do.*

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119, but only where a statement is a requirement on the protocol. Advice to implementers is labelled as advice.

**R1. An overture is a request for the principal to take one action.** It MUST be signed by the requester's AID, and MUST remain verifiable with any transport stripped away. Its body MUST commit by SAID to each attached overture, and to each item of authority evidence it relies on. An attachment the body does not name carries no claim by the requester.

**R2. Each send is fresh; sameness is the overture id.** Each send of an overture is a fresh signed message, and replay protection judges it on its own date. Two sends are the same overture when they come from the same requester and carry the same overture id. The first version an agent admits is authoritative, and an agent that notices different content under an admitted id refuses it. A requester sends every later message under an overture id to the endpoint where it first sent that id.

**R9. One action per overture; dependencies by link.** An overture names exactly one action. It MAY name prerequisites by overture id, and these links form a dependency graph. A prerequisite MUST already be known to the agent or be carried in the same batch, and cycles MUST be refused. If any part of a batch is malformed (a dependency cycle, an unknown prerequisite, the same overture id twice, or an overture that fails verification), the agent MUST refuse the whole batch and admit none of it. A well-formed batch is judged overture by overture. If a prerequisite does not succeed, the overture that depends on it ends without being acted on, and overtures not linked to it are unaffected. Nothing is rolled back.

**R12. Refusal before admission is free.** An agent MAY refuse an overture or a batch it has not admitted without storing anything beyond aggregate counters and without signing anything, and that includes refusing by silence. The protocol MUST NOT oblige an agent to store or sign anything about an overture before admitting it. Implementations MAY store and sign more.

*Advice to implementers:* before admitting a cold overture, an agent may require a stateless proof that the requester can receive replies, using a nonce of its own: a MAC over a time counter, the requester's AID and the overture id. Whatever key state the agent resolves for the requester MUST be the key state that signed the overture.

**R13. A signed receipt marks admission.** When an agent admits an overture, including one whose handling it defers (for example to quiet hours), it returns a receipt signed by the agent's AID. The receipt names the overture id, commits to the digest of the admitted content, and carries the time of admission. A receipt means the agent has agreed to treat the overture as a work item that later polls and aborts can refer to. It does not promise that the principal will act, or that an outcome will arrive within any time. The receipt is also the agent's non-repudiable acknowledgement that it has been given notice of the overture's content: someone reporting a lost license, for example, shifts responsibility from the time of notice, even if revocation takes longer.

**R14. Overtures are referred to by overture id.** Polls, aborts and dependency links refer to an overture by its overture id, scoped to the requester's AID.
