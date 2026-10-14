# Overture Protocol: requirements draft (unreviewed)

*Draft 2, 2026-10-13. A first synthesis of requirements, not yet reviewed. Each requirement leaves this file when it is reviewed: approved ones move, rewritten, to [`requirements.md`](requirements.md). Terms are defined in [`this.i`](../this.i) term nodes, and design decisions in its decision nodes; where this draft disagrees with either, they win.*

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119, but only where a statement is a requirement on the protocol. Advice to implementers is labelled as advice.

## 1. Parties

- **Requester.** The party that proposes. It is authenticated by a key, but who stands behind the key may be unknown.
- **Agent.** Acts for exactly one principal and is the only party that speaks Overture back to the requester. In KERI terms an agent is reached through an OOBI of the form `/oobi/{principal AID}/agent/{agent AID}`, and the principal authorizes the agent's endpoint role.
- **Principal.** The party the agent acts for. The principal is always a single AID: one facet or capacity of whatever entity stands behind it. It is named in the protocol but never takes part in it.
- **Behind the counter.** Anything between the agent and the principal: a policy engine, escalation to the principal, nested layers of sub-agents. The protocol never discloses any of it.
- **Third parties.** Parties that some actions involve, such as the target of an introduction or the relying party a result is meant for.

## 2. Scope

Overture is a public counter. A requester may propose anything, including things nobody anticipated. The agent handles what it is empowered to handle and turns away the rest. In scope:

- Proposing actions such as issuing or revoking a credential, resolving an OOBI, being challenged to prove something, being introduced to a third party, creating a relationship AID, or starting another protocol with the requester.
- Receipts, status and final dispositions for those proposals.

Out of scope:

- **Administering the agent.** Nothing in Overture configures or commands the agent itself: no changes to policy, preferences or grants. A proposal signed by the principal has no special standing in the protocol.
- **Routing around the agent.** A principal who wants another channel adds one.
- **How the decision is made,** and how the principal is reached.
- **How launched actions run.** IPEX, challenge-response, introduction and the like keep their own definitions. Overture launches and tracks them, but does not redefine them.

## 3. Proposals

**R1. A proposal is a self-addressing signed artifact.** Its SAID identifies it. It MUST be signed by the requester's AID, and it MUST remain verifiable with any transport stripped away. The signature MUST cover every artifact the proposal carries, not only the first.

**R2. A proposal is separate from the message that carries it.** A proposal's SAID never changes. The carrier is fresh for each send, so that transport-level freshness and replay mechanisms (such as KRAM) judge the carrier. A long-pending proposal can therefore be referred to and resubmitted without looking like a replay. A proposal MUST NOT be referenced by transaction mechanisms whose windows would expire while the proposal is still pending.

**R3. A proposal names its recipient.** It MUST name the principal AID it addresses, so that it cannot be replayed to a different agent or principal.

**R4. Proposals are requests, never offers.** No action by the principal or agent can turn a proposal into a commitment by the requester. Any outcome that would bind the requester requires a separate signature by the requester, made after it has seen the outcome, either through the launched action's own countersignature step or an acknowledgement (R17).

**R5. Interest conditions.** A proposal MAY carry conditions that express utility, not commitment: "I propose that you do X, but I'm not interested unless Y." Version 1 defines *start-by* and *finish-by*; other bounds may be added later.
- A proposal not accepted by its start-by time ends `declined`.
- An agent that can see at decision time that finish-by cannot be met SHOULD decline rather than start.
- Completing after finish-by is best effort. The requester judges whether the result is still useful.
- Nothing in the protocol depends on proving when something finished.

**R6. Signer requirement.** A proposal MAY say which signer it will accept on a binding result:
- `principal`: the principal's AID, or a KERI delegate of it created with the Delegate-Is-Delegator (`DID`) trait. This can be checked from KELs alone.
- `representative` (the default): the principal, or any signer that proves a chain of representation to the principal. The chain may be a KERI delegation or a chain of GCD credentials linked through `issuer` edges.

An agent MUST NOT complete a proposal with a binding artifact that fails the stated requirement. It declines instead. Requesters apply any richer acceptance logic on their own side. The field is open to richer predicates later.

