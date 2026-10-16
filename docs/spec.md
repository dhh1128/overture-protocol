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

- An Overture message MUST be sent as a body-with-attachments group (count code `-U`, or `--U` when large), with its attachments in one attachment group (`-V` or `--V`).
- Each attached message that the body commits to, whether a passed-on message, an ACDC of an evidence chain or an attached result, MUST be a nested body-with-attachments group inside that attachment group, carrying its own signatures.
- KELs, TEL events and endpoint replies MUST NOT be nested. They are sent before the Overture message in the same stream, as top-level messages, so that the receiver's ordinary KERI processing learns the key state before it verifies the Overture message.

*Advice to implementers:* keripy's parser delivers nested groups to an `exn` handler only for a fixed set of routes, so an implementation built on it must give `/overture/` routes their nests (`630f824j`).

### 4.4 Freshness and currency

An Overture engine MUST verify each message it receives against the signer's latest establishment event, and MUST refuse a message whose `dt` falls outside its freshness window by its own clock, or that replays a message it has already accepted (`35wllumn`). These are Overture's own requirements, whatever performs them, and an engine MUST NOT run without them.

The signatures on a passed-on message attached inside another (§6.8) are verified, at every depth of nesting, against each signer's latest establishment event, and the carrying message is refused if a signer has rotated since signing (`3j0mdxh4`). Such a message is not judged for freshness, because it may be old.

*Advice to implementers:* keripy performs both checks only in KRAM, which `Kevery` leaves off unless `enableKram` is set; without KRAM, keripy verifies a signature against whichever establishment event it cites and never checks freshness. KRAM checks only the message received, never one attached inside it, so an implementation checks attached messages itself. An implementation that relies on KRAM should refuse to start when KRAM is off, unless the operator passes an explicit override, and should warn at every start with that override.
