"""Tests for canonical JSON serialization."""

import copy

from witnessadr_core.canonical import canonicalize


def test_canonicalize_is_deterministic_regardless_of_key_insertion_order():
    entry_a = {
        "session_id": "s1",
        "agent_id": "a1",
        "action": {"description": "test", "tool_name": "search"},
        "adr_version": "1.0",
    }
    # Same logical content, different insertion order
    entry_b = {
        "adr_version": "1.0",
        "action": {"tool_name": "search", "description": "test"},
        "agent_id": "a1",
        "session_id": "s1",
    }
    assert canonicalize(entry_a) == canonicalize(entry_b)


def test_canonicalize_excludes_entry_hash():
    entry = {"adr_version": "1.0", "outcome": "done", "entry_hash": "sha256:" + "a" * 64}
    result = canonicalize(entry)
    assert b"entry_hash" not in result


def test_canonicalize_excludes_signature():
    entry = {"adr_version": "1.0", "outcome": "done", "signature": "ed25519:abc123"}
    result = canonicalize(entry)
    assert b"signature" not in result


def test_canonicalize_includes_prev_hash():
    prev = "sha256:" + "b" * 64
    entry_with = {"adr_version": "1.0", "prev_hash": prev}
    entry_without = {"adr_version": "1.0"}
    assert canonicalize(entry_with) != canonicalize(entry_without)


def test_canonicalize_returns_utf8_bytes():
    entry = {"outcome": "résultat"}
    result = canonicalize(entry)
    assert isinstance(result, bytes)
    decoded = result.decode("utf-8")
    assert "résultat" in decoded


def test_canonicalize_nested_keys_sorted():
    entry = {"action": {"z_key": 1, "a_key": 2}}
    result = canonicalize(entry).decode("utf-8")
    assert result.index("a_key") < result.index("z_key")


def test_canonicalize_compact_no_whitespace():
    entry = {"a": 1, "b": 2}
    result = canonicalize(entry).decode("utf-8")
    assert " " not in result
    assert "\n" not in result


def test_canonicalize_null_value():
    entry_null = {"prev_hash": None}
    entry_str = {"prev_hash": "sha256:" + "0" * 64}
    assert canonicalize(entry_null) != canonicalize(entry_str)


def test_canonicalize_same_content_same_bytes_multiple_calls():
    entry = {"session_id": "abc", "sequence_number": 42}
    assert canonicalize(entry) == canonicalize(copy.deepcopy(entry))
