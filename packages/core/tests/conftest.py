"""Shared test fixtures for witnessadr_core tests."""

import uuid
from datetime import datetime, timezone

import pytest
from witnessadr_core.hashing import compute_entry_hash
from witnessadr_core.signing import generate_keypair, sign_hash


def make_entry(
    seq: int,
    prev_hash: str | None,
    session_id: str = "test-session",
    agent_id: str = "test-agent",
    outcome: str = "completed",
    private_key_bytes: bytes | None = None,
) -> dict:
    """Build a valid, fully-hashed ADR entry for testing."""
    entry = {
        "adr_version": "1.0",
        "id": str(uuid.uuid4()),
        "sequence_number": seq,
        "prev_hash": prev_hash,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
        "agent_id": agent_id,
        "actor": {"type": "model", "model": "test-model"},
        "decision_type": "reasoning_step",
        "input_context_hash": "sha256:" + "a" * 64,
        "action": {"description": f"test action {seq}"},
        "outcome": outcome,
        "retention_class": "general",
    }
    entry["entry_hash"] = compute_entry_hash(entry, prev_hash)
    if private_key_bytes is not None:
        entry["signature"] = sign_hash(entry["entry_hash"], private_key_bytes)
    return entry


def build_chain(
    length: int,
    session_id: str = "test-session",
    private_key_bytes: bytes | None = None,
) -> list[dict]:
    """Build a valid hash chain of the given length."""
    entries = []
    prev_hash = None
    for i in range(length):
        entry = make_entry(
            seq=i,
            prev_hash=prev_hash,
            session_id=session_id,
            private_key_bytes=private_key_bytes,
        )
        entries.append(entry)
        prev_hash = entry["entry_hash"]
    return entries


@pytest.fixture
def keypair():
    return generate_keypair()


@pytest.fixture
def valid_chain():
    return build_chain(5)


@pytest.fixture
def signed_chain(keypair):
    private_key, _ = keypair
    return build_chain(5, private_key_bytes=private_key)
