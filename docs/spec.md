# Specification

The Agent Decision Record (ADR) schema specification is maintained in [`spec/spec.md`](../../spec/spec.md) and the JSON Schema in [`spec/adr-schema-v1.json`](../../spec/adr-schema-v1.json).

---

## Hash Chain Design

Each ADR entry is linked to the previous one via its `entry_hash`:

```
entry_hash = "sha256:" + SHA256(canonicalize(entry) + prev_hash_or_empty)
```

Where `canonicalize(entry)` is the deterministic, sorted-key JSON serialization of all fields except `entry_hash` and `signature`. This means:

- **Modifying any field** in an entry changes its `entry_hash`
- **Changing `entry_hash`** breaks the next entry's `prev_hash` link
- **Deleting an entry** causes a sequence number gap
- **Reordering entries** breaks both `prev_hash` links and sequence numbers

All four tamper vectors are caught by `verify_chain()`.

---

## Schema Quick Reference

See [spec/spec.md](../../spec/spec.md) for the full field reference and design rationale.

### Required fields

`adr_version`, `id`, `sequence_number`, `timestamp`, `session_id`, `agent_id`, `actor`, `decision_type`, `input_context_hash`, `action`, `outcome`, `retention_class`, `entry_hash`

### `decision_type` values

`tool_call` · `reasoning_step` · `policy_check` · `escalation` · `human_override` · `final_action`

### `retention_class` values

`eu_ai_act_high_risk` · `finra_advice` · `hipaa` · `general` · `custom`

---

## Versioning

The `adr_version` field (`"1.0"`) is present on every entry so old and new entries can coexist in one verifiable chain as the schema evolves. Non-breaking additions (new optional fields) are patch-level changes. Breaking changes (removing or renaming fields) require a new `adr_version` value and a new schema file.