**R7. Audience.** A proposal MAY name an audience (the AID of a downstream relying party) and carry that party's nonce, so that the resulting artifact can be bound to one act and one audience. The resulting artifact does the binding. Overture only carries the inputs. Audience is distinct from the party on whose behalf the requester acts; that is shown by the requester's own authority evidence, carried as an attachment.

**R8. Human-facing purpose.** Proposals that reach a person need a description of the purpose that the person can read. Because a stranger supplies it, the person approving MUST be able to see the exact signed proposal, never only a summary rendered from it. The purpose text is the requester's claim and a disclosure the requester answers for, not a gate. Structured action vocabularies (effect × state-kind, and later Syntelos) are preferred over free text where they suffice, and they make localization possible.

**R9. One act per proposal; dependencies by link.**
- A proposal names exactly one action.
- A proposal MAY name others, by SAID, that must complete before it. The links form a dependency graph. Proposals with no link between them may be done in any order or at the same time.
- A batch MAY carry any number of proposals. A prerequisite MUST be already known to the agent or included in the same batch. Cycles MUST be refused.
- A proposal whose prerequisite ends in anything other than `completed` ends `declined`.
- All-or-nothing atomicity and either/or alternatives are out of scope.

**R10. Attachments.** Proposals and dispositions MAY carry attachments through one general, CESR-encoded mechanism. Kinds include: a motivating proposal from a hop closer to the original requester, carried unaltered; dependency links; authority evidence (GCD chains, delegation KELs); KELs for first contact; and outcome artifacts.

**R11. The action catalog is extensible and fails closed.** Every action type has a stable identifier and a parameter schema, and is placed on the effect × state-kind grid so that a policy engine can evaluate it against GCD constraints without knowing Overture. An agent MUST refuse an unknown action.

## 4. Admission and receipts

**R12. Refusal before admission is free.** An agent MAY refuse a proposal it has not admitted without storing anything (beyond aggregate counters) and without signing anything. That includes silence. The protocol MUST NOT oblige an agent to store or sign anything about a proposal before admitting it. Implementations MAY store and sign more.

**R13. A signed receipt marks admission and gives notice.** When an agent admits a proposal (including one deferred, for example by quiet hours), it returns a receipt signed by the agent. The receipt commits to the proposal's SAID and the time of receipt. From then on the agent owes a final disposition. The receipt is also the agent's non-repudiable acknowledgement that it has been given notice. For example, someone reporting a lost license shifts responsibility from the time of notice, even if revocation takes longer.

**R14. Tracking.** The proposal's SAID is its tracking id. It can be recomputed by anyone holding the proposal, so it needs no storage of its own.

*Advice to implementers:* before admitting a cold proposal, an agent may require a stateless proof that the requester can receive replies, using a nonce of its own: a MAC over a time counter, the requester AID and the proposal SAID. Whatever key state the agent resolves for the requester MUST be the key state that signed the proposal.

## 5. Lifecycle

**R15. States.**
- *Refused before admission:* not a state. There is no record, and a later poll returns "unknown".
- *Pending:* from the receipt onward.
- *In progress:* accepted, with the action under way.
- *Final dispositions:*
  - `completed`, with attachments (§6).
  - `declined`. No reason is given by default. This also covers a lapsed start-by and a failed prerequisite.
  - `failed`: accepted, but did not succeed. Lateness alone is not failure.
  - `aborted`: the requester's abort was honored. The disposition reports anything already done.

The agent's first signed final disposition fixes the outcome. An abort is a request, and the agent answers it with whatever disposition is true at that point. Reasons are left out by default, because they let a stranger probe the principal's policy.

**R16. Polling.**
- Only the AID that submitted a proposal can see its status. For anyone else it reads as "unknown".
- A poll MAY list many SAIDs. The response gives one status per SAID, and the whole response is signed once.
- "Unknown" is always a valid answer, even for a proposal that was once receipted. A requester that gets it resubmits outside the polling path: the same body yields the same SAID, and a changed body is a new proposal.
- A proposal or poll MAY carry a `wait` hint: hold the exchange open for up to N seconds. The agent returns the final disposition inline if it has one, or else returns when any listed proposal changes state or the time runs out. The agent may always decline to answer inline.
- Push is an optional per-binding feature, used only when the requester advertises an endpoint.

