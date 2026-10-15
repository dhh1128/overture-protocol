# Overture Protocol: requirements

*Approved by Daniel Hardman, requirement by requirement. Terms are defined in [`this.i`](../this.i) term nodes (render them with `i glossary`), and the reasons for design choices are in its decision nodes; this file states only what the protocol must do.*

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119, but only where a statement is a requirement on the protocol. Advice to implementers is labelled as advice.

## Scope

Overture is a public counter. A requester may ask for any action in the action catalog, and new actions can be added to the catalog without changing the protocol (R11). The agent handles what it is empowered to handle and turns away the rest.

In scope:
- Overtures asking for actions such as issuing or revoking a credential, resolving an OOBI, being challenged to prove something, being introduced to a third party, creating a relationship AID, or starting another protocol with the requester.
- Receipts, status and outcomes for those overtures.

Out of scope:
- **Administering the agent.** Nothing in Overture configures or commands the agent itself: no changes to policy, preferences or grants. An overture signed by the principal has no special standing in the protocol.
- **Routing around the agent.** A principal who wants another channel adds one.
- **Anything behind the counter,** including how the decision is made and how the principal is reached.
- **How launched actions run.** IPEX, challenge-response, introduction and the like keep their own definitions. Overture launches and tracks them, but does not redefine them.

## Requirements

**R1. An overture is a request for the principal to take one action.** It MUST be signed by the requester's AID, and MUST remain verifiable with any transport stripped away. Its body MUST commit by SAID to each attached overture, and to each item of authority evidence it relies on. An attachment the body does not name carries no claim by the requester.

**R2. Each send is fresh; sameness is the overture's SAID.** Each send of an overture is a fresh signed message, and replay protection judges it on its own date. Two sends are the same overture when they come from the same requester and carry an overture with the same SAID (R14). A requester sends every later message about an overture to the endpoint where it first sent that overture, or to another location published for the agent AID that receipted it, and never to a different agent's endpoint.

**R3. An overture references its principal.** An overture MUST reference, by AID, the principal it addresses, so that it cannot be replayed to a different principal.

**R4. Overtures are never offers.** Nothing the principal or an agent does can turn an overture into a commitment by the requester. Overture defines no message by which a requester commits. If an outcome would bind the requester, it does so only after the requester signs it separately, having seen it, through the launched action's own countersignature step.

**R5. The requester may set preconditions.** An overture MAY carry preconditions. Preconditions are the requester's statement, in advance, that the overture should not be started unless it can be carried out in a way that meets them. They are advisory. Version 1 defines start-by, finish-by, signer (R6) and audience (R7), and more are expected, such as a cost ceiling or a bar on public disclosure. An agent MUST NOT admit an overture that carries a precondition the agent does not understand.
- An agent SHOULD decline an overture rather than start it when it can see that a precondition will not be met.
- An overture that is not acted on by its start-by time ends `expired` (R15).
- A precondition that was predicted to be meetable, but that ends unmet, can only be judged a failure by the requester. (R15)

**R6. Signer precondition.** Version 1 defines a third precondition (R5), signer. It says who must sign a result for the requester to want it:
- `principal`: the principal's AID, or a KERI delegate of it created with the Delegate-Is-Delegator (`DID`) trait. This can be checked from KELs alone.
- `representative` (the default): the principal, or any signer that proves a chain of representation to the principal, through KERI delegation or a chain of GCD credentials linked through `issuer` edges.

An overture without a signer precondition is treated as carrying `representative`. Like every precondition, signer is advisory. An agent SHOULD decline rather than start when it can see that a result would not be signed as required. The requester checks who signed any result it receives, and applies any richer acceptance logic itself.

**R7. Audience precondition.** Version 1 defines a fourth precondition (R5), audience. It references a downstream relying party by AID and carries that party's nonce. It says the requester wants a result only if the result binds itself to that audience and nonce. The result does the binding, and the overture only carries the inputs. The nonce is the relying party's challenge, which the overture carries unchanged as an opaque value. Like every precondition, audience is advisory, and the requester checks the binding itself. The audience is not the party on whose behalf the requester acts. That party is shown by the requester's authority evidence, attached to the overture.

