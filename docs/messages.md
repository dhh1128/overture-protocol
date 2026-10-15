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
