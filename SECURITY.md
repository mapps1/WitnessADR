# Security Policy

## Supported Versions

WitnessADR is early-stage software. Only the latest release receives security fixes.

| Version | Supported |
|---|---|
| 0.1.x (latest) | ✓ |
| older | ✗ |

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues by emailing **security@witnessadr.io** (or the maintainer directly via GitHub's private vulnerability reporting feature). Include:

1. A description of the vulnerability
2. Steps to reproduce or a proof-of-concept
3. Your assessment of severity and potential impact
4. Whether you have a suggested fix

We will acknowledge receipt within 48 hours and aim to issue a fix within 14 days for critical issues.

---

## Scope

Issues considered in-scope for security reports:

- **Tamper-detection bypasses**: A way to modify an ADR entry without `verify_chain` detecting it
- **Signature verification bypasses**: A crafted signature that `verify_signature` accepts with the wrong key
- **PII leakage via redactors**: `HashOnlyRedactor` or `RegexPIIRedactor` storing content that should only be hashed
- **Path traversal or injection in the CLI** (e.g., in `witnessadr export`)
- **Dependency vulnerabilities** in `cryptography`, `jsonschema`, or `aiosqlite`

Issues considered out-of-scope:

- Vulnerabilities that require physical access to the machine running WitnessADR
- Key management — WitnessADR stores private keys as local files; protecting them is the operator's responsibility
- Denial-of-service via malformed ADR entries (no availability guarantee in v1)

---

## Cryptographic Design Notes

WitnessADR's tamper evidence is built on:

- **SHA-256** for hash chain links — collision resistance at 128-bit security level
- **Ed25519** (RFC 8032) for optional entry signatures — 128-bit security, deterministic signing, small key/signature sizes

The hash chain design does **not** use a Merkle tree in v1 (planned for v2). It uses a simple linear chain, which means:
- You can detect **which** entry was tampered with but not **where in a batch** a fork occurred
- Chain verification is O(n) in the number of entries
- The security assumption is that the chain is verified periodically and not just at end-of-life
