# Overture Protocol: requirements

*Approved requirements only. Each one is moved here from [`requirements-draft.md`](requirements-draft.md) when Daniel Hardman approves it, in the reviewed wording. Terms are defined in [`this.i`](../this.i) term nodes (render them with `i glossary`), and the reasons for design choices are in its decision nodes; this file states only what the protocol must do.*

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119, but only where a statement is a requirement on the protocol. Advice to implementers is labelled as advice.

**R1. An overture is a request for the principal to take one action.** It MUST be signed by the requester's AID, and MUST remain verifiable with any transport stripped away. Its body MUST commit by SAID to each attached overture, and to each item of authority evidence it relies on. An attachment the body does not name carries no claim by the requester.

**R2. Each send is fresh; sameness is the overture id.** Each send of an overture is a fresh signed message, and replay protection judges it on its own date. Two sends are the same overture when they come from the same requester and carry the same overture id. The first version an agent admits is authoritative, and an agent that notices different content under an admitted id refuses it. A requester sends every later message under an overture id to the endpoint where it first sent that id.

**R9. One action per overture; dependencies by link.** An overture names exactly one action. It MAY name prerequisites by overture id, and these links form a dependency graph. A prerequisite MUST already be known to the agent or be carried in the same batch, and cycles MUST be refused. If any part of a batch is malformed (a dependency cycle, an unknown prerequisite, the same overture id twice, or an overture that fails verification), the agent MUST refuse the whole batch and admit none of it. A well-formed batch is judged overture by overture. If a prerequisite does not succeed, the overture that depends on it ends without being acted on, and overtures not linked to it are unaffected. Nothing is rolled back.

**R14. Overtures are referred to by overture id.** Polls, aborts and dependency links refer to an overture by its overture id, scoped to the requester's AID.