*Advice to implementers:* a relying party should make its nonce unpredictable, because a guessable challenge lets someone produce a result in advance.

**R8. Purpose.** An overture MAY carry a purpose: text the requester writes for a person, saying why it asks. The purpose is the requester's claim, covered by its signature, and the requester answers for it. It is never a gate. Any standard description of what the action does comes from the action's catalog entry (R11), not from the requester.

*Advice to implementers:* because a stranger writes the purpose, a person deciding on an overture should be able to see the exact signed overture, never only a summary rendered from it.

**R9. One action per overture; dependencies by link.** An overture asks for exactly one action. It MAY reference prerequisites by SAID, and these links form a dependency graph, which cannot contain a cycle because a prerequisite's SAID must exist before an overture that depends on it. A prerequisite MUST already be known to the agent or be carried in the same batch. If any part of a batch is malformed (an unknown prerequisite, the same overture twice, or an overture that fails verification), the agent MUST refuse the whole batch and admit none of it. A well-formed batch is judged overture by overture. If a prerequisite does not succeed, the overture that depends on it ends without being acted on, and overtures not linked to it are unaffected. Nothing is rolled back.

**R10. Attachments.** Overture messages MAY carry attachments, all through one CESR mechanism. An attachment is covered by the sender's signature only if the message body commits to it by SAID. The body MUST commit to each overture being passed on, and to the exact message that carried it, which is attached unaltered. It MUST also commit to each item of authority evidence the message relies on, such as GCD credential chains or delegation KELs, and to each result a status report carries (R17, R18). An attached KEL needs no commitment, because a KEL verifies itself. An attachment the body does not commit to carries no claim by the sender. Prerequisite links are body fields (R9), not attachments. Because the sender's signature covers the whole body, passing an overture on discloses every overture in the message it arrived in.

*Advice to implementers:* a requester should send any overture it expects to be passed on, such as an introduction, in its own message, so that passing it on discloses nothing else.

