#!/usr/bin/env python3
"""
WitnessADR — Raw API example

Demonstrates:
1. Creating a WitnessADRStore backed by a temp SQLite file
2. Writing 3 ADR entries simulating a simple agent's tool calls
3. Verifying the chain — should PASS
4. Corrupting one entry directly in the SQLite database
5. Verifying again — should FAIL with precise attribution

No real LLM API calls. Run with:
    pip install witnessadr-storage-sqlite
    python examples/raw_api_example.py
"""

import json
import sqlite3
import tempfile
from pathlib import Path

from witnessadr_core.signing import generate_keypair
from witnessadr_storage_sqlite import WitnessADRStore


def main() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    print(f"Database: {db_path}\n")

    # ── Generate a signing keypair ──────────────────────────────────────────
    private_key, public_key = generate_keypair()
    store = WitnessADRStore(db_path)
    session_id = "demo-session-001"

    # ── Entry 0: agent plans its approach ──────────────────────────────────
    e0 = store.append(
        session_id=session_id,
        agent_id="research-agent-v1",
        actor={"type": "model", "model": "claude-sonnet-4"},
        decision_type="reasoning_step",
        action={
            "description": "Plan: search for climate data, then summarize findings",
        },
        outcome="Plan formulated",
        raw_input_context={
            "system": "You are a research assistant.",
            "user": "Summarize recent climate trends.",
        },
        retention_class="general",
        private_key_bytes=private_key,
    )
    print(f"[Entry 0] decision_type=reasoning_step  seq={e0['sequence_number']}")

    # ── Entry 1: agent calls a search tool ─────────────────────────────────
    e1 = store.append(
        session_id=session_id,
        agent_id="research-agent-v1",
        actor={"type": "model", "model": "claude-sonnet-4"},
        decision_type="tool_call",
        action={
            "description": "Web search for 2024 temperature anomaly data",
            "tool_name": "web_search",
            "parameters": {"query": "2024 global temperature anomaly NOAA"},
        },
        outcome="Retrieved 8 search results from NOAA and NASA sources",
        input_context_hash="sha256:" + "b" * 64,
        policy_checks=[
            {"policy_id": "safe-search", "result": "pass"},
            {"policy_id": "pii-check", "result": "pass"},
        ],
        retention_class="general",
        private_key_bytes=private_key,
    )
    print(f"[Entry 1] decision_type=tool_call       seq={e1['sequence_number']}")

    # ── Entry 2: agent produces the final answer ────────────────────────────
    e2 = store.append(
        session_id=session_id,
        agent_id="research-agent-v1",
        actor={"type": "model", "model": "claude-sonnet-4"},
        decision_type="final_action",
        action={
            "description": "Compose summary of 2024 climate data for user",
        },
        outcome="Summary delivered to user",
        input_context_hash="sha256:" + "c" * 64,
        retention_class="general",
        private_key_bytes=private_key,
    )
    print(f"[Entry 2] decision_type=final_action    seq={e2['sequence_number']}")

    # ── Verify the chain — should PASS ─────────────────────────────────────
    print("\n--- Verification (before tampering) ---")
    result = store.verify(session_id, public_key_bytes=public_key)
    print(result)
    assert result.is_valid, "Chain should be valid at this point"

    # ── Corrupt Entry 1 directly in SQLite ─────────────────────────────────
    print("\n--- Tampering with entry 1 (sequence_number=1) ---")
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT entry_data FROM adr_entries WHERE session_id=? AND sequence_number=1",
        (session_id,),
    ).fetchone()
    corrupted = json.loads(row[0])
    corrupted["outcome"] = "ALTERED — this value was changed after recording"
    # Note: entry_hash is NOT updated, so the hash chain will detect the change
    conn.execute(
        "UPDATE adr_entries SET entry_data=? WHERE session_id=? AND sequence_number=1",
        (json.dumps(corrupted), session_id),
    )
    conn.commit()
    conn.close()
    print("Outcome field of entry 1 was changed without updating entry_hash.")

    # ── Verify again — should FAIL ─────────────────────────────────────────
    print("\n--- Verification (after tampering) ---")
    result = store.verify(session_id, public_key_bytes=public_key)
    print(result)
    assert not result.is_valid, "Chain should be broken after tampering"
    assert result.first_broken_index == 1, f"Expected index 1, got {result.first_broken_index}"

    print("\nDemo complete. Tamper detection works correctly.")
    Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
