"""WitnessADR Core — tamper-evident hash-chain engine for AI agent audit logs."""

__version__ = "0.1.0"

from .canonical import canonicalize
from .hashing import compute_entry_hash
from .redaction import HashOnlyRedactor, Redactor, RegexPIIRedactor
from .schema import validate_entry
from .signing import generate_keypair, sign_hash, verify_signature
from .verify import VerificationResult, verify_chain

__all__ = [
    "canonicalize",
    "compute_entry_hash",
    "generate_keypair",
    "sign_hash",
    "verify_signature",
    "validate_entry",
    "verify_chain",
    "VerificationResult",
    "HashOnlyRedactor",
    "RegexPIIRedactor",
    "Redactor",
]