**R11. The action catalog is extensible and fails closed.** Each entry in the action catalog has a stable identifier, a parameter schema and a description a person can read (R8). It also lists the (effect, state-kind) points the action occupies on the act grid defined for [GCD credentials](https://github.com/bakobo/schema/blob/main/gcd/index.md), and says which of its parameters designate the act's targets, so that a policy engine can check an overture against a GCD without knowing Overture. New entries may be added without changing the protocol. An agent MUST refuse, before admission, an overture for an action whose entry it does not know (R12).

**R12. Refusal before admission is free.** An agent MAY refuse an overture or a batch it has not admitted without storing anything beyond aggregate counters and without signing anything, and that includes refusing by silence. The protocol MUST NOT oblige an agent to store or sign anything about an overture before admitting it. Implementations MAY store and sign more.

*Advice to implementers:* before admitting a cold overture, an agent may require a stateless proof that the requester can receive replies, using a nonce of its own: a MAC over a time counter, the requester's AID and the overture's SAID. Whatever key state the agent resolves for the requester MUST be the key state that signed the overture.

**R13. A signed receipt marks admission.** When an agent admits an overture, including one whose handling it defers (for example to quiet hours), it returns a receipt signed by the agent's AID. The receipt references the overture by its SAID, which is the digest of the admitted content, and carries the time of admission. A receipt means the agent has agreed to treat the overture as a work item that later polls and aborts can refer to. It does not promise that the principal will act, or that an outcome will arrive within any time. The receipt is also the agent's signed acknowledgement that it has been given notice of the overture's content. Like every Overture signature, it is ephemeral evidence: it shows what the agent said, judged against the agent's key state at the time. A claim that must outlive a rotation, such as notice that shifts liability for a lost license, belongs in a result anchored by its own mechanism.

**R14. An overture is identified by its own SAID.** Every overture MUST carry a salty nonce of about 128 bits of entropy that the requester makes fresh for it, so two identical asks are two overtures and an overture's SAID reveals nothing about its content. An overture is identified by its own SAID, scoped to the requester's AID. That SAID MUST be computed by the SAID derivation protocol of the [CESR specification](https://github.com/trustoverip/kswg-cesr-specification) (its section "Self-addressing identifier (SAID)"), over the overture serialized as JSON, whatever serialization kind carries it. Prerequisite links, polls, aborts, receipts and status reports reference it by that SAID.

**R15. States and outcomes.** An overture refused before admission has no state, and a later poll about it returns "unknown". After admission, its only visible state is *pending*, from the receipt until its outcome, for as long as that takes. It ends in exactly one outcome:
- `completed`, with any evidence.
- `declined`.
- `expired`: its start-by time passed before it was acted on.
- `failed`: it was agreed to, but did not succeed. A precondition that was predicted to be meetable, but that ends unmet, can only be judged a failure by the requester. (R5)
- `aborted`: the requester's abort was honored, and the report says anything already done.
- `precluded`: a prerequisite did not succeed, so it was never acted on.

The agent's first signed report of an outcome fixes it. An abort is answered with whatever state or outcome holds at that moment. Reasons are omitted by default, because they let a stranger probe the principal's policy, but a principal may choose to give them.

**R16. Polling.**
- Only the requester AID that sent an overture can see its state or outcome. To anyone else it reads as "unknown".
- A poll MAY reference several overtures. The response gives one state or outcome per overture and is signed once.
- "Unknown" is always a valid answer, even for an overture that was receipted. A requester that gets it may send the overture again.
- An overture or a poll MAY carry a `waitUntil` hint, asking the agent to hold the exchange open until a given time. The agent returns the outcome inline if it has one, or else returns when any listed overture's state changes or the time is reached. If the time has already passed when the message arrives, the agent answers at once. The agent may always decline to hold the exchange open.
- Receipts and status reports MAY carry a suggested time for the next poll.
- Delivery initiated by the agent is an optional feature of each binding, used only when the requester advertises an endpoint.

*Advice to implementers:* a principal who does not want response timing to reveal how it decides can add random delays.

*Advice to implementers:* the gap between a message's `dt` and the time it arrives bounds the sender's clock skew plus transit time, so an agent can use it to judge how the sender's `waitUntil` maps onto its own clock.

**R17. Every signature's meaning is explicit; receipts have one form.** A receipt states the signer's AID, what is receipted, the signer's `dt`, and a meaning from a closed set. An overture is receipted by its SAID, which is the digest of its admitted content; a message is receipted by its SAID. The meanings are:
- `admitted`: an agent has admitted the overture as a work item and acknowledges notice of its content (R13).
- `seen`: the signer received the item. This is optional and is not a commitment.

One message MAY carry receipts for several overtures. A receipt is its own small signed message or an attachment. It is not a KERI `rct`, which is reserved for key events.

Every Overture message MUST state what its signature means, through its signed route, its signed field names, or a signed meaning field. A status report that gives an outcome states, for each result it names, that the result is a result of the overture. A result that can sign, such as a newly created AID, MAY state the same about itself, and an action's catalog entry MAY require that it does.

**R18. Results can be checked with ordinary tools.** Every result is either a verifiable artifact, such as an ACDC, a KEL or TEL event, or an IPEX exchange, or a reference that resolves to one, such as an AID's OOBI or a credential SAID plus its registry. Verifying a result needs nothing specific to Overture. The status report that gives the outcome shows that a result is a result of the overture (R17). A requester that keeps that status report and its attachments keeps everything it needs, apart from whatever its by-reference results resolve to.

*R19 retired: a result's link to the overture is stated by the status report that gives its outcome (R17), and its link to the principal is shown by representation evidence (R6).*

**R20. Agents sign under an authorized AID, with provable weight.** Every message an agent sends is signed under that agent's AID, which MUST be one the principal has authorized at the endpoint. Its statements carry as much weight as the authority the agent can prove, through delegation or a GCD chain. If the principal incepted the agent's AID with KERI's `DID` (delegate is delegator) trait, the agent's statements carry the principal's weight; that is the principal's choice.

**R21. The protocol never requires disclosure of the decision path.** Nothing in Overture reveals whether policy, a person or nested agents decided, though a principal may choose to say more. The principal's involvement shows only where a result must carry the principal's own signature, such as a contract the principal must sign whoever was consulted along the way. Declining never needs escalation. An act that should go ahead but lies outside the agent's signing authority must involve whoever holds that authority before it completes; how and when that happens is behind the counter. Escalation may nest to any depth. Whoever signs a result MUST be able to prove a chain of representation back to the principal.

**R22. Transport independence.** Overture messages verify with any transport stripped away (R1). HTTP is one binding. A binding MAY add its own transport authentication, such as RFC 9421 HTTP message signatures for HTTP, which [fiki](https://github.com/bakobo/fiki) implements. That authentication is used only for transport decisions, and the Overture engine never relies on it. BLE, NFC and other bindings are meant to work too. LoRa-class links are an aspiration, not a requirement. An overture's SAID MUST be usable on a different transport from the one that delivered the overture.

**R23. Requester identity.** A requester is identified by its AID, which may be transferable or non-transferable. If a requester's key changes under a non-transferable AID, it becomes a new requester, and its earlier overtures stay scoped to the old AID. Before it verifies a requester's signature, an agent needs that AID's key state. The agent may already have it. If not, the requester attaches its KEL or gives an OOBI. An agent MAY decline to resolve an OOBI from a requester whose overture it has not admitted.

**R24. Anchored signatures are not required.** An agent verifies an overture when it receives it, against the requester's key state at that time. A requester need not anchor an overture's signature in its KEL. If the requester rotates its key after admission, the overture stays admitted.

**R25. Every received message is checked for currency and freshness.** An Overture engine MUST verify each message it receives against the signer's latest establishment event. It MUST refuse a message whose `dt` falls outside its freshness window by its own clock, or that replays a message it has already accepted. It MUST also verify the signatures on each overture being passed on that a message carries (R10), at every depth of nesting, against each signer's latest establishment event, and refuse the message if a signer has rotated since; such an overture is not judged for freshness, because it may be old. These are Overture's own requirements, and whatever performs the checks, an engine MUST NOT run without them.

*Advice to implementers:* keripy performs both checks only in KRAM, and `Kevery` leaves KRAM off unless `enableKram` is set. Without KRAM, keripy's Exchanger verifies a signature against whichever establishment event the signature cites, even an old one, and never checks freshness. KRAM checks only the message received, never one attached inside it, so an implementation checks attached overtures itself. An implementation that relies on KRAM should refuse to start when KRAM is off, unless the operator passes an explicit override, and should warn every time it starts with that override.

## Test cases

- **Double-consent introduction** (after Aries RFC 0028). R asks agent A for P: "introduce me to T". A sends T's agent its own overture, attaching R's original unaltered (R10). This tests passing an overture on, an outer finish-by bounding the inner one, what T may learn about R before consenting (only what R sent in that one message), how the status reports R receives protect T's privacy, and a result that means "invitation delivered" rather than "relationship formed".
- **"Start a protocol with me"**, using coin flip (Aries RFC 0193) as the example.
- **"Challenge me"**: the agent opens an IPEX `apply`, with `p` linking back to the overture.
- **Revoke and reissue** a license after loss: a prerequisite link (R9) and the `admitted` receipt as notice within the interaction (R13).
- **A relationship AID**: an OOBI as the result, with the new AID stating that it is a result of the overture (R17).
- **Preconditions**: an overture that finishes after its finish-by, which the requester judges; an overture carrying a precondition the agent does not understand, refused before admission (R5); and one where the `representative` default rules out a third-party signer (R6).

## Deliverables

- The protocol specification.
- JSON Schemas for every message.
- Test vectors.
- A reference stand-in agent that clients can build against before real agents exist.
- The action catalog's initial entries (R11), enough to run the test cases.