*Advice to implementers:* a principal who worries that response timing reveals whether policy or a person decided can add random delays.

## 6. Outcomes and evidence

**R17. Receipts are one form.** A receipt consists of a signer AID, the SAID being receipted, a meaning from a closed set, and the signer's `dt`. The meanings are:
- `notice`: an agent receipting a proposal.
- `bound`: a newly created AID receipting the proposal it was created for.
- `seen`: a requester acknowledging a disposition. Optional; not a commitment.

A receipt is its own small signed message or an attachment, not a KERI `rct`, which is reserved for key events. The `dt` on a `notice` receipt is a claim against the agent's own interest, so it needs no anchoring.

**R18. Results can be checked with ordinary tools.** Every result is either a verifiable artifact (an ACDC, a KEL or TEL event, an IPEX exchange) or a reference that resolves to one, such as an AID's OOBI or a credential SAID plus its registry. Results are carried inline or by reference. Checking them needs nothing specific to Overture. A requester that keeps only the attached artifacts loses nothing it needs for verification.

**R19. Where the link is the result, the link is signed.** Sometimes the claim is the result's relationship to the proposal or the principal, for example "this new AID is the one created for our relationship, and it represents P". Then that relationship MUST be signed: by the new AID (a `bound` receipt) and/or by the agent's disposition. In that case the disposition is evidence, not just a convenience.

## 7. Who signs what

**R20. The agent signs every Overture message under its own AID.** These are statements by the agent, and they carry as much weight as the agent's provable authority. If the agent's AID is a `DID` delegate of the principal, its statements carry the principal's weight; that is the principal's choice.

**R21. The decision path is never disclosed.** A principal's involvement becomes visible only on a resulting artifact that the act requires the principal to sign (a halftime contract needs the performer's signature, whoever was consulted along the way). Declining never needs escalation. An act the agent decides should go ahead, but which lies outside its signing authority, must involve the principal before it completes, and policy decides how and when. Escalation may be nested to any depth. Whoever signs MUST prove a chain of representation back to the principal.

## 8. Authentication and transport

**R22. Transport independence.** The core is signed, self-addressing CESR/JSON artifacts. HTTP is one binding, and its requester authentication uses RFC 9421 HTTP message signatures, which [fiki](https://github.com/bakobo/fiki) implements. BLE, NFC and others are meant to work too. LoRa-class links are an aspiration, not a requirement. A tracking id MUST be usable on a different transport from the one that delivered the proposal.

**R23. Requester continuity.** A requester's identity persists across proposals through its key. Requesters SHOULD start with a transferable direct-mode AID and attach its KEL to their first proposal. A requester that starts with an ephemeral non-transferable key and later moves to a transferable AID links the two with a single message signed by both keys and bound to one recipient. This is the KERI analogue of DIDComm v2's `from_prior`, with an audience binding and an explicit proof by the new key, both of which `from_prior` lacks.

**R24. Anchored signatures are not required.** Proposals are acted on when received, against key state at that time. Accountability for proposals comes from the records the parties keep, not from KEL anchoring.

## 9. Test cases

- **Double-consent introduction** (after Aries RFC 0028). R asks agent A for P: "introduce me to T". A sends T's agent a second, chained Overture proposal, attaching R's original. This tests chaining, an outer deadline bounding the inner one, what T may learn about R before consenting, how R's disposition protects T's privacy, and a disposition that means "invitation delivered" rather than "relationship formed".
- **"Start protocol P with me"**, using coin flip (Aries RFC 0193) as the example.
- **"Challenge me"** opening an IPEX `apply` from the agent, with `p` linking back to the proposal.
- **Revoke and reissue** a license after loss: dependency links and receipt-as-notice.
- **A relationship AID**: OOBI-as-result plus a `bound` receipt.

## 10. Deliverables

- The protocol specification.
- JSON Schemas for every message.
- Test vectors.
- A reference stand-in agent that clients can build against before real agents exist.

## Open questions

- The default proof that a new relationship AID belongs to P (R19): a `bound` receipt alone, the agent vouching, or a `DID` delegation (which links publicly to P).
- Whether message schemas are SAIDified, ACDC-style.
- Confirming that keripy validators act on the `DID` trait, not only define it, before the spec relies on it.
