# Overture Protocol Specification

*Version 1.0, draft. Editor: Daniel Hardman. This specification is derived from the approved requirements in [`requirements.md`](requirements.md) and message layouts in [`messages.md`](messages.md); the reason for each design choice is a decision node in [`this.i`](../this.i), cited here by its eight-character id, such as `7cw0yhrk`. Where this text and those files disagree, this text is the one to fix.*

## 1. Introduction

Overture lets a requester ask an agent that acts for a principal to have that principal take one action: issue or revoke a credential, introduce the requester to someone, challenge the requester to prove something, create an AID for the relationship, start another protocol, and so on. The requester is identified by its AID and need not be known to anyone. The agent may refuse at no cost. If it admits the overture, it returns a signed receipt; the requester then polls, and the agent's status report eventually gives the overture's outcome, with verifiable results for whatever was done.

Overture is to an agent what a service counter is to a shop. Anyone can walk up and ask; the counter takes what it is empowered to handle and turns away the rest. Everything between the agent and the principal, such as a policy engine, an escalation to a person, or nested layers of agents, is *behind the counter*, and nothing in this protocol discloses it.

Every Overture message is a KERI v2 `exn` message under a route that begins `/overture/`, signed by its sender and verifiable with any transport stripped away.

### 1.1 Scope

In scope: overtures asking for actions in the action catalog (§8); receipts, status and outcomes for them; and one transport binding, HTTP (§10).

Out of scope:

- Administering the agent. Nothing in Overture configures or commands the agent itself. An overture signed by the principal has no special standing.
- Routing around the agent. A principal who wants another channel adds one.
- Anything behind the counter, including how a decision is made and how the principal is reached.
- How launched actions run. IPEX, challenge-response, introduction and the like keep their own definitions. Overture launches and tracks them, but does not redefine them.

### 1.2 Conventions

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, RECOMMENDED and MAY are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they appear in all capitals. Paragraphs labelled *Advice to implementers* are not requirements.

Times are written as in KERI's `dt` field: an ISO 8601 date-time with microseconds and a UTC offset, such as `2026-10-15T17:05:00.000000+00:00`. JSON examples show the `a` block of an `exn` and omit `version`, and SAIDs in examples are abbreviated.

### 1.3 Normative references

