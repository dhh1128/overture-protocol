# Overture Protocol: messages

*Approved message layouts. Each one is added here when Daniel Hardman approves it. Requirements are in [`requirements.md`](requirements.md), and the reasons for each choice are in [`this.i`](../this.i) decision nodes.*

Every Overture message is a KERI v2 `exn` (`7cw0yhrk`). Envelope fields keep keripy's names: `v t d i ri x p dt r q a`. Fields inside `a` are Overture's own and have expressive camelCase names. Routes are listed with each message (`970lu92k`). Every message's `a` block also carries `version`, required, written major.minor and starting at `"1.0"`; an agent refuses a major version it does not support, and a minor version only adds optional fields (`3vpll4pd`). The examples below omit it.

## Batch

Route: `/overture/batch`.

Sent by a requester to carry one or more overtures (a batch) to the principal.

- `i`: the requester's AID (R1, R23).
- `ri`: the principal's AID (R3, `6f7mlrg6`).
- `dt`: the send time, by which replay protection judges each send (R2).
- `x`, `p`, `q`: empty.
- `a.overtures`: a list of one or more overtures (`5xwgkz20`).
- `a.waitUntil`: optional. The time until which the agent is asked to hold the exchange open (R16).

Each overture:

| Field | Required | Meaning |
|---|---|---|
| `d` | yes | The overture's own SAID, which identifies it within the requester's scope (R14, `7erf49uk`). It is computed by CESR's SAID protocol over the overture serialized as JSON, whatever kind the exn uses (`48tfl3xj`). It stays the same across resends. |
| `u` | yes | A salty nonce of about 128 bits of entropy, made fresh for each overture, so two identical asks are two overtures and the SAID blinds the content (R14). |
| `action` | yes | The SAID (`$id`) of the catalog entry for the one action asked for (R9, R11, `0nztkj2q`). |
| `params` | yes | The action's parameters, which MUST validate against the catalog entry referenced by `action` (R11). |
| `prereqs` | no | SAIDs of overtures that must succeed first (R9). |
| `preconditions` | no | A map of preconditions (R5): `startBy`, `finishBy`, `signer` (R6), `audience` with `aid` and `nonce`, the relying party's challenge carried unchanged (R7). |
| `purpose` | no | Text for a person, saying why the requester asks (R8). |
| `triggeredBy` | no | An object referencing the overture that caused this one: `said`, that overture's SAID, and `exn`, the exn SAID of the message that carried it. That message is attached whole as a nested substream (R10, `4uvlnnx4`). The agent refuses this overture unless the attached message has exactly that exn SAID and contains an overture with exactly that SAID. `exn` commits to the whole attached message; `said` selects which of its overtures is meant (`5xwgkz20`). |
| `evidence` | no | SAIDs of the authority evidence the overture relies on (R1, R10). |

Attachments: the requester's signatures; optionally its KEL (R23); the message referenced by each `triggeredBy`; and the authority evidence named by each `evidence`.

```json
"a": {
  "overtures": [
    { "d": "EAbc...", "u": "0AB3...", "action": "<revoke license>", "params": { } },
    { "d": "EXyz...", "u": "0AQ9...", "action": "<issue license>", "params": { },
      "prereqs": ["EAbc..."], "purpose": "Replace my lost license." }
  ]
}
```

## Receipt

Route: `/overture/receipt`.

Signed by the agent to mark admission, or by either party to say it has seen a message (R13, R17).

- `i`: the signer's AID.
- `ri`: the AID of the party the receipt is sent to.
- `dt`: the signer's time. On an `admitted` receipt it is the time of admission.
- `a.receipts`: a list of one or more receipts (`9z0lpky7`).
- `a.nextPoll`: optional, and only in a receipt the agent signs. The earliest time the agent expects any still-pending overture this message references to change (`0jjt97xh`). Omitted when nothing referenced is pending.

Each receipt:

| Field | Required | Meaning |
|---|---|---|
| `meaning` | yes | `admitted` (the agent admitted the overture) or `seen` (the signer received the item, without commitment). |
| `said` | yes | For `admitted`, the overture's own SAID (`d`), which is also the digest of the admitted content. For `seen`, the exn SAID of the message seen. |

```json
"a": {
  "receipts": [
    { "meaning": "admitted", "said": "EAbc..." },
    { "meaning": "admitted", "said": "EXyz..." }
  ],
  "nextPoll": "2026-10-15T18:00:00.000000+00:00"
}
```

## Poll

Route: `/overture/poll`.

Signed by the requester to ask for the state or outcome of overtures it sent (R16). Answered by a status report.

- `i`: the requester's AID.
- `ri`: the principal's AID (`6f7mlrg6`).
- `a.saids`: the SAIDs of the overtures asked about, in the requester's scope (R14).
- `a.waitUntil`: optional. The time until which the agent is asked to hold the exchange open (R16, `5zj9qmg0`).

```json
"a": { "saids": ["EAbc...", "EXyz..."], "waitUntil": "2026-10-15T17:05:00.000000+00:00" }
```

## Abort

Route: `/overture/abort`.

Signed by the requester to withdraw overtures it sent (R15). Answered by a status report giving whatever holds for each overture when the abort arrives.

- `i`: the requester's AID.
- `ri`: the principal's AID.
- `a.saids`: the SAIDs of the overtures to withdraw.

```json
"a": { "saids": ["EXyz..."] }
```

## Status report

Route: `/overture/status`.

Signed by the agent. It answers a poll, an abort, or an overture sent with `waitUntil`, and is what the agent sends when it delivers on its own initiative (R16, `30urjn80`).

- `i`: the agent's AID.
- `ri`: the requester's AID.
- `dt`: the agent's time.
- `a.statuses`: one item per overture the message references (`8ryggr28`).
- `a.nextPoll`: optional. As in the receipt, it covers only the items still `pending`.

Each status:

| Field | Required | Meaning |
|---|---|---|
| `said` | yes | The overture's SAID (R14). |
| `status` | yes | `pending`, `unknown`, or one of the outcomes `completed`, `declined`, `expired`, `failed`, `aborted`, `precluded` (R15). |
| `results` | no | Only on an outcome. Each result is `{said}` for an artifact, optionally with `registry` for a credential checked by reference, or `{aid, oobi}` for a new identifier (R18). On `aborted`, anything already done. |
| `reason` | no | Free text, given only when the principal chooses (R15). |

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
