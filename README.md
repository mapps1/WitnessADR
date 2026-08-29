# WitnessADR

**Tamper-evident audit trail for AI agent decisions — open-source, self-hosted, hash-chained, Ed25519-signed.**

[![CI](https://github.com/witnessadr/witnessadr/actions/workflows/ci.yml/badge.svg)](https://github.com/witnessadr/witnessadr/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![PyPI: witnessadr-core](https://img.shields.io/pypi/v/witnessadr-core?label=witnessadr-core)](https://pypi.org/project/witnessadr-core/)
[![Status: Early Stage](https://img.shields.io/badge/status-early--stage-yellow.svg)](docs/faq.md#is-this-production-ready)

---

## What problem does this solve?

AI agents make consequential decisions — tool calls, policy checks, final actions — that may need to be audited by regulators, customers, or your own security team. WitnessADR is a small Python library that records each decision as a tamper-evident Agent Decision Record (ADR): a hash-chained, optionally Ed25519-signed log entry that an external auditor can independently verify without trusting your infrastructure. Every entry links to the previous one cryptographically, so deleting, reordering, or altering any entry invalidates the entire chain from that point forward — and the verifier tells you exactly which entry broke and why.

---

## Quick Start

```python
from witnessadr_core.signing import generate_keypair
from witnessadr_storage_sqlite import WitnessADRStore

private_key, public_key = generate_keypair()
store = WitnessADRStore("audit.db")

# Record an agent's tool call
store.append(
    session_id="session-001",
    agent_id="my-agent-v1",
    actor={"type": "model", "model": "claude-sonnet-4"},
    decision_type="tool_call",
    action={"description": "Search for climate data", "tool_name": "web_search"},
    outcome="Retrieved 8 results",
    input_context_hash="sha256:" + "a" * 64,  # or pass raw_input_context=
    retention_class="general",
    private_key_bytes=private_key,
)

# Verify the entire chain
result = store.verify("session-001", public_key_bytes=public_key)
print(result)  # PASS — 1 entries verified
```

**LangChain** (one extra line):
```python
from witnessadr_adapter_langchain import WitnessADRCallbackHandler
handler = WitnessADRCallbackHandler(WitnessADRStore("audit.db"), session_id="s1")
chain.invoke({"input": "..."}, config={"callbacks": [handler]})
```

**OpenAI** (wrap your existing client):
```python
from witnessadr_adapter_openai import WitnessADROpenAI
client = WitnessADROpenAI(openai.OpenAI(), WitnessADRStore("audit.db"), session_id="s1")
response = client.chat("gpt-4o", messages=[...])
```

Install:
```bash
pip install witnessadr-storage-sqlite witnessadr-cli
pip install "witnessadr-adapter-langchain[langchain]"   # LangChain
pip install witnessadr-adapter-openai                    # OpenAI
```

---

## Architecture

```
┌─────────────────────────────┐
│   Agent framework code       │
│ (LangChain / LangGraph /     │
│  CrewAI / raw API calls)     │
└───────────────┬──────────────┘
                │ instrumentation call
┌───────────────▼──────────────┐
│      Framework Adapters       │
│ (adapters/langchain.py, etc.) │
└───────────────┬──────────────┘
                │ raw event
┌───────────────▼──────────────┐
│        Redaction Hook         │  ← pluggable, user-supplied
└───────────────┬──────────────┘
                │ cleaned event
┌───────────────▼──────────────┐
│          Core Engine          │
│  - schema validation          │
│  - hash chain computation     │
│  - optional Ed25519 signing   │
└───────────────┬──────────────┘
                │ ADR entry
┌───────────────▼──────────────┐
│       Storage Adapter         │
│  (SQLite / Postgres / S3)     │
└────────────────────────────────┘

Separately, at any time:
┌────────────────────────────────┐
│     Verification CLI/Library    │
│  reads storage → walks hash     │
│  chain → checks signatures →    │
│  reports pass/fail + first break│
└────────────────────────────────┘
```

---

## CLI

```bash
# Create a new store + Ed25519 keypair
witnessadr init audit.db

# Verify a session's hash chain (exit 0 = valid, exit 1 = broken — CI-safe)
witnessadr verify audit.db session-001 --public-key witnessadr.key.pub

# Export a self-contained compliance bundle for an auditor
witnessadr export audit.db session-001 --out ./compliance-bundle --public-key witnessadr.key.pub
```

---

## How this differs from Langfuse, LangSmith, and Kosmoy

| | WitnessADR | Langfuse / LangSmith | Kosmoy |
|---|---|---|---|
| **Primary purpose** | Compliance evidence — tamper-evident, independently verifiable audit log | Developer observability — traces, debugging, prompt analysis | Managed compliance platform for AI governance |
| **Deployment** | Self-hosted, open-source | Langfuse: self-hosted or cloud. LangSmith: cloud-first | Managed SaaS |
| **Tamper evidence** | Hash chain + Ed25519 signatures, independently verifiable | Not a design goal | Varies |
| **Scope** | Narrow: capture + verify only | Broad: full observability stack | Broad: governance, risk, compliance platform |
| **Relationship** | Can ingest from Langfuse/LangSmith via OTel bridge | Complementary | More direct overlap, different deployment model |

Langfuse and LangSmith are developer tools that help you understand and debug your agents. WitnessADR is a compliance primitive that proves to a third party what your agents did. The two are complementary; you do not need to choose one over the other.

---

## Repository Layout

```
witnessadr/
├── spec/                        # Canonical ADR schema + specification
│   ├── adr-schema-v1.json
│   └── spec.md
├── packages/
│   ├── core/                    # witnessadr-core: hashing, signing, verification
│   ├── storage_sqlite/          # witnessadr-storage-sqlite (sync + async)
│   ├── cli/                     # witnessadr CLI (init / verify / export)
│   ├── adapter_langchain/       # witnessadr-adapter-langchain
│   ├── adapter_openai/          # witnessadr-adapter-openai
│   ├── storage_postgres/        # (planned)
│   ├── adapter_anthropic/       # (planned)
│   ├── adapter_crewai/          # (planned)
│   └── otel_bridge/             # (planned)
├── examples/
├── docs/                        # MkDocs documentation site
├── llms.txt                     # AI crawler index
└── llms-full.txt                # Comprehensive AI-readable documentation
```

---

## Design Principles

- **No phone-home**: entirely self-hosted, zero telemetry by default
- **Dependency-light**: core package requires only `jsonschema` and `cryptography`
- **Hash-only by default**: raw prompts are never stored unless you opt in via a Redactor
- **Independent verifiability**: auditors need only `witnessadr-core` and read access — no vendor trust required
- **Open-core**: the OSS library does capture + verify; managed retention, dashboards, and compliance reports are future paid-tier features

---

## Status

Early-stage open-source project. The core hash chain engine, SQLite storage, and CLI are implemented. Framework adapters (LangChain, LangGraph, CrewAI) and the OTel bridge are in development. The schema has not yet undergone formal security or compliance review. See [docs/faq.md](docs/faq.md) for more.

---

## License

Apache 2.0. See [LICENSE](LICENSE).
