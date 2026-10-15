# Overture Protocol: messages

*Approved message layouts. Each one is added here when Daniel Hardman approves it. Requirements are in [`requirements.md`](requirements.md), and the reasons for each choice are in [`this.i`](../this.i) decision nodes. Route names are not chosen yet.*

Every Overture message is a KERI v2 `exn` (`7cw0yhrk`). Envelope fields keep keripy's names: `v t d i ri x p dt r q a`. Fields inside `a` are Overture's own and have expressive camelCase names.

## Overture

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
| `d` | yes | The overture's own SAID. It stays the same across resends of the same content. |
| `overtureId` | yes | Chosen by the requester, scoped to its AID (R14). |
| `action` | yes | The catalog identifier of the one action asked for (R9, R11). |
| `params` | yes | The action's parameters, per its catalog entry (R11). |
| `prereqs` | no | Overture ids that must succeed first (R9). |
| `preconditions` | no | A map of preconditions (R5): `startBy`, `finishBy`, `signer` (R6), `audience` with `aid` and `nonce` (R7). |
| `purpose` | no | Text for a person, saying why the requester asks (R8). |
| `triggeredBy` | no | The SAID of the overture that caused this one, attached whole as a nested substream (R10, `4uvlnnx4`). |
| `evidence` | no | SAIDs of the authority evidence the overture relies on (R1, R10). |

Attachments: the requester's signatures; optionally its KEL (R23); the overture named by each `triggeredBy`; and the authority evidence named by each `evidence`.

```json
"a": {
  "overtures": [
    { "d": "E...", "overtureId": "rr-1", "action": "<revoke license>", "params": { } },
    { "d": "E...", "overtureId": "rr-2", "action": "<issue license>", "params": { },
      "prereqs": ["rr-1"], "purpose": "Replace my lost license." }
  ]
}
```

## Receipt

Signed by the agent to mark admission, or by either party to say it has seen a message (R13, R17).

- `i`: the signer's AID.
- `ri`: the AID of the party the receipt is sent to.
- `dt`: the signer's time. On an `admitted` receipt it is the time of admission.
- `a.receipts`: a list of one or more receipts (`9z0lpky7`).
- `a.nextPoll`: optional, and only in a receipt the agent signs. The earliest time the agent expects any still-pending overture this message references by `overtureId` to change (`0jjt97xh`). Omitted when nothing referenced is pending.

Each receipt:

| Field | Required | Meaning |
|---|---|---|
| `meaning` | yes | `admitted` (the agent admitted the overture) or `seen` (the signer received the item, without commitment). |
| `overtureId` | for an overture | The receipted overture's id. |
| `said` | yes | For an overture, its own SAID (`d`), the digest of the admitted content. For a message, its exn SAID. |

```json
"a": {
  "receipts": [
    { "meaning": "admitted", "overtureId": "rr-1", "said": "E..." },
    { "meaning": "admitted", "overtureId": "rr-2", "said": "E..." }
  ],
  "nextPoll": "2026-10-15T18:00:00.000000+00:00"
}
```

## Poll

Signed by the requester to ask for the state or outcome of overtures it sent (R16). Answered by a status report.

- `i`: the requester's AID.
- `ri`: the principal's AID (`6f7mlrg6`).
- `a.overtureIds`: the overture ids asked about, in the requester's scope (R14).
- `a.waitUntil`: optional. The time until which the agent is asked to hold the exchange open (R16, `5zj9qmg0`).

```json
"a": { "overtureIds": ["rr-1", "rr-2"], "waitUntil": "2026-10-15T17:05:00.000000+00:00" }
```

## Abort

Signed by the requester to withdraw overtures it sent (R15). Answered by a status report giving whatever holds for each overture when the abort arrives.

- `i`: the requester's AID.
- `ri`: the principal's AID.
- `a.overtureIds`: the overture ids to withdraw.

```json
"a": { "overtureIds": ["rr-2"] }
```
