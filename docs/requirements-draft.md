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

*R1 approved; see requirements.md.*

*R2 approved; see requirements.md.*

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

*R9 approved; see requirements.md.*

**R10. Attachments.** Proposals and dispositions MAY carry attachments through one general, CESR-encoded mechanism. Kinds include: a motivating proposal from a hop closer to the original requester, carried unaltered; dependency links; authority evidence (GCD chains, delegation KELs); KELs for first contact; and outcome artifacts.

**R11. The action catalog is extensible and fails closed.** Every action type has a stable identifier and a parameter schema, and is placed on the effect × state-kind grid so that a policy engine can evaluate it against GCD constraints without knowing Overture. An agent MUST refuse an unknown action.

## 4. Admission and receipts

*R12 approved; see requirements.md.*

*R13 approved; see requirements.md.*

*R14 approved; see requirements.md.*

*The advice on cold admission moved to R12 in requirements.md.*

## 5. Lifecycle

*R15 approved; see requirements.md.*

*R16 approved; see requirements.md.*

## 6. Outcomes and evidence

*R17 approved; see requirements.md. The `bound` receipt it described is gone: the evidence that a new AID was created for an overture belongs to that action's catalog entry (see R19).*

**R18. Results can be checked with ordinary tools.** Every result is either a verifiable artifact (an ACDC, a KEL or TEL event, an IPEX exchange) or a reference that resolves to one, such as an AID's OOBI or a credential SAID plus its registry. Results are carried inline or by reference. Checking them needs nothing specific to Overture. A requester that keeps only the attached artifacts loses nothing it needs for verification.

**R19. Where the link is the result, the link is signed.** Sometimes the claim is the result's relationship to the proposal or the principal, for example "this new AID is the one created for our relationship, and it represents P". Then that relationship MUST be signed: by the new AID (a `bound` receipt) and/or by the agent's disposition. In that case the disposition is evidence, not just a convenience.

## 7. Who signs what

*R20 approved; see requirements.md.*

*R21 approved; see requirements.md.*

## 8. Authentication and transport

*R22 approved; see requirements.md.*

*R23 approved; see requirements.md.*

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