- KERI: [Key Event Receipt Infrastructure](https://github.com/trustoverip/kswg-keri-specification), version 2 messages.
- CESR: [Composable Event Streaming Representation 1.0](https://github.com/trustoverip/kswg-cesr-specification/tree/v1.0), including its section "Self-addressing identifier (SAID)".
- ACDC: [Authentic Chained Data Containers 1.0](https://github.com/trustoverip/kswg-acdc-specification/tree/v1.0), including its schema rules and the JSON Schema 2020-12 dialect they require.
- GCD: [Generalized Cooperative Delegation credentials](https://github.com/bakobo/schema/blob/main/gcd/index.md), whose schema has the SAID `ELDiEui48xsASGvDcNdsOwPptW0v4i-oN6-75_I1d60c`.
- [RFC 6202](https://www.rfc-editor.org/rfc/rfc6202), for long polling in the HTTP binding.

## 2. Terminology

- **Requester**: the party that sends an overture, identified by its AID, which may be transferable or non-transferable. Who controls that AID may remain unknown.
- **Principal**: the AID an agent acts for. An overture references it, but it never takes part in the protocol. A principal is always one facet of whatever entity stands behind it.
- **Agent**: a party, identified by its AID, that receives overtures for exactly one principal and is the only party that answers the requester. A principal may authorize several agents.
- **Overture**: a signed request from a requester asking a principal to take exactly one action. It is identified by its own SAID within the requester's scope (§6.2).
- **Batch**: a single message that carries one or more overtures. Each overture in a batch keeps its own lifecycle, and a batch is never all-or-nothing.
- **Endpoint**: the location a requester sends to: a URL a principal's agent publishes by a `/loc/scheme` reply, which is the agent's general KERI ingress. Any agent AID the principal has authorized there may answer. This differs from KERI's sense, in which an endpoint is identified by one `eid` (`2mgg0fn7`).
- **Admission**: the agent's acceptance of an overture as a work item, marked by a signed `admitted` receipt.
- **Outcome**: what became of an overture: the principal acted on it or declined it, or it ended by an event such as expiry or an honored abort.
- **Result**: a verifiable artifact produced by acting on an overture, or a reference that resolves to one.
- **Hop**: a party that, having received an overture, sends its own overture onward to another agent because of it (§6.8).
- **Behind the counter**: everything between the agent and the principal.

## 3. Overview

A requester first learns the agent's endpoint and key state through KERI's own endpoint authorization (`0svwkvee`): the principal signs an `/end/role/add` reply naming the agent's AID in the `agent` role, and the agent signs a `/loc/scheme` reply giving its URL, both reachable by OOBI. This proves only that the agent is an endpoint the principal authorized. The authority the agent can prove for what it says is shown separately, by delegation or a GCD chain (§6.10).

The exchange then runs:

1. The requester sends a **batch** carrying one or more overtures (§5.1).
2. The agent checks the message (§6.1). It may refuse the whole batch, or any overture in it, without storing or signing anything (§6.4). For each overture it admits, it returns a signed **receipt** with meaning `admitted` (§5.2).
3. The requester sends **polls** (§5.3), and may send an **abort** (§5.4). The agent answers each with a **status report** (§5.5) giving, per overture, `pending`, `unknown`, or an outcome with its results.
4. If the requester advertised an endpoint, the agent may also deliver status reports on its own initiative (§6.9).

Two overtures in one batch may depend on each other, so that the second is acted on only if the first succeeds (§6.5). A hop that passes an overture on sends its own overture and attaches the original message unaltered (§6.8).

## 4. Common message rules

### 4.1 Envelope

Every Overture message MUST be a KERI v2 `exn` whose route `r` begins `/overture/` (`7cw0yhrk`). The route is a body field covered by the message's SAID and its sender's signature, so it is the sender's signed claim that the message is an Overture message of that kind. The routes are `/overture/batch`, `/overture/receipt`, `/overture/poll`, `/overture/abort` and `/overture/status` (`970lu92k`). Envelope fields keep KERI's names (`v t d i ri x p dt r q a`). Fields inside `a` are Overture's own and use camelCase names.

- `i` MUST be the sender's AID.
- `ri` MUST be the AID of the party the message is addressed to. In a message from a requester, that is the principal's AID (`6f7mlrg6`); an agent MUST refuse before admission a message whose `ri` is not the AID of the principal it acts for. In a message from an agent, it is the requester's AID.
- `dt` MUST be the sender's time of sending.
- `x`, `p` and `q` MUST be empty, because an overture's own SAID ties later messages to it.
- `a.version` is REQUIRED in every Overture message (§9).

### 4.2 What a signature means

Every Overture message MUST state what its signature means, through its signed route, its signed field names, or a signed meaning field from a closed set (`7m92u5mp`). A batch signature means "I ask for what these overtures say". A receipt's meaning is stated per item (§5.2). A poll means "tell me about these overtures"; an abort means "I withdraw these overtures". A status report states each overture's status, and for an outcome it states that each result it lists is a result of that overture.

Every Overture signature is ephemeral evidence (`7sx6spf2`): it shows what its signer said, judged against the signer's key state when the message was received. Nothing in Overture is anchored in a KEL (`2j74vu2p`). A claim that must outlive a rotation belongs in a result, which is anchored by its own mechanism.

### 4.3 Attachments and framing

An attachment is covered by the sender's signature only if the message body commits to it by SAID (`8erq0hp5`). An attachment the body does not commit to carries no claim by the sender. The body of an Overture message MUST commit to:

- each overture being passed on, and the exact message that carried it (§6.8);
- each item of authority evidence the message relies on, where a GCD chain is committed by the SAID of its leaf credential, whose edges commit to every other link;
- each result a status report carries.

KELs, TEL events and KERI endpoint replies need no commitment, because each verifies itself; that includes the KELs that show a delegation. Leaving them uncommitted also lets a relay or agent supply fresher key state while an overture waits.

Framing follows CESR v2 (`0xc2dqvw`):

- An Overture message MUST be sent as a message + attachments group (count code `-B`, or `--B` when large), which encloses the message body, a JSON body inside a non-native body group (`-H` or `--H`), followed by its attachments.
- Each attached message that the body commits to, whether a passed-on message, an ACDC of an evidence chain or an attached result, MUST be a nested message + attachments group among those attachments, carrying its own signatures.
- KELs, TEL events and endpoint replies MUST NOT be nested. They are sent before the Overture message in the same stream, as top-level messages, so that the receiver's ordinary KERI processing learns the key state before it verifies the Overture message.

*Advice to implementers:* keripy's parser delivers nested groups to an `exn` handler only for a fixed set of routes, so an implementation built on it must give `/overture/` routes their nests (`630f824j`).

### 4.4 Freshness and currency

An Overture engine MUST verify each message it receives against the signer's latest establishment event, and MUST refuse a message whose `dt` falls outside its freshness window by its own clock, or that replays a message it has already accepted (`35wllumn`). These are Overture's own requirements, whatever performs them, and an engine MUST NOT run without them.

The signatures on a passed-on message attached inside another (§6.8) are verified, at every depth of nesting, against each signer's latest establishment event, and the carrying message is refused if a signer has rotated since signing (`3j0mdxh4`). Such a message is not judged for freshness, because it may be old.

*Advice to implementers:* keripy performs both checks only in KRAM, which `Kevery` leaves off unless `enableKram` is set; without KRAM, keripy verifies a signature against whichever establishment event it cites and never checks freshness. KRAM checks only the message received, never one attached inside it, so an implementation checks attached messages itself. An implementation that relies on KRAM should refuse to start when KRAM is off, unless the operator passes an explicit override, and should warn at every start with that override.

## 5. Messages

### 5.1 Batch

Route `/overture/batch`. Sent by a requester to ask the principal for what its overtures say (`5xwgkz20`).

- `i`: the requester's AID. `ri`: the principal's AID.
- `a.overtures`: REQUIRED. A list of one or more overtures.
- `a.waitUntil`: OPTIONAL. A time until which the requester asks the agent to hold the exchange open (§6.7).

Each overture is a JSON object with these fields:

| Field | Required | Meaning |
|---|---|---|
| `d` | yes | The overture's own SAID (§6.2). |
| `u` | yes | A salty nonce of about 128 bits of entropy, made fresh for this overture and never a counter, so two identical asks are two overtures and the SAID reveals nothing about a guessable overture's content. |
| `action` | yes | The SAID (`$id`) of the catalog entry for the one action asked for (§8). |
| `params` | yes | The action's parameters. They MUST validate against the catalog entry referenced by `action`. |
| `prereqs` | no | SAIDs of overtures that must succeed before this one is acted on (§6.5). |
| `preconditions` | no | A map of preconditions (§7). |
| `purpose` | no | Text the requester writes for a person, saying why it asks. It is the requester's signed claim and is never a gate (`6yusrcwc`). |
| `triggeredBy` | no | An object with `said`, the SAID of the overture that caused this one, and `exn`, the exn SAID of the message that carried it (§6.8). |
| `evidence` | no | SAIDs of the authority evidence this overture relies on; for each GCD chain, its leaf credential's SAID. |

Attachments: the requester's signatures; the message referenced by each `triggeredBy`, nested; and the evidence each `evidence` entry references, nested, with the rest of each chain. Before the batch in the same stream, the requester MAY send its KEL (§6.10) and its endpoint replies (§6.9).

```json
"a": {
  "overtures": [
    { "d": "EAbc...", "u": "0AB3...", "action": "E...revoke-license", "params": { "credential": "E...lost" } },
    { "d": "EXyz...", "u": "0AQ9...", "action": "E...issue-license", "params": { },
      "prereqs": ["EAbc..."], "purpose": "Replace my lost license." }
  ]
}
```

### 5.2 Receipt

Route `/overture/receipt`. Signed by an agent to mark admission, or by a requester to acknowledge a status report (`9z0lpky7`, `6fcnv3q0`).

- `i`: the signer's AID. `ri`: the AID of the party the receipt is sent to. `dt`: the signer's time; on an `admitted` receipt, the time of admission.
- `a.receipts`: REQUIRED. A list of one or more receipts.
- `a.nextPoll`: OPTIONAL, and only in a receipt an agent signs (§6.7).

Each receipt:

| Field | Required | Meaning |
|---|---|---|
| `meaning` | yes | `admitted` or `seen`. No other value is defined in version 1. |
| `said` | yes | For `admitted`, the overture's SAID, which is also the digest of the admitted content. For `seen`, the exn SAID of the status report seen. |
| `keptUntil` | for `admitted` | The time until which the agent commits to keep the overture's status and outcome, and will not answer `unknown` about it (§6.6). It MUST NOT appear on `seen`. |

The meanings are:

- `admitted`: signed by an agent. The agent has admitted the overture as a work item that later polls and aborts can refer to, and acknowledges that it has been given notice of the overture's content (§6.4).
- `seen`: signed by a requester over a status report that gives outcomes, to tell the agent it has them (§6.6). It is not a commitment. An agent MUST NOT sign `seen`.

A receipt is not a KERI `rct`, which is reserved for key events.

```json
"a": {
  "receipts": [
    { "meaning": "admitted", "said": "EAbc...", "keptUntil": "2026-11-15T00:00:00.000000+00:00" },
    { "meaning": "admitted", "said": "EXyz...", "keptUntil": "2026-11-15T00:00:00.000000+00:00" }
  ],
  "nextPoll": "2026-10-15T18:00:00.000000+00:00"
}
```

### 5.3 Poll

Route `/overture/poll`. Signed by a requester to ask for the status of overtures it sent (`5zj9qmg0`). Answered by a status report.

- `i`: the requester's AID. `ri`: the principal's AID.
- `a.saids`: REQUIRED. The SAIDs of the overtures asked about, one or more, read in the requester's scope.
- `a.waitUntil`: OPTIONAL (§6.7).

```json
"a": { "saids": ["EAbc...", "EXyz..."], "waitUntil": "2026-10-15T17:05:00.000000+00:00" }
```

### 5.4 Abort

Route `/overture/abort`. Signed by a requester to withdraw overtures it sent. Answered by a status report giving whatever holds for each overture when the abort arrives. An abort carries no `waitUntil`.

- `i`: the requester's AID. `ri`: the principal's AID.
- `a.saids`: REQUIRED. The SAIDs of the overtures to withdraw, one or more.

```json
"a": { "saids": ["EXyz..."] }
```

### 5.5 Status report

Route `/overture/status`. Signed by an agent (`30urjn80`, `8ryggr28`). It answers a poll, an abort, or a batch sent with `waitUntil`, and is what the agent sends when it delivers on its own initiative.

- `i`: the agent's AID. `ri`: the requester's AID. `dt`: the agent's time.
- `a.statuses`: REQUIRED. One item per overture the message references.
- `a.nextPoll`: OPTIONAL. It covers only the items still `pending` (§6.7).

Each status:

| Field | Required | Meaning |
|---|---|---|
| `said` | yes | The overture's SAID. |
| `status` | yes | `pending`, `unknown`, or one of the outcomes `completed`, `declined`, `expired`, `failed`, `aborted`, `precluded` (§6.3). |
| `results` | no | Only with an outcome. A list of results, each `{"said": ...}` for an artifact, optionally with `registry` for a credential checked by reference, or `{"aid": ..., "oobi": ...}` for a new identifier. On `aborted`, it lists anything already done. Each result the message attaches is committed by its SAID here. |
| `reason` | no | Free text, given only when the principal chooses (§6.3). |

```json
"a": {
  "statuses": [
    { "said": "EAbc...", "status": "completed", "results": [ { "said": "E...revocation event" } ] },
    { "said": "EXyz...", "status": "pending" },
    { "said": "EQrs...", "status": "unknown" }
  ],
  "nextPoll": "2026-10-15T18:00:00.000000+00:00"
}
```

## 6. Processing

### 6.1 Checking a received message

An agent checks a message in this order, and each step relies on the one before it:

1. **Bound.** It refuses a message larger than it is willing to parse.
2. **Parse.** It parses the CESR stream (§4.3), processing any KELs, TEL events and endpoint replies that precede the message by ordinary KERI rules.
3. **Currency and freshness.** It applies §4.4 to the message.
4. **Address.** It refuses a message whose `ri` is not its principal's AID (§4.1).
5. **Version.** It refuses a message whose major version it does not support (§9).
6. **Shape.** It validates the `a` block against the JSON Schema for the route and version.
7. **SAIDs.** It verifies the SAID of every overture in the message, and of every overture in each attached message, by the verification protocol of CESR's section "Self-addressing identifier (SAID)" (§6.2).
8. **Attached messages.** It verifies each attached message's signatures (§4.4) and each `triggeredBy` match (§6.8).
9. **Batch integrity.** It checks the batch rules of §6.5.
10. **Catalog.** For each overture, it refuses one whose `action` references a catalog entry it does not know, or whose `params` do not validate against that entry (§8).
11. **Preconditions.** It refuses an overture carrying a precondition it does not understand (§7).

A failure at steps 1 to 9 is a failure of the message. For a batch, a failure at steps 7 to 9 makes the batch malformed, and the agent MUST refuse the whole batch and admit none of it (`7f9ydc0f`): the requester built it wrongly, so nothing in it can be trusted to mean what was intended. A failure at steps 10 or 11 refuses that overture. After these checks, whether to admit an overture is the agent's decision, made behind the counter.

### 6.2 Overture identity

An overture is identified by its own SAID, the value of its `d` field, within the scope of the requester's AID (`7erf49uk`): an overture with the same SAID sent by a different requester is that requester's own. The SAID MUST be computed by the derivation protocol of CESR's section "Self-addressing identifier (SAID)", with the overture object as the self-addressed data, its fields in the order sent, serialized as JSON without whitespace, whatever serialization kind carries the batch (`48tfl3xj`). An agent MUST verify every overture's SAID that way (§6.1, step 7).

The SAID covers everything in the overture but not the batch's `dt`, so every resend of the same overture carries the same SAID, and different content is a different overture. Two sends are the same overture when they come from the same requester and carry an overture with the same SAID. Because a prerequisite's SAID must exist before an overture that depends on it can be hashed, a dependency cycle cannot be built.

Prerequisite links, polls, aborts, receipts, status reports and `triggeredBy` reference an overture by its SAID, and that SAID MUST remain usable on a transport other than the one that delivered the overture.

### 6.3 States and outcomes

An overture refused before admission has no state, and a later poll about it returns `unknown`. After admission, its only visible state is `pending`, from the receipt until its outcome, for as long as that takes (`36j5xvln`). An agent may track internally that the principal has agreed and the action is under way, but never shows it. An overture ends in exactly one outcome:

- `completed`: the action was carried out. Results are listed.
- `declined`: the principal, or the agent for it, chose not to act.
- `expired`: its start-by time (§7) passed before it was acted on.
- `failed`: it was agreed to but did not succeed.
- `aborted`: the requester's abort was honored. Results list anything already done.
- `precluded`: a prerequisite did not succeed, so it was never acted on (§6.5).

The agent's first signed report of an outcome fixes it; the agent MUST NOT later report a different status for that overture except `unknown` after its `keptUntil` time. Reasons are omitted by default, because they let a stranger probe the principal's policy, but a principal may choose to give them in `reason`.

A precondition that was predicted to be meetable, but that ends unmet, can only be judged a failure by the requester (§7).

### 6.4 Admission and refusal

An agent MAY refuse an overture or a batch it has not admitted without storing anything beyond aggregate counters and without signing anything, and that includes refusing by silence. The protocol never obliges an agent to store or sign anything about an overture before admitting it; implementations may store and sign more.

When an agent admits an overture, including one whose handling it defers (for example to quiet hours), it MUST return a receipt signed under its AID with meaning `admitted`, referencing the overture by its SAID, with the receipt's `dt` as the time of admission and with `keptUntil` (§6.6). One receipt message MAY carry `admitted` receipts for several overtures of a batch. If the batch carried `waitUntil` and the agent holds the exchange open (§6.7), it sends the receipt and then, in the same answer, a status report when it has one.

A receipt means the agent has agreed to treat the overture as a work item that later polls and aborts can refer to. It does not promise that the principal will act, or that an outcome will arrive within any time. It is also the agent's signed acknowledgement that it has been given notice of the overture's content. Notice runs only from an `admitted` receipt. Like every Overture signature, it is ephemeral evidence (§4.2); a claim that must outlive a rotation, such as notice that shifts liability for a lost license, belongs in a result.

*Advice to implementers:* before admitting a cold overture, an agent may require a stateless proof that the requester can receive replies, using a nonce of its own, such as a MAC over a time counter, the requester's AID and the overture's SAID. Whatever key state the agent resolves for the requester must be the key state that signed the overture.

*Advice to implementers:* a principal who does not want response timing to reveal how it decides can add random delays.

### 6.5 Batches and dependencies

An overture asks for exactly one action. It MAY reference prerequisites by SAID in `prereqs`, and these links form a dependency graph. Each prerequisite MUST be an overture the agent has already admitted from the same requester, or an overture carried in the same batch. A batch is malformed (§6.1) if a prerequisite is neither, if it carries the same overture twice, or if it carries a resend of an admitted overture under a different major version (§9).

A well-formed batch is judged overture by overture (`8zysn4nv`). An overture is acted on only after each of its prerequisites ends `completed`; if a prerequisite ends any other way, the overture that depends on it ends `precluded`, and overtures not linked to it are unaffected. Nothing is rolled back: an overture already acted on is not undone when a later one fails.

### 6.6 Agent memory and resends

An agent MUST remember each overture it has admitted (its SAID in the requester's scope, its time of admission and its status) for as long as it is `pending`, and MUST keep its outcome until the overture's `keptUntil` time (`8fwdvgmg`). Before that time the agent MUST NOT answer `unknown` about it. After it, `unknown` is allowed. Several agent AIDs answering at one endpoint MUST share this memory (`43lr8z7v`).

A requester MAY send an overture again until it holds an `admitted` receipt for it, and MUST NOT send it again after that (`5c5fzw97`). An agent answers a resend of an overture it has already admitted with a receipt that repeats the original time of admission and `keptUntil`. A requester that gets `unknown` for an admitted overture and still wants the act sends a new overture, with a new `u`, knowing the first may already have been carried out.

A requester MAY sign a `seen` receipt over the exn SAID of a status report that gives outcomes. After receiving it, the agent MAY forget those outcomes before their `keptUntil` time (`6fcnv3q0`).

*Advice to implementers:* `keptUntil` should comfortably exceed how long a requester plausibly needs to poll. Lasting proof of what was done comes from the results, not from the agent's memory.

### 6.7 Polling, waiting and aborts

Only the requester AID that sent an overture can see its status. To anyone else, the overture reads as `unknown`. A poll or abort MAY reference several overtures, and the status report gives one status per overture and is signed once (`0u4svfnq`). An abort is answered with whatever status holds when it arrives; an agent honors an abort if it still can, and reports `aborted` with anything already done.

A batch or a poll MAY carry `waitUntil`, asking the agent to hold the exchange open until that time by the agent's clock. The agent answers when it has an outcome for any referenced overture, when a referenced overture's status changes, or when the time is reached; if the time has passed when the message arrives, it answers at once. The agent MAY always decline to hold the exchange open, and MUST hold it only for a message that has passed §6.1's checks.

Receipts and status reports MAY carry `nextPoll`, the earliest time the agent expects any still-pending overture the message references to change (`0jjt97xh`). It covers only those overtures, is omitted when none is pending, and appears only in messages an agent signs. The requester need not honor it. Because the agent computes it from what is behind the counter, it SHOULD NOT reveal behind-the-counter facts.

*Advice to implementers:* an agent should give coarse or jittered `nextPoll` values. The gap between a message's `dt` and its arrival bounds the sender's clock skew plus transit time, which helps an agent judge how a sender's `waitUntil` maps onto its own clock.

### 6.8 Passing an overture on

A hop that passes an overture on, whether escalating through layers of agents or performing a double-consent introduction, MUST send its own overture, signed under its own AID, with its own `u` and `dt`, and MUST attach the original message unaltered as a nested group (§4.3) (`4uvlnnx4`). It never forwards the original as a live send and never wraps it in a message that says nothing of its own. Its overture's `triggeredBy` MUST reference the triggering overture's SAID in `said` and the attached message's exn SAID in `exn`. The receiving agent MUST refuse the hop's overture, as malformed, unless the attached message has exactly that exn SAID and contains an overture with exactly that SAID (`5xwgkz20`), and MUST verify the attached message's signatures as §4.4 requires.

Each hop is the requester of the next, and only each hop's own send is judged for freshness, so a slow layer never makes the overture stale. Escalation may nest to any depth.

Because the original sender's signature covers its whole message, passing an overture on discloses every overture in the message it arrived in, with their parameters, purposes and evidence SAIDs (`7gcqnese`). It also discloses the original's attached evidence, so a hop is a Discloser in ACDC's sense and MUST apply any terms of use the evidence's original disclosure carries; a hop that cannot pass the evidence on under its terms MUST NOT pass the overture on (`4y5jkshj`).

*Advice to implementers:* a requester should send any overture it expects to be passed on, such as an introduction, in its own batch, and should not attach evidence it does not want re-disclosed.

### 6.9 Delivery on the agent's initiative

Delivery initiated by the agent is an optional feature of each binding, used only when the requester has advertised an endpoint (`4yzm2pn6`). A requester advertises one by sending KERI's own signed endpoint replies before its message in the same stream (§4.3): `/end/role/add` authorizing the AID that receives for it, such as a mailbox it chose or its own agent, and `/loc/scheme` giving that AID's URL. These are governed by KERI's BADA rules, so a later message can carry newer ones. The agent delivers status reports there. The agent hosts no mailbox for requesters; a requester that advertises no endpoint polls.

When a requester works through its own agent, that agent is the requester toward the other agent, signs its own overtures (§6.8) and advertises its own endpoint.

### 6.10 Identity, key state and endpoints

A requester is identified by its AID, which may be transferable or non-transferable. If a requester's key changes under a non-transferable AID, it becomes a new requester, and its earlier overtures stay scoped to the old AID. Before it verifies a requester's signature, an agent needs that AID's key state: it may already have it, or the requester sends its KEL before the message (§4.3) or gives an OOBI. An agent MAY decline to resolve an OOBI from a requester whose overture it has not admitted. A requester need not anchor an overture's signature in its KEL, and if it rotates after admission, the overture stays admitted.

A requester MUST send every later message about an overture (a resend, poll or abort) to the endpoint where it first sent that overture, or to another location published by `/loc/scheme` for the agent AID that receipted it, and never to a different agent's endpoint (`43lr8z7v`).

Every message an agent sends MUST be signed under an agent AID the principal has authorized at the endpoint (§3). Its statements carry as much weight as the authority the agent can prove, through delegation or a GCD chain. If the principal incepted the agent's AID with KERI's Delegate-Is-Delegator (`DID`) trait, the agent's statements carry the principal's weight.

A transport binding MAY add its own transport authentication, such as RFC 9421 HTTP message signatures. It is used only for transport decisions, such as rate limits and blocking abusive callers, and the Overture engine never relies on it (`48r9sm0z`).

### 6.11 Results and the decision path

Every result is either a verifiable artifact, such as an ACDC, a KEL or TEL event, or an IPEX exchange, or a reference that resolves to one, such as an AID's OOBI or a credential SAID with its registry. Verifying a result needs nothing specific to Overture. The status report that gives the outcome states that each result it lists is a result of the overture. A result that can sign, such as a newly created AID, MAY state the same about itself, and an action's catalog entry MAY require that it does (`4662pten`).

Nothing the principal or an agent does can turn an overture into a commitment by the requester. Overture defines no message by which a requester commits. If an outcome would bind the requester, it does so only after the requester signs it separately, having seen it, through the launched action's own countersignature step.

Nothing in Overture reveals whether policy, a person or nested agents decided, though a principal may choose to say more. The principal's involvement shows only where a result must carry the principal's own signature. Declining never needs escalation. An act that lies outside the agent's signing authority must involve whoever holds that authority before it completes. Whoever signs a result MUST be able to prove a chain of representation back to the principal.

## 7. Preconditions

An overture MAY carry preconditions in its `preconditions` map. A precondition is the requester's statement, in advance, that the overture should not be started unless it can be carried out in a way that meets it (`83e2qr0z`). Preconditions are advisory: they are not obligations on the principal. An agent MUST NOT admit an overture that carries a precondition it does not understand, because advice can be set aside deliberately only by an agent that can read it. An agent SHOULD decline an overture rather than start it when it can see that a precondition will not be met. A precondition that was predicted to be meetable, but that ends unmet, can only be judged a failure by the requester.

Version 1 defines four:

- `startBy`: a time. An overture not acted on by then ends `expired`.
- `finishBy`: a time by which the requester wants the action finished.
- `signer`: who must sign a result for the requester to want it (`5yen7mup`). `principal` means the principal's AID, or a KERI delegate of it created with the Delegate-Is-Delegator (`DID`) trait, which can be checked from KELs alone. `representative` means the principal, or any signer that proves a chain of representation to the principal, through KERI delegation or a chain of GCD credentials linked through `issuer` edges. An overture without `signer` is treated as carrying `representative`. The requester checks who signed any result it receives.
- `audience`: an object with `aid`, a downstream relying party's AID, and `nonce`, that party's challenge, carried unchanged as an opaque value (`35d29vn5`). It says the requester wants a result only if the result binds itself to that audience and nonce. The result does the binding; the overture carries only the inputs, and the requester checks the binding itself. The audience is not the party on whose behalf the requester acts, which the requester's authority evidence shows.

Understanding `audience` means recognizing it. An agent that cannot produce a result bound to the audience and nonce SHOULD decline the overture, and until a catalog entry defines a result that carries the binding, every agent will (`4gqmgjxf`). Using `audience` tells the principal, everyone behind the counter and every hop which relying party the requester means to present the result to, and the binding may keep that relying party's AID in the result. A requester that does not want that known should not use it.

A hop's own overture SHOULD NOT carry a `finishBy` later than the `finishBy` of the overture it passes on, so that the outer request bounds the inner one.

*Advice to implementers:* a relying party should make its nonce unpredictable, because a guessable challenge lets someone produce a result in advance. Clock agreement is already assumed by the freshness checks of §4.4, and preconditions are judged by the agent's clock.

## 8. The action catalog

An overture identifies the one action it asks for by the SAID of a catalog entry (`0nztkj2q`). Anyone may define catalog entries, and new entries need no change to this protocol. An agent MUST refuse, before admission, an overture whose `action` references an entry it does not know.

A catalog entry MUST be a JSON Schema, in the JSON Schema 2020-12 dialect, that validates an overture's `params`, SAIDified and verified by the schema rules of ACDC 1.0, so that its top-level `$id` is a bare SAID of the entry. It is not called an ACDC schema, because its instances are parameters, not ACDCs. Any change to an entry makes a new entry with a new SAID, so a signed overture commits to exactly which act it requests. In the entry:

- `title` is a label for people, and `description` is the standard description of what the action does (§5.1 `purpose` is the requester's own words, not this).
- The annotation keyword `overture` holds an object with three fields: `gcdSchema`, the SAID of the GCD schema whose act grid the entry uses; `acts`, the list of (effect, state-kind) points the action occupies on that grid, each written as GCD writes an entry of `acts`, such as `"create record"`; and `targets`, the list of JSON Pointers into `params` that designate the act's targets, GCD's third coordinate. With these, a policy engine can check an overture against a GCD credential without knowing Overture.
- The entry MAY state, in its description, that a result able to sign must state itself to be a result of the overture (§6.11), and which step of a launched protocol its result is.

An action whose result exists to keep the principal unlinkable, such as creating a relationship AID, SHOULD NOT use KERI delegation from the principal as the result's representation evidence, because a delegated AID names its delegator in its inception event for anyone to read. Its entry SHOULD specify evidence disclosed only to the requester, such as a GCD credential blinded with `u`, as the default (`7l9nr4dn`).

This specification ships a set of initial entries, enough to run the test cases in Appendix A. They are published as separate files beside it.

### 8.1 Relationship to IPEX

An IPEX `apply` asks a connected party to disclose a credential. It carries no admission, receipt, status, preconditions, abort, or proof of the requester's authority. Overture provides those for a requester the issuer does not know, then launches IPEX: the agent answers an admitted issuance overture by starting an IPEX exchange at `offer` or `grant`, whose first message sets `p` to the exn SAID of the batch that carried the overture (`535qked4`). A requester already connected to an issuer may use IPEX `apply` directly. The issuance entry states which IPEX step its result is.

## 9. Versioning

Every Overture message's `a` block MUST carry `version`, a string of two decimal integers written `major.minor`, starting at `"1.0"` (`3vpll4pd`, `0n0cy9mx`). An agent MUST refuse a message whose major version it does not support.

Within a major version, a minor version MAY add optional fields, which an older reader ignores, except inside `preconditions`, where an unknown key makes the agent refuse the overture (§7). A new precondition therefore needs only a minor version. A new status value, a new receipt meaning, or a changed meaning of any existing field needs a new major version. The JSON Schemas for each message allow additional properties everywhere except in closed sets: statuses, receipt meanings and `signer` values.

An overture is bound to the major version of the batch that first carried it. A resend MUST use the same major version (§6.5). A message attached inside another is judged by its own version, and an agent that does not support that version refuses the message carrying it.

Because refusal may be silent (§6.4), a binding MAY report an unsupported major version at the transport layer without signing anything, so that a requester can tell a version problem from a policy decision (§10).

## 10. HTTP binding

A requester sends each stream by HTTP `POST` to the agent's endpoint URL (`2mgg0fn7`), the agent's general KERI ingress, not an Overture-specific path; the `/overture/` route inside the message selects Overture. The request body is the whole CESR stream (§4.3): any KELs, TEL events and endpoint replies, then the Overture message framed as a message + attachments group, with `Content-Type: application/cesr`. The request MUST NOT carry a `CESR-ATTACHMENT` header.

The agent's answer travels in the body of the response to the `POST` that carried the message, as a CESR stream with `Content-Type: application/cesr` and status `200` (`0y83jfj7`). For a batch the answer is a receipt, followed by a status report if the agent held the exchange open and has one; for a poll or an abort it is a status report. A `204` response means the agent has nothing to send, including when it refuses silently. When the agent refuses a message only because it does not support its major version, it MAY answer `400` with a body of type `application/problem+json` ([RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)) whose `supportedMajors` member lists the major versions it supports; nothing in that answer is signed.

Holding the exchange open for `waitUntil` is long polling as described in RFC 6202: the agent holds the response until it has an answer or the time passes. Delivery on the agent's initiative (§6.9) is a `POST` of a status report, framed the same way, to the URL the requester advertised.

*Advice to implementers:* an agent should cap how long it holds a response open and how many it holds per requester AID, and may rate-limit by transport-level identity. keripy's HTTP ingress expects one message in the body with its attachments in a `CESR-ATTACHMENT` header, which is too small for nested messages, and answers every `exn` with `204`. An implementation built on it must accept the whole-stream form at the same URL, recognizable by the absent header, and answer Overture routes inline.

## 11. Security considerations

**Replay and stale keys.** §4.4 makes every engine check each message against the signer's latest establishment event and refuse stale or replayed messages. Without these checks, a thief holding a rotated-out key could have a fresh batch admitted under the requester's AID.

**Retrograde attacks on passed-on messages.** Because nothing is anchored, a signature made before a rotation cannot be told from one made later by a thief holding the old key. So a passed-on message is judged against its signer's current key state, and refused if the signer has rotated since (`3j0mdxh4`). An honest requester that rotates while its overture is being passed on has the hop's overture refused, and the hop must ask it to send again.

**Rotation after admission.** An overture stays admitted if its requester rotates (§6.10). After a rotation forced by compromise, the requester's remedy is to abort its pending overtures under its new key state, which does nothing for an overture already completed (`2j74vu2p`).

**Double execution.** A requester never resends an overture after its `admitted` receipt (§6.6), and an agent never answers `unknown` about an admitted overture before its `keptUntil` time. Together these keep an action that is not idempotent, such as issuing a credential, from running twice because state was lost.

**Malformed and oversized input.** An agent bounds a message's size before parsing it and checks it in the order of §6.1, so that no step trusts input an earlier step has not checked. A malformed batch is refused whole, and refusal before admission costs nothing (§6.4).

**Held connections.** Holding an exchange open is always at the agent's discretion, and only for a message that has passed §6.1's checks, so an unauthenticated flood cannot hold anything open (§10).

**Who answers for the principal.** Overture uses KERI's `agent` endpoint role, which keripy defines although the KERI specification's role list does not yet include it. Some hosts, such as KERIA, already authorize an operator-keyed AID in that role for their own plumbing. If such a host also installs Overture's handlers, that AID answers overtures for the principal, and its `admitted` receipts give notice (`8drpdx72`). A principal using such a host must decide deliberately whether to let it answer overtures. An agent's statements carry only the weight it can prove (§6.10), so a requester relying on notice checks that weight.

**Transport authentication.** A transport signature, such as RFC 9421 over HTTP, authenticates only the transport exchange. The Overture engine bases every decision on the signature on the Overture message, so a transport-layer allow-list cannot stand in for admission (`48r9sm0z`).

**Purpose text.** A stranger writes `purpose`. A person deciding on an overture should be able to see the exact signed overture, never only a summary rendered from it.

**Unknown preconditions and actions.** An agent refuses an overture with a precondition it does not understand (§7) or an action whose entry it does not know (§8), so a later extension is never silently ignored by an earlier agent.

## 12. Privacy considerations

**The decision path.** Nothing in Overture reveals whether policy, a person or nested agents decided (§6.11). Reasons are omitted by default, and a status report shows only `pending` until an outcome. `nextPoll` and response timing can still reveal behind-the-counter facts, such as when a person is available; agents should give coarse or jittered values and may add random delays.

**Status visibility.** Only the requester that sent an overture can see its status; to anyone else it reads as `unknown`, which is also what an overture that was never sent reads as.

**Blinded SAIDs.** An overture's `u` keeps its SAID, which travels in receipts, status reports, `prereqs` and `triggeredBy`, from revealing a guessable overture's content.

**Passing an overture on.** A hop discloses every overture in the message the original arrived in, with their parameters, purposes and evidence SAIDs (`7gcqnese`), and the original's evidence, under that evidence's terms of use (§6.8). A requester controls this by sending an overture it expects to be passed on in its own batch, and by not attaching evidence it does not want re-disclosed.

**Relationship AIDs.** A delegated AID names its delegator for anyone who resolves it, so an action meant to keep the principal unlinkable should not prove representation by delegation from the principal (§8).

**Audience.** The `audience` precondition tells the principal, everyone behind the counter and every hop which relying party the requester will present the result to, and the result may keep that relying party's AID (§7).

**Requester endpoints.** A requester that advertises an endpoint (§6.9) discloses where it can be reached. By default it advertises none and polls.

## Appendix A. Test cases

- **Double-consent introduction** (after Aries RFC 0028). R asks agent A, acting for P: "introduce me to T". A sends T's agent its own overture, attaching R's original unaltered (§6.8). This tests passing an overture on, an outer `finishBy` bounding the inner one, what T may learn about R before consenting (only what R sent in that one batch), how the status reports R receives protect T's privacy, and a result that means "invitation delivered" rather than "relationship formed".
- **"Start a protocol with me"**, using coin flip (Aries RFC 0193) as the example, with the protocol identified in `params`.
- **"Challenge me"**: the agent opens an IPEX `apply`, with `p` linking back to the exn that carried the overture.
- **Revoke and reissue** a license after loss: a prerequisite link (§6.5) and the `admitted` receipt as notice within the interaction (§6.4).
- **A relationship AID**: an OOBI as the result, with the new AID stating that it is a result of the overture (§6.11), and representation shown without delegation (§8).
- **Preconditions**: an overture that finishes after its `finishBy`, which the requester judges; an overture carrying a precondition the agent does not understand, refused before admission; and one where the `representative` default rules out a third-party signer (§7).
- **Lost state**: a poll before `keptUntil` never returns `unknown` for an admitted overture, and a requester's `seen` lets the agent forget early (§6.6).
