# WitnessADR — Agent Decision Record Specification v1.0

This document describes the Agent Decision Record (ADR) schema and the hash-chain tamper-evidence design used by WitnessADR.

---

## What is an Agent Decision Record?

An Agent Decision Record (ADR) is a single, immutable log entry that records one consequential decision made by an AI agent — a tool call, a reasoning step, a policy check, a human override, or a final action. Each entry conforms to a versioned JSON Schema (`adr-schema-v1.json`) and is linked to the previous entry via a cryptographic hash chain, making the full log independently verifiable.

---

## Hash Chain Design

### Why not just append-only storage?

Append-only storage (e.g., S3 Object Lock, immutable database flags) protects against _external_ tampering but not against a malicious or compromised _writer_ silently omitting or reordering entries before they are written. A hash chain — where each entry commits to the hash of the entry before it — means that even the system producing the log cannot alter, delete, or reorder a past entry without invalidating every entry after it.

This is independently checkable by a third party who only has read access. It is the same core idea behind Certificate Transparency logs and Sigstore's Rekor, applied here to agent decisions.

### How the chain works

Every entry carries two fields that form the chain:

- **`sequence_number`**: A monotonically increasing integer within a session, starting at 0. Gaps in the sequence are detected by the verifier as a chain break.
- **`prev_hash`**: The `entry_hash` of the immediately preceding entry, or `null` for the first entry in a session.

The `entry_hash` field is computed as:

```
entry_hash = "sha256:" + SHA256(canonicalize(entry) + (prev_hash || ""))
```

where:
- `canonicalize(entry)` is the deterministic, sorted-key JSON serialization of all fields **except** `entry_hash` and `signature` (since those are derived from this serialization)
- `prev_hash` is the raw string value of the previous entry's `entry_hash`, or an empty string for the first entry
- The concatenation is byte-level: canonical UTF-8 bytes followed by UTF-8 encoded prev_hash string

### Canonical serialization

To ensure `entry_hash` is reproducible across machines, languages, and library versions:

- All object keys are sorted recursively (alphabetical)
- No whitespace between tokens (compact form)
- UTF-8 encoding
- Python's `json.dumps(..., sort_keys=True, separators=(',', ':'))` satisfies this requirement

### Optional Ed25519 signatures

Each entry may optionally carry a `signature` field: an Ed25519 signature over `entry_hash`, encoded as `"ed25519:<base64>"`.

Signatures serve a stronger guarantee than hashing alone: they prove that a specific keypair (whose public key is distributed to auditors out-of-band) produced each entry. An auditor can verify the chain's integrity without trusting the storage system at all.

Key management:
- Private keys are stored locally by the operator (never sent anywhere)
- Public keys are distributed to auditors
- The `witnessadr init` CLI command generates a keypair

---

## Schema Field Reference

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `adr_version` | `"1.0"` | ✓ | Schema version. Allows old and new entries to coexist in one chain as the schema evolves. |
| `id` | UUID v4 string | ✓ | Unique identifier for this entry. |
| `sequence_number` | integer ≥ 0 | ✓ | Position in the session's chain. Must be contiguous with no gaps. |
| `prev_hash` | `"sha256:<hex>"` or `null` | — | Hash of the preceding entry. `null` for the first entry. |
| `timestamp` | ISO 8601 UTC string | ✓ | When this entry was recorded. |
| `session_id` | string | ✓ | Identifies the agent run or conversation. |
| `agent_id` | string | ✓ | Identifies the agent instance. |
| `actor` | object | ✓ | Who made this decision (model, human, or system). |
| `decision_type` | enum | ✓ | Categorizes the decision (see below). |
| `input_context_hash` | `"sha256:<hex>"` | ✓ | Hash of the full input context. Raw context is NOT stored by default. |
| `input_context_ref` | string | — | Optional pointer to redacted context in external storage. |
| `action` | object | ✓ | What the agent decided to do. |
| `policy_checks` | array | — | Policy gate evaluations. |
| `outcome` | string | ✓ | Human-readable result of this decision. |
| `human_approval` | object | — | Human-in-the-loop review record. |
| `retention_class` | enum | ✓ | Applicable regulatory retention requirement (tag only, not enforced). |
| `entry_hash` | `"sha256:<hex>"` | ✓ | This entry's position in the hash chain. |
| `signature` | `"ed25519:<base64>"` | — | Optional Ed25519 signature over `entry_hash`. |

### `decision_type` values

| Value | Meaning |
|---|---|
| `tool_call` | Agent invoked an external tool or API |
| `reasoning_step` | Intermediate LLM reasoning step (chain-of-thought, planning) |
| `policy_check` | A policy or safety gate was evaluated |
| `escalation` | Agent escalated to a human or higher-authority system |
| `human_override` | A human overrode, modified, or rejected an agent decision |
| `final_action` | The terminal decision of an agent run |

### `retention_class` values

| Value | Typical retention window | Source |
|---|---|---|
| `eu_ai_act_high_risk` | 10 years (Article 18) | EU AI Act |
| `finra_advice` | 6 years | FINRA Rule 4511 |
| `hipaa` | 6–10 years (varies by state) | HIPAA |
| `general` | Operator-defined | — |
| `custom` | Operator-defined | — |

The SDK tags entries with the correct class; it does not enforce deletion or retention. That is a storage-layer and cloud-product concern.

---

## Why `input_context_hash` instead of raw context storage

Storing raw prompts and conversation history creates significant risk for regulated deployments:

1. **PII leakage**: Prompts often contain names, emails, addresses, or account numbers.
2. **Legal hold complexity**: Stored content may be subject to discovery or deletion requests (GDPR Article 17, CCPA).
3. **Breach surface**: A compromised log store exposes not just metadata but substantive user data.

By default, WitnessADR stores only the SHA-256 hash of the input context — this proves the context existed at that exact moment (binding it to the chain) without retaining the content itself. Deployers who need the content for debugging can opt in via the `input_context_ref` field, passing a pre-redacted version through a `Redactor` instance.

---

## Verification

An external auditor can verify a chain using only:
1. The exported chain (JSON file produced by `witnessadr export`)
2. The public key (distributed by the operator, or embedded in the export bundle)
3. Python 3.11+ with `witnessadr-core` installed

The verification algorithm:

```
for i, entry in enumerate(entries):
    assert entry.sequence_number == entries[0].sequence_number + i       # no gaps
    assert entry.prev_hash == (entries[i-1].entry_hash if i > 0 else None)  # chain links
    assert recompute_hash(entry) == entry.entry_hash                      # content integrity
    if public_key:
        assert verify_ed25519(entry.entry_hash, entry.signature, public_key)  # signing key
```

The verifier reports the **first** broken entry — its index and reason — so the failure is precisely attributable, not just a binary pass/fail.
