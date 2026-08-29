"""SHA-256 hash chain computation."""

import hashlib

from .canonical import canonicalize


def compute_entry_hash(entry: dict, prev_hash: str | None) -> str:
    """Compute the hash chain link for an entry.

    Hash is SHA-256 over:
        canonicalize(entry) + (prev_hash or "").encode("utf-8")

    The prev_hash binding ties each entry to its predecessor so that
    neither reordering nor deletion can go undetected.

    Returns a "sha256:<hex>" formatted string.
    """
    canonical_bytes = canonicalize(entry)
    prev_bytes = (prev_hash or "").encode("utf-8")
    digest = hashlib.sha256(canonical_bytes + prev_bytes).hexdigest()
    return f"sha256:{digest}"
