# Quick Start

This guide walks through the complete WitnessADR workflow: writing entries, verifying the chain, and exporting a compliance bundle.

---

## 1. Create a store and generate a keypair

```python
from witnessadr_core.signing import generate_keypair
from witnessadr_storage_sqlite import WitnessADRStore

# Generate an Ed25519 keypair (or use witnessadr init from the CLI)
private_key, public_key = generate_keypair()

# Create a SQLite-backed store (file is created automatically)
store = WitnessADRStore("audit.db")
```

!!! tip "Key management"
    Keep `private_key` secret. Distribute `public_key` to anyone who needs to verify your logs.
    Use `witnessadr init audit.db` to do this from the CLI with file-based key storage.

---

## 2. Record agent decisions

```python
# An agent reasons about its plan
store.append(
    session_id="session-001",
    agent_id="research-agent-v1",
    actor={"type": "model", "model": "claude-sonnet-4"},
    decision_type="reasoning_step",
    action={"description": "Plan: search for data, then summarize"},
    outcome="Plan formulated",
    raw_input_context={
        "system": "You are a research assistant.",
        "user": "Summarize recent climate trends.",
    },
    retention_class="general",
    private_key_bytes=private_key,
)

# The agent calls a tool
store.append(
    session_id="session-001",
    agent_id="research-agent-v1",
    actor={"type": "model", "model": "claude-sonnet-4"},
    decision_type="tool_call",
    action={
        "description": "Web search for climate data",
        "tool_name": "web_search",
        "parameters": {"query": "2024 global temperature records"},
    },
    outcome="Retrieved 8 results from NOAA",
    input_context_hash="sha256:" + "a" * 64,  # hash of prompt at this step
    policy_checks=[
        {"policy_id": "safe-search", "result": "pass"},
    ],
    retention_class="general",
    private_key_bytes=private_key,
)
```

### `raw_input_context` vs `input_context_hash`

| Parameter | Use when |
|---|---|
| `raw_input_context={"messages": [...]}` | You have the raw context and want WitnessADR to hash it for you (via the configured Redactor) |
| `input_context_hash="sha256:..."` | You already have a hash, or you computed it yourself |

By default, `raw_input_context` is passed through `HashOnlyRedactor` — only the hash is stored, never the content.

---

## 3. Verify the chain

```python
result = store.verify("session-001", public_key_bytes=public_key)
print(result)
# PASS — 2 entries verified
```

The verifier checks:
- All sequence numbers are contiguous with no gaps
- Each entry's `prev_hash` matches the preceding entry's `entry_hash`
- Each entry's `entry_hash` matches the recomputed hash over its content
- Each entry's signature is valid for the provided public key

On failure, it reports the **first broken entry** — its index and reason — not just a binary pass/fail.

---

## 4. Export a compliance bundle

```bash
witnessadr export audit.db session-001 \
    --out ./compliance-bundle \
    --public-key witnessadr.key.pub
```

The bundle directory contains:
- `chain.json` — the full entry chain
- `public_key.b64` — the public key (base64-encoded)
- `VERIFICATION.md` — step-by-step instructions + a standalone Python verification script

An auditor with no prior knowledge of your system can verify the bundle with:

```bash
pip install witnessadr-core
cd compliance-bundle
python verify_bundle.py
# PASS — 2 entries verified
```

---

## 5. Human-in-the-loop approval

For EU AI Act and similar requirements, you can record human approvals explicitly:

```python
from witnessadr_storage_sqlite import record_human_approval

# Record that a human reviewed and approved a specific decision
record_human_approval(
    store,
    session_id="session-001",
    reviewed_decision_id=entry["id"],   # the id of the entry being approved
    approver_id="reviewer-jane-doe",
    decision="approved",
    private_key_bytes=private_key,
)
```

This creates a `human_override` decision type entry linked to the original decision's ID, satisfying the EU AI Act Article 14 human oversight record requirement.
