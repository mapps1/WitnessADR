# WitnessADR FAQ

---

## What is an Agent Decision Record?

An Agent Decision Record (ADR) is a single tamper-evident log entry recording one consequential decision made by an AI agent — a tool call, reasoning step, policy check, human override, or final action. Each entry is cryptographically linked to the previous one (hash chain), so the full log can be verified by a third party who has never seen the system that produced it. WitnessADR is the open-source library for capturing and verifying these records.

---

## How is this different from LLM observability tools like Langfuse or LangSmith?

Langfuse and LangSmith are developer-facing observability and debugging tools: they help you understand what your agent did, replay traces, and debug failures. WitnessADR is a compliance-evidence primitive: its purpose is to produce a cryptographically verifiable audit log that an external auditor can independently check. The two can coexist — WitnessADR includes an OpenTelemetry bridge so you can ingest spans already captured by those tools rather than ripping them out.

---

## Does WitnessADR store my raw prompts or conversation data?

No, not by default. WitnessADR stores the SHA-256 hash of the input context, not the content itself. This means it can prove that specific content was present at decision time (the hash is a cryptographic commitment) without retaining PII, trade secrets, or other sensitive data. Deployers who need the content for debugging can opt in by using a `Redactor` — a pluggable interface that either strips PII patterns before storage (`RegexPIIRedactor`) or stores nothing beyond the hash (`HashOnlyRedactor`, the default).

---

## What compliance regimes does WitnessADR help with?

WitnessADR is designed to support the logging and traceability requirements in:
- **EU AI Act** (Articles 12–19): documentation, logging, and human oversight for high-risk AI systems
- **FINRA Rule 4511 / SEC 17a-4**: records retention for advice given by AI-assisted systems
- **HIPAA** (45 CFR §164.312): audit controls for AI systems handling protected health information
- **SOC 2 Type II** (Availability and Integrity criteria): evidence of system integrity for security reviews

WitnessADR tags each entry with a `retention_class` that indicates the applicable regime. It does **not** enforce deletion or retention — that is a storage-layer concern. Think of it as providing the evidence; your data platform enforces the policy.

---

## Can I use WitnessADR alongside Langfuse or LangSmith?

Yes. The recommended pattern is to run both: your existing observability tooling for debugging and developer experience, and WitnessADR for compliance evidence. WitnessADR's OTel bridge (in `packages/otel_bridge/`, planned for Phase 5) can ingest spans already captured by OTel-instrumented code and convert them into ADR entries, so you avoid double-instrumentation. You can also use both independently and they will not conflict.

---

## Is this production-ready?

Not yet. WitnessADR is early-stage open-source software — the core engine (hashing, signing, verification, SQLite storage) is implemented and tested, but the framework adapters (LangChain, CrewAI, etc.) and the OTel bridge are still in development per the phased build plan. The schema and hash-chain format are stable but have not yet been reviewed by external compliance or security specialists. Use it for evaluation and development; production use in regulated environments should wait for those reviews. Feedback on the schema and design is very welcome via GitHub issues.

---

## Why Apache 2.0 and not AGPL or a Business Source License?

Apache 2.0 allows teams to adopt WitnessADR into proprietary systems without requiring them to open-source their own code or negotiate a commercial license. For a compliance tool that needs to be embedded deep in production infrastructure, adoption friction is a real barrier. AGPL is a common blocker for enterprise procurement. Apache 2.0 is used by comparable open-core projects in this space (LangChain, Opik, Laminar) and lets the project build adoption first.

---

## How does the hash chain compare to Certificate Transparency or Sigstore?

The design uses the same core idea as Certificate Transparency (CT) logs and Sigstore's Rekor: an append-only, hash-linked log where any entry can be independently verified by a third party with only read access. The difference is scope — CT and Rekor work on TLS certificates and software artifacts respectively; WitnessADR applies the same tamper-evidence primitive to AI agent decisions. For v1, WitnessADR uses a simple linear hash chain. A Merkle-tree-per-time-window with externally anchored roots (as used in CT) is a planned v2 enhancement for stronger guarantees in high-volume deployments.
