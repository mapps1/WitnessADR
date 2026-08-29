"""
Canonical JSON serialization for hash computation.

Rules:
- All object keys sorted recursively (alphabetical)
- No whitespace between tokens
- UTF-8 encoded
- Fields `entry_hash` and `signature` excluded (they are derived from this output)

This serialization must be identical across machines and Python versions.
Python 3.7+ guarantees dict insertion order, and json.dumps(sort_keys=True)
sorts recursively, making the output fully deterministic.
"""

import json


def canonicalize(entry: dict) -> bytes:
    """Return deterministic UTF-8 JSON bytes for hashing.

    Excludes `entry_hash` and `signature` since those fields are computed
    from this serialization and cannot be part of their own input.
    """
    clean = {k: v for k, v in entry.items() if k not in ("entry_hash", "signature")}
    return json.dumps(
        clean,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
