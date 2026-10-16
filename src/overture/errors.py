"""Why the reference package refuses a message or an overture (this.i 0s3s9prx).

Codes follow the error-code grammar <sorter>.<descriptor>[.<sub>].<disposition>. They are
logged and never travel in a signed message, because refusal may be silent (spec §6.4).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Code:
    code: str
    title: str


TOO_LARGE = Code("e.input.range.size.f", "The stream is larger than this agent will parse.")
MALFORMED = Code("e.input.format.message.f", "The message is not a well-formed Overture message.")
NO_MESSAGE = Code("e.input.missing.message.f", "The stream carries no Overture message.")
ROUTE_UNSUPPORTED = Code("e.feature.unsupported.route.f",
                         "The message's route is not one this agent answers.")
WRONG_PRINCIPAL = Code("e.input.range.recipient.f",
                       "The message is not addressed to the principal this agent acts for.")
VERSION_UNSUPPORTED = Code("e.feature.unsupported.version.f",
                           "The message's major version is not one this agent supports.")
SHAPE = Code("e.input.format.shape.f", "The message's a block does not match its schema.")
KEY_STATE_MISSING = Code("e.state.missing.kel.r",
                         "This agent lacks the key state that the signature needs.")
KEYS_ROTATED = Code("e.proof.message.rotated.f",
                    "The message was signed under keys its signer has since rotated away.")
SIGNATURE_INVALID = Code("e.proof.message.sig.f",
                         "The message's signatures do not verify against its sender's keys.")
NOT_FRESH = Code("e.rule.freshness.window.f",
                 "The message's time falls outside this agent's freshness window.")
REPLAYED = Code("e.rule.freshness.replay.f", "The message was already accepted once.")
SAID_MISMATCH = Code("e.proof.overture.said.f", "An overture's d is not the SAID of its content.")
ATTACHED_INVALID = Code("e.proof.attached.sig.f",
                        "An attached message's signatures do not verify.")
TRIGGER_MISMATCH = Code("e.input.format.triggered-by.f",
                        "A triggeredBy does not match the attached message and overture.")
EVIDENCE_MISSING = Code("e.input.missing.evidence.f",
                        "An evidence SAID, or a link of its chain, has no attached ACDC.")
EVIDENCE_STATE_MISSING = Code("e.state.missing.tel.r",
                              "The agent lacks the TEL or schema needed to check attached evidence.")
EVIDENCE_INVALID = Code("e.proof.evidence.chain.f", "Attached evidence does not verify.")
EVIDENCE_REVOKED = Code("e.proof.evidence.revoked.f",
                        "Attached evidence relies on a revoked credential.")
DUPLICATE = Code("e.input.format.duplicate.f", "A batch carries the same overture twice.")
PREREQ_UNKNOWN = Code("e.state.missing.prereq.f",
                      "A prerequisite is neither admitted from this requester nor in the batch.")
MAJOR_CHANGED = Code("e.state.conflict.version.f",
                     "A resend of an admitted overture uses a different major version.")
ACTION_UNKNOWN = Code("e.feature.unsupported.action.f",
                      "An overture's action references a catalog entry this agent does not know.")
PARAMS_INVALID = Code("e.input.format.params.f",
                      "An overture's params do not validate against its catalog entry.")
PRECONDITION_UNKNOWN = Code("e.feature.unsupported.precondition.f",
                            "An overture carries a precondition this agent does not understand.")


class Refusal(Exception):
    """A refusal with its code and a sentence of detail."""

    def __init__(self, code: Code, detail: str = ""):
        self.code = code
        self.detail = detail or code.title
        super().__init__(f"{code.code}: {self.detail}")


def matches(pattern: str, code: str) -> bool:
    """Prefix match when ``pattern`` ends in a dot, exact match otherwise."""
    return code.startswith(pattern) if pattern.endswith(".") else code == pattern
