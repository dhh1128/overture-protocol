# Overture Protocol

Overture is a protocol for proposing an action to someone else's agent. An external party, authenticated by a key but not necessarily identified, sends a signed proposal to an agent acting for a named principal. Examples: "issue me a credential", "revoke this one", "introduce me to someone you know", "challenge me to prove something", "create an identifier for our relationship", "start protocol X with me". The agent answers at once with a signed receipt or a refusal. Later it reports a final disposition, and that disposition carries verifiable evidence of whatever was done.

Overture is to an agent what the counter is to a shop. Anyone can walk up and ask, and the counter takes what it is empowered to handle and turns away the rest. What happens behind the counter (a policy engine, an escalation to the principal, layers of sub-agents) is never disclosed by the protocol.

## Design commitments

- **Proposals are requests, never offers.** Anything that binds the requester takes a separate signature from the requester, made after it has seen the outcome.
- **The decision path stays hidden.** Receipts, status and dispositions never reveal whether policy or a human decided. A principal's involvement shows up only on an artifact that, by its nature, only the principal can sign.
- **Outcomes can be checked with ordinary tools.** Results are KERI/ACDC artifacts, or references that resolve to them, carried as CESR attachments. Checking them needs nothing specific to Overture.
- **Strangers cost nothing.** An agent may refuse an unadmitted proposal without storing or signing anything. A signed receipt is the point at which the agent takes on the obligation to answer, and it also serves as notice.
- **Transport-independent.** Messages are signed, self-addressing artifacts. HTTP (with RFC 9421 message signatures) is one binding. BLE, NFC and others are meant to work too.

## Status

Requirements stage. The requirements are approved and are in [`docs/requirements.md`](docs/requirements.md). Message definitions, JSON Schemas, test vectors and a reference stand-in agent will follow.

Overture is being designed under a clean-room process. See [`docs/provenance.md`](docs/provenance.md).

## Relationship to other specifications

Overture builds on [KERI](https://github.com/trustoverip/kswg-keri-specification), [ACDC](https://github.com/trustoverip/kswg-acdc-specification) and CESR. It is meant to sit beside IPEX, which assumes the parties are already connected and covers only disclosure, and to launch IPEX and other exchanges rather than redefine them. The intended long-term home is the KERI Foundation or WebOfTrust.

## License

[Apache-2.0](LICENSE).
