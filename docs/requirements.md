# Overture Protocol: requirements

*Approved requirements only. Each one is moved here from [`requirements-draft.md`](requirements-draft.md) when Daniel Hardman approves it, in the reviewed wording. Terms are defined in [`this.i`](../this.i) term nodes (render them with `i glossary`), and the reasons for design choices are in its decision nodes; this file states only what the protocol must do.*

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119, but only where a statement is a requirement on the protocol. Advice to implementers is labelled as advice.

**R1. An overture is a request for the principal to take one action.** It MUST be signed by the requester's AID, and MUST remain verifiable with any transport stripped away. Its body MUST commit by SAID to each attached overture, and to each item of authority evidence it relies on. An attachment the body does not name carries no claim by the requester.

**R2. Each send is fresh; sameness is the overture id.** Each send of an overture is a fresh signed message, and replay protection judges it on its own date. Two sends are the same overture when they come from the same requester and carry the same overture id. The first version an agent admits is authoritative, and an agent that notices different content under an admitted id refuses it. A requester sends every later message under an overture id to the endpoint where it first sent that id, or to another location published for the agent AID that receipted it, and never to a different agent's endpoint.

**R9. One action per overture; dependencies by link.** An overture names exactly one action. It MAY name prerequisites by overture id, and these links form a dependency graph. A prerequisite MUST already be known to the agent or be carried in the same batch, and cycles MUST be refused. If any part of a batch is malformed (a dependency cycle, an unknown prerequisite, the same overture id twice, or an overture that fails verification), the agent MUST refuse the whole batch and admit none of it. A well-formed batch is judged overture by overture. If a prerequisite does not succeed, the overture that depends on it ends without being acted on, and overtures not linked to it are unaffected. Nothing is rolled back.

**R12. Refusal before admission is free.** An agent MAY refuse an overture or a batch it has not admitted without storing anything beyond aggregate counters and without signing anything, and that includes refusing by silence. The protocol MUST NOT oblige an agent to store or sign anything about an overture before admitting it. Implementations MAY store and sign more.

*Advice to implementers:* before admitting a cold overture, an agent may require a stateless proof that the requester can receive replies, using a nonce of its own: a MAC over a time counter, the requester's AID and the overture id. Whatever key state the agent resolves for the requester MUST be the key state that signed the overture.

**R13. A signed receipt marks admission.** When an agent admits an overture, including one whose handling it defers (for example to quiet hours), it returns a receipt signed by the agent's AID. The receipt names the overture id, commits to the digest of the admitted content, and carries the time of admission. A receipt means the agent has agreed to treat the overture as a work item that later polls and aborts can refer to. It does not promise that the principal will act, or that an outcome will arrive within any time. The receipt is also the agent's non-repudiable acknowledgement that it has been given notice of the overture's content: someone reporting a lost license, for example, shifts responsibility from the time of notice, even if revocation takes longer.

**R14. Overtures are referred to by overture id.** Polls, aborts and dependency links refer to an overture by its overture id, scoped to the requester's AID.

**R15. States and outcomes.** An overture refused before admission has no state, and a later poll about it returns "unknown". After admission, its only visible state is *pending*, from the receipt until its outcome, for as long as that takes. It ends in exactly one outcome:
- `completed`, with any evidence.
- `declined`.
- `expired`: its start-by time passed before it was acted on.
- `failed`: it was agreed to, but did not succeed. Lateness alone is not failure.
- `aborted`: the requester's abort was honored, and the report says anything already done.
- `precluded`: a prerequisite did not succeed, so it was never acted on.

The agent's first signed report of an outcome fixes it. An abort is answered with whatever state or outcome holds at that moment. Reasons are omitted by default, because they let a stranger probe the principal's policy, but a principal may choose to give them.

**R16. Polling.**
- Only the requester AID that sent an overture can see its state or outcome. To anyone else it reads as "unknown".
- A poll MAY name several overture ids. The response gives one state or outcome per id and is signed once.
- "Unknown" is always a valid answer, even for an overture that was receipted. A requester that gets it may send the overture again under the same overture id.
- An overture or a poll MAY carry a `wait` hint, asking the agent to hold the exchange open for up to N seconds. The agent returns the outcome inline if it has one, or else returns when any listed overture's state changes or the time runs out. The agent may always decline to hold the exchange open.
- Receipts and status reports MAY carry a suggested time for the next poll.
- Delivery initiated by the agent is an optional feature of each binding, used only when the requester advertises an endpoint.

*Advice to implementers:* a principal who does not want response timing to reveal how it decides can add random delays.

**R17. Every signature's meaning is explicit; receipts have one form.** A receipt states the signer's AID, what is receipted, the signer's `dt`, and a meaning from a closed set. An overture is receipted by its overture id together with the digest of its admitted content; a message is receipted by its SAID. The meanings are:
- `admitted`: an agent has admitted the overture as a work item and acknowledges notice of its content (R13).
- `seen`: the signer received the item. This is optional and is not a commitment.

One message MAY carry receipts for several overtures. A receipt is its own small signed message or an attachment. It is not a KERI `rct`, which is reserved for key events. The `dt` on an `admitted` receipt is a claim against the agent's own interest, so it needs no anchoring.

Every Overture message MUST state what its signature means, through its signed route, its signed field names, or a signed meaning field. An outcome report states, for each result it names, that the result is a result of the overture. A result that can sign, such as a newly created AID, MAY state the same about itself, and an action's catalog entry MAY require that it does.

**R20. Agents sign under an authorized AID, with provable weight.** Every message an agent sends is signed under that agent's AID, which MUST be one the principal has authorized at the endpoint. Its statements carry as much weight as the authority the agent can prove, through delegation or a GCD chain. If the principal incepted the agent's AID with KERI's `DID` (delegate is delegator) trait, the agent's statements carry the principal's weight; that is the principal's choice.

**R21. The protocol never requires disclosure of the decision path.** Nothing in Overture reveals whether policy, a person or nested agents decided, though a principal may choose to say more. The principal's involvement shows only where a result must carry the principal's own signature, such as a contract the principal must sign whoever was consulted along the way. Declining never needs escalation. An act that should go ahead but lies outside the agent's signing authority must involve whoever holds that authority before it completes; how and when that happens is behind the counter. Escalation may nest to any depth. Whoever signs a result MUST be able to prove a chain of representation back to the principal.
