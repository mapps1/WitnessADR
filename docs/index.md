---
hide:
  - navigation
---

# WitnessADR

**WitnessADR is an open-source Python library for tamper-evident AI agent decision logging.** It records every consequential agent decision — tool calls, reasoning steps, policy checks, human overrides, final actions — as a cryptographically hash-chained, Ed25519-signed audit log entry that any third party can independently verify without trusting the system that produced it.

---

## What problem does WitnessADR solve?

AI agents in regulated environments need a verifiable, immutable record of every consequential decision they make. Standard logging is insufficient: log files can be altered after the fact, entries can be silently deleted, and there is no way for an external auditor to confirm the log is complete. WitnessADR solves this with a cryptographic hash chain — each entry commits to the hash of the previous one, so any deletion, reordering, or modification breaks the chain at the tampered entry and is detectable by anyone with only read access.

---

## Quick Start

=== "Basic usage"

    ```python
    from witnessadr_core.signing import generate_keypair
    from witnessadr_storage_sqlite import WitnessADRStore

    private_key, public_key = generate_keypair()
    store = WitnessADRStore("audit.db")

    store.append(
        session_id="session-001",
        agent_id="my-agent-v1",
        actor={"type": "model", "model": "claude-sonnet-4"},
        decision_type="tool_call",
        action={"description": "Search for policy docs", "tool_name": "search"},
        outcome="Found 3 relevant documents",
        input_context_hash="sha256:" + "a" * 64,
        retention_class="eu_ai_act_high_risk",
        private_key_bytes=private_key,
    )

    result = store.verify("session-001", public_key_bytes=public_key)
    print(result)  # PASS — 1 entries verified
    ```

=== "LangChain"

    ```python
    from witnessadr_storage_sqlite import WitnessADRStore
    from witnessadr_adapter_langchain import WitnessADRCallbackHandler

    store = WitnessADRStore("audit.db")
    handler = WitnessADRCallbackHandler(store, session_id="session-001")

    # One line of integration with any LangChain chain or agent:
    chain.invoke({"input": "..."}, config={"callbacks": [handler]})
    ```

=== "OpenAI"

    ```python
    import openai
    from witnessadr_storage_sqlite import WitnessADRStore
    from witnessadr_adapter_openai import WitnessADROpenAI

    store = WitnessADRStore("audit.db")
    client = WitnessADROpenAI(openai.OpenAI(), store, session_id="session-001")

    response = client.chat("gpt-4o", messages=[
        {"role": "user", "content": "Summarize the policy document"}
    ])
    ```

---

## Key Features

<div class="grid cards" markdown>

- :material-link-lock: **Hash chain tamper evidence**

    Each entry commits to the hash of the previous one. Deletion, reordering, or modification of any entry is immediately detectable.

- :material-key: **Ed25519 signatures**

    Optional per-entry signing proves a specific key produced each entry. Auditors verify with only the public key.

- :material-shield-off: **Privacy by default**

    Input context is never stored — only its SHA-256 hash. Opt in to PII-scrubbed storage via `RegexPIIRedactor`.

- :material-puzzle: **Framework adapters**

    Drop-in support for LangChain, OpenAI, and more. Under 5 lines of integration code.

- :material-console: **CLI tools**

    `witnessadr verify` and `witnessadr export` produce self-contained compliance bundles auditors can check independently.

- :material-home: **Self-hosted**

    No telemetry. No external dependencies. No vendor trust required.

</div>

---

## Install

```bash
pip install witnessadr-storage-sqlite    # core + SQLite storage
pip install witnessadr-cli               # adds the witnessadr CLI
pip install witnessadr-adapter-langchain # LangChain adapter
pip install witnessadr-adapter-openai    # OpenAI adapter
```

---

## How it differs from Langfuse and LangSmith

Langfuse and LangSmith are developer observability tools — great for debugging, tracing, and understanding what your agents do. WitnessADR is a compliance primitive: its purpose is to produce a cryptographically verifiable audit log that an external auditor can independently check. The two are complementary; WitnessADR includes an OpenTelemetry bridge (planned) for ingesting spans already captured by those tools.

---

## Status

[![CI](https://github.com/witnessadr/witnessadr/actions/workflows/ci.yml/badge.svg)](https://github.com/witnessadr/witnessadr/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/witnessadr/witnessadr/blob/main/LICENSE)

Early-stage open-source project. The core engine and SQLite storage are implemented and tested. Framework adapters for LangChain and OpenAI are available. The OTel bridge and Postgres/S3 storage adapters are planned. See the [FAQ](faq.md) for current production-readiness guidance.
