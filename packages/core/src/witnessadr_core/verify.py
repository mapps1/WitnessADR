"""Chain integrity verification."""

from dataclasses import dataclass

from .hashing import compute_entry_hash
from .signing import verify_signature


@dataclass(frozen=True)
class VerificationResult:
    """Result of verifying a hash chain."""

    is_valid: bool
    total_entries: int
    first_broken_index: int | None
    broken_reason: str | None

    def __str__(self) -> str:
        if self.is_valid:
            return f"PASS — {self.total_entries} entries verified"
        return (
            f"FAIL — broken at entry index {self.first_broken_index} "
            f"of {self.total_entries}: {self.broken_reason}"
        )


def verify_chain(
    entries: list[dict],
    public_key_bytes: bytes | None = None,
) -> VerificationResult:
    """Verify the integrity of an ADR hash chain.

    Checks performed for each entry in order:
    1. sequence_number is contiguous (no gaps or reordering)
    2. prev_hash matches the preceding entry's entry_hash
    3. entry_hash matches the recomputed hash over the entry's content
    4. If public_key_bytes provided: signature is valid

    Returns immediately at the FIRST broken entry — the index and reason
    are precisely attributed to the entry where the problem occurs,
    not a downstream symptom.

    Args:
        entries: List of ADR entry dicts in sequence order.
        public_key_bytes: Raw 32-byte Ed25519 public key. If provided,
            signature verification is performed on every entry.

    Returns:
        VerificationResult with is_valid=True on success.
    """
    total = len(entries)

    if total == 0:
        return VerificationResult(
            is_valid=True,
            total_entries=0,
            first_broken_index=None,
            broken_reason=None,
        )

    prev_hash: str | None = None

    for i, entry in enumerate(entries):
        # 1. Sequence number must be contiguous
        actual_seq = entry.get("sequence_number")
        if i > 0:
            expected_seq = entries[i - 1].get("sequence_number", -1) + 1
            if actual_seq != expected_seq:
                return VerificationResult(
                    is_valid=False,
                    total_entries=total,
                    first_broken_index=i,
                    broken_reason=(
                        f"sequence_number gap: expected {expected_seq}, got {actual_seq}"
                    ),
                )

        # 2. prev_hash must chain to previous entry
        actual_prev = entry.get("prev_hash")
        if actual_prev != prev_hash:
            return VerificationResult(
                is_valid=False,
                total_entries=total,
                first_broken_index=i,
                broken_reason=(
                    f"prev_hash mismatch: expected {prev_hash!r}, got {actual_prev!r}"
                ),
            )

        # 3. entry_hash must match recomputed hash
        stored_hash = entry.get("entry_hash")
        computed_hash = compute_entry_hash(entry, prev_hash)
        if computed_hash != stored_hash:
            return VerificationResult(
                is_valid=False,
                total_entries=total,
                first_broken_index=i,
                broken_reason=(
                    "entry_hash mismatch: stored hash does not match recomputed hash "
                    "(entry content was modified after recording)"
                ),
            )

        # 4. Signature verification (optional)
        if public_key_bytes is not None:
            sig = entry.get("signature")
            if sig is None:
                return VerificationResult(
                    is_valid=False,
                    total_entries=total,
                    first_broken_index=i,
                    broken_reason=(
                        "missing signature: public key provided for verification "
                        "but this entry has no signature field"
                    ),
                )
            if not verify_signature(stored_hash, sig, public_key_bytes):
                return VerificationResult(
                    is_valid=False,
                    total_entries=total,
                    first_broken_index=i,
                    broken_reason="signature verification failed: wrong key or tampered hash",
                )

        prev_hash = stored_hash

    return VerificationResult(
        is_valid=True,
        total_entries=total,
        first_broken_index=None,
        broken_reason=None,
    )
