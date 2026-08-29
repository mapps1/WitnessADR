"""Tests for the SQLite storage adapter."""

import json
import sqlite3

import pytest
from witnessadr_core.signing import generate_keypair
from witnessadr_storage_sqlite import (
    AsyncWitnessADRStore,
    WitnessADRStore,
    record_human_approval,
)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def store(db_path):
    return WitnessADRStore(db_path)


def _append_fake(store, session_id="s1", n=1, **kwargs):
    entries = []
    for i in range(n):
        e = store.append(
            session_id=session_id,
            agent_id="agent-1",
            actor={"type": "model", "model": "test-model"},
            decision_type="tool_call",
            action={"description": f"action {i}", "tool_name": "search"},
            outcome=f"result {i}",
            input_context_hash="sha256:" + "a" * 64,
            **kwargs,
        )
        entries.append(e)
    return entries


# ── Basic write/read ──────────────────────────────────────────────────────────

def test_append_returns_entry_with_entry_hash(store):
    entry = _append_fake(store)[0]
    assert entry["entry_hash"].startswith("sha256:")


def test_append_sets_sequence_numbers(store):
    entries = _append_fake(store, n=3)
    seqs = [e["sequence_number"] for e in entries]
    assert seqs == [0, 1, 2]


def test_append_chains_prev_hash(store):
    entries = _append_fake(store, n=3)
    assert entries[0]["prev_hash"] is None
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]
    assert entries[2]["prev_hash"] == entries[1]["entry_hash"]


def test_get_chain_returns_entries_in_order(store):
    _append_fake(store, n=5)
    chain = store.get_chain("s1")
    assert len(chain) == 5
    for i, e in enumerate(chain):
        assert e["sequence_number"] == i


def test_multiple_sessions_independent(store):
    _append_fake(store, session_id="session-a", n=3)
    _append_fake(store, session_id="session-b", n=2)

    chain_a = store.get_chain("session-a")
    chain_b = store.get_chain("session-b")
    assert len(chain_a) == 3
    assert len(chain_b) == 2
    # Each session's chain starts at 0
    assert chain_a[0]["sequence_number"] == 0
    assert chain_b[0]["sequence_number"] == 0


# ── Integrity verification ────────────────────────────────────────────────────

def test_verify_passes_for_valid_chain(store):
    _append_fake(store, n=4)
    result = store.verify("s1")
    assert result.is_valid is True


def test_verify_with_signing(store):
    private_key, public_key = generate_keypair()
    _append_fake(store, n=3, private_key_bytes=private_key)
    result = store.verify("s1", public_key_bytes=public_key)
    assert result.is_valid is True


def test_verify_detects_tampered_entry(db_path, store):
    _append_fake(store, n=3)
    chain = store.get_chain("s1")
    _ = chain[1]  # reference to confirm entry exists before tampering

    # Directly tamper with the stored JSON (without updating entry_hash)
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT entry_data FROM adr_entries WHERE session_id='s1' AND sequence_number=1"
    ).fetchone()
    tampered = json.loads(row[0])
    tampered["outcome"] = "TAMPERED"
    conn.execute(
        "UPDATE adr_entries SET entry_data=? WHERE session_id='s1' AND sequence_number=1",
        (json.dumps(tampered),),
    )
    conn.commit()
    conn.close()

    result = store.verify("s1")
    assert result.is_valid is False
    assert result.first_broken_index == 1


def test_list_sessions(store):
    _append_fake(store, session_id="alpha")
    _append_fake(store, session_id="beta")
    sessions = store.list_sessions()
    assert "alpha" in sessions
    assert "beta" in sessions


# ── Redaction ─────────────────────────────────────────────────────────────────

def test_raw_input_context_with_hash_only_redactor(store):
    raw = {"user": "alice@example.com", "query": "sensitive data"}
    entry = store.append(
        session_id="s1",
        agent_id="a1",
        actor={"type": "model", "model": "m"},
        decision_type="tool_call",
        action={"description": "search"},
        outcome="ok",
        raw_input_context=raw,
    )
    # Hash is present and has the right format
    assert entry["input_context_hash"].startswith("sha256:")
    # Raw content must not appear in the stored entry
    entry_str = json.dumps(entry)
    assert "alice@example.com" not in entry_str
    # input_context_ref is not populated by HashOnlyRedactor
    assert "input_context_ref" not in entry


# ── Human approval ────────────────────────────────────────────────────────────

def test_record_human_approval(store):
    agent_entry = _append_fake(store)[0]
    approval = record_human_approval(
        store,
        session_id="s1",
        reviewed_decision_id=agent_entry["id"],
        approver_id="reviewer-007",
        decision="approved",
    )
    assert approval["decision_type"] == "human_override"
    assert approval["actor"]["type"] == "human"
    assert approval["human_approval"]["decision"] == "approved"
    assert agent_entry["id"] in json.dumps(approval["action"])


def test_full_chain_with_human_approval_verifies(store):
    _append_fake(store, n=2)
    chain = store.get_chain("s1")
    record_human_approval(
        store,
        session_id="s1",
        reviewed_decision_id=chain[0]["id"],
        approver_id="reviewer-1",
        decision="approved",
    )
    result = store.verify("s1")
    assert result.is_valid is True
    assert result.total_entries == 3


# ── Async store ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_async_store_append_and_verify(tmp_path):
    db = str(tmp_path / "async.db")
    async with AsyncWitnessADRStore(db) as store:
        for i in range(3):
            await store.append(
                session_id="async-session",
                agent_id="agent-1",
                actor={"type": "model", "model": "test"},
                decision_type="reasoning_step",
                action={"description": f"step {i}"},
                outcome="done",
                input_context_hash="sha256:" + "b" * 64,
            )
        result = await store.verify("async-session")
    assert result.is_valid is True
    assert result.total_entries == 3


@pytest.mark.asyncio
async def test_async_store_signed_chain(tmp_path):
    private_key, public_key = generate_keypair()
    db = str(tmp_path / "async-signed.db")
    async with AsyncWitnessADRStore(db) as store:
        await store.append(
            session_id="s",
            agent_id="a",
            actor={"type": "model", "model": "m"},
            decision_type="tool_call",
            action={"description": "tool"},
            outcome="ok",
            input_context_hash="sha256:" + "c" * 64,
            private_key_bytes=private_key,
        )
        result = await store.verify("s", public_key_bytes=public_key)
    assert result.is_valid is True
