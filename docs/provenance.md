# Provenance

The Overture Protocol is being designed under a clean-room process, so that its independence from a prior protocol covering similar ground can be shown. That prior protocol's design and implementation are under copyright restrictions the author must respect.

## The process

- **Requirements, not mechanism.** The design team, an AI assistant working with Daniel Hardman, never read the prior protocol's specification, code, interfaces or vocabulary. Before reading anything, it ran filename-only searches to build a list of files that mention the prior protocol, and it excluded them.
- **A separate extraction step.** Some product repositories that are clients of the prior protocol describe what they *need* from such a protocol. To use those needs as requirements, a separate extraction agent ran in a [bubblewrap](https://github.com/containers/bubblewrap) sandbox. Only an allowlist of paths existed inside it, and the prior protocol's source tree was not one of them. The agent wrote a requirements-only extract: client needs in neutral wording, with no mechanism, interfaces or coined terms. Passages it judged to describe the prior protocol were listed by location only. Daniel Hardman reviewed and approved the extract before the design team read it. The extraction agent's context was then discarded.
- **Everything is logged.** Every prompt Daniel Hardman gave, every source consulted, every source excluded, every subagent instruction, and one disclosed slip (a research subagent read three files before discovering they mentioned the prior protocol, and relayed nothing from them) are recorded in a timestamped git history.

## The record

The full record cites private repositories, so it is kept in a private git repository rather than published here. This repository commits to it:

| Field | Value |
|---|---|
| Record repository | private; available to an auditor or counsel on request |
| First commit | 2026-10-13T00:33:04Z |
| Commit at the time this repository was created | `4942eaaa46566042f3a657e051bd589ba79eaf30` |
| Commits in the record at that point | 32 |

A git commit SHA commits to the full content and history of the record up to that point. Anyone later given access to the record can check that it matches.

## What came from where

Every requirement in [`requirements.md`](requirements.md) traces to one of four sources:
- Daniel Hardman's own statements.
- Public specifications: KERI, ACDC/IPEX, CESR, DIDComm v2, and the Aries RFCs.
- Public Bakobo work: the GCD credential in [bakobo/schema](https://github.com/bakobo/schema), and [fiki](https://github.com/bakobo/fiki).
- The approved client-needs extract described above.

The design discussion that turned those sources into settled requirements is part of the record.
