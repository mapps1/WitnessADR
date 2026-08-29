# WitnessADR Core

Core engine for the WitnessADR tamper-evident agent decision logging library.

Provides:
- JSON Schema validation for ADR entries
- Canonical JSON serialization (deterministic, reproducible)
- SHA-256 hash chain computation
- Ed25519 signing and verification
- Chain integrity verification
- Pluggable redaction (PII scrubbing before storage)
