"""Tests for SHA-256 hash chain computation."""

import copy

from witnessadr_core.hashing import compute_entry_hash

_DUMMY_PREV = "sha256:" + "f" * 64


def _base_entry() -> dict:
    return {
        "adr_version": "1.0",
        "session_id": "s1",
        "agent_id": "a1",
        "outcome": "done",
        "sequence_number": 0,
    }


def test_hash_format():
    entry = _base_entry()
    h = compute_entry_hash(entry, None)
    assert h.startswith("sha256:")
    hex_part = h[len("sha256:"):]
    assert len(hex_part) == 64
    assert all(c in "0123456789abcdef" for c in hex_part)


def test_first_entry_hash_differs_from_subsequent():
    entry = _base_entry()
    h1 = compute_entry_hash(entry, None)
    h2 = compute_entry_hash(entry, _DUMMY_PREV)
    assert h1 != h2


def test_same_entry_same_prev_hash_is_deterministic():
    entry = _base_entry()
    h1 = compute_entry_hash(entry, _DUMMY_PREV)
    h2 = compute_entry_hash(copy.deepcopy(entry), _DUMMY_PREV)
    assert h1 == h2


def test_different_content_different_hash():
    entry_a = _base_entry()
    entry_b = {**_base_entry(), "outcome": "tampered"}
    h_a = compute_entry_hash(entry_a, None)
    h_b = compute_entry_hash(entry_b, None)
    assert h_a != h_b


def test_different_prev_hash_different_hash():
    entry = _base_entry()
    prev_a = "sha256:" + "a" * 64
    prev_b = "sha256:" + "b" * 64
    assert compute_entry_hash(entry, prev_a) != compute_entry_hash(entry, prev_b)


def test_entry_hash_field_excluded_from_computation():
    """entry_hash field must not affect the computed hash (it's derived from the computation)."""
    entry_a = _base_entry()
    entry_b = {**_base_entry(), "entry_hash": "sha256:" + "e" * 64}
    # Canonical serialization excludes entry_hash, so hashes must match
    assert compute_entry_hash(entry_a, None) == compute_entry_hash(entry_b, None)


def test_signature_field_excluded_from_computation():
    entry_a = _base_entry()
    entry_b = {**_base_entry(), "signature": "ed25519:abc123"}
    assert compute_entry_hash(entry_a, None) == compute_entry_hash(entry_b, None)
