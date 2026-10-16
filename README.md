# Overture Protocol

Overture is a protocol for asking someone else's agent to have its principal take one action. A requester, identified by its AID but not necessarily known to anyone, sends a signed overture to an agent that acts for a principal. Examples: "issue me a credential", "revoke this one", "introduce me to someone you know", "challenge me to prove something", "create an identifier for our relationship", "start protocol X with me". An agent that admits the overture returns a signed receipt; it may also refuse, and refusing costs it nothing. The requester polls for status, and the agent's status report eventually gives the overture's outcome, with verifiable results for whatever was done.

Overture is to an agent what the counter is to a shop. Anyone can walk up and ask, and the counter takes what it is empowered to handle and turns away the rest. What happens behind the counter (a policy engine, an escalation to the principal, layers of sub-agents) is never disclosed by the protocol.

## Design commitments

- **Overtures are requests, never offers.** Nothing the principal or an agent does can turn an overture into a commitment by the requester. Anything that would bind the requester takes the requester's own separate signature, made after it has seen the outcome.
- **The decision path stays hidden.** Receipts and status reports never reveal whether policy, a person or nested agents decided. A principal's involvement shows only on a result that, by its nature, only the principal can sign.
- **Results can be checked with ordinary tools.** Results are KERI/ACDC artifacts, or references that resolve to them. Checking them needs nothing specific to Overture.
- **Strangers cost nothing.** An agent may refuse an overture it has not admitted without storing or signing anything. A signed receipt marks admission: the agent has agreed to treat the overture as a work item, and has been given notice of its content. It does not promise that the principal will act.
- **Transport-independent.** Every message is a signed KERI exn that verifies with any transport stripped away. HTTP is one binding; BLE, NFC and others are meant to work too.

## Status

Design stage. The approved requirements are in [`docs/requirements.md`](docs/requirements.md) and the message layouts in [`docs/messages.md`](docs/messages.md); the reasons for each choice are decision nodes in [`this.i`](this.i). The normative specification, JSON Schemas, test vectors and a reference stand-in agent come next.

Overture is being designed under a clean-room process. See [`docs/provenance.md`](docs/provenance.md).

## Relationship to other specifications

Overture builds on [KERI](https://github.com/trustoverip/kswg-keri-specification), [ACDC](https://github.com/trustoverip/kswg-acdc-specification) and [CESR](https://github.com/trustoverip/kswg-cesr-specification). It is meant to sit beside IPEX, which assumes the parties are already connected and covers only disclosure, and to launch IPEX and other exchanges rather than redefine them. The intended long-term home is the KERI Foundation or WebOfTrust.

## License

[Apache-2.0](LICENSE).
