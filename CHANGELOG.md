# Changelog

All notable changes to WitnessADR are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Breaking changes to `adr-schema-v1.json` require a new `adr_version` value and are treated as major version bumps.

---

## [Unreleased]

### Added
- `witnessadr-adapter-langchain`: LangChain callback handler (`WitnessADRCallbackHandler`) that records LLM calls and tool invocations as ADR entries
- `witnessadr-adapter-openai`: OpenAI SDK wrapper (`WitnessADROpenAI`) and `record_openai_tool_call` helper
- `AsyncWitnessADRStore` for `aioasqlite`-based async writes
- `record_human_approval()` helper for EU AI Act Article 14 human-in-the-loop records
- `RegexPIIRedactor` for opt-in readable-but-scrubbed context storage
- `witnessadr export` CLI command producing a self-contained compliance bundle with `VERIFICATION.md`
- `witnessadr init` CLI command for keypair and store initialization
- `witnessadr verify` CLI command with CI-safe exit codes

---

## [0.1.0] — 2026-08-28

### Added
- `witnessadr-core`: canonical JSON serialization, SHA-256 hash chain, Ed25519 signing and verification, JSON Schema validation (`adr-schema-v1.json`)
- `witnessadr-storage-sqlite`: SQLite-backed `WitnessADRStore` with sync API
- `witnessadr-cli`: `init`, `verify`, and `export` commands (Typer + Rich)
- `HashOnlyRedactor`: safe default that stores only the SHA-256 hash of input context
- `spec/adr-schema-v1.json`: JSON Schema (draft 2020-12) for Agent Decision Record v1
- `spec/spec.md`: human-readable specification with hash-chain design rationale
- Apache 2.0 license

[Unreleased]: https://github.com/witnessadr/witnessadr/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/witnessadr/witnessadr/releases/tag/v0.1.0
