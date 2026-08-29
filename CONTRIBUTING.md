# Contributing to WitnessADR

Thank you for considering a contribution. WitnessADR is an early-stage project and contributions — bug reports, documentation improvements, new adapters, and code reviews — are genuinely valuable.

---

## Before You Start

- Read [spec/spec.md](spec/spec.md) to understand the hash-chain design. The schema and verification correctness are the core value proposition; changes that affect them require careful review.
- Check [open issues](https://github.com/witnessadr/witnessadr/issues) to avoid duplicating work.
- For large changes, open an issue to discuss the approach before investing significant time.

---

## Development Setup

```bash
git clone https://github.com/witnessadr/witnessadr.git
cd witnessadr
python3 -m venv .venv
source .venv/bin/activate

# Install all packages in editable mode
pip install -e packages/core -e packages/storage_sqlite -e packages/cli \
            -e packages/adapter_openai \
            -e "packages/adapter_langchain[langchain]"

# Install dev tools
pip install pytest pytest-asyncio ruff
```

---

## Running Tests

```bash
# All tests
pytest packages/ -v

# Single package
pytest packages/core/tests/ -v

# With coverage
pip install pytest-cov
pytest packages/ --cov=packages --cov-report=term-missing
```

---

## Code Style

WitnessADR uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
ruff check packages/
ruff format packages/
```

Key style rules (enforced by Ruff, not by custom config):
- No extraneous docstrings — comment only what the code can't show on its own
- No `# type: ignore` without a comment explaining why
- Prefer `match` over long `if/elif` chains where Python 3.10+ syntax fits

---

## Adding a New Adapter

Framework adapters live in `packages/adapter_<name>/`. Each adapter:

1. Has its own `pyproject.toml` with the framework as an **optional** dependency (so the package installs without the framework and gives a clear error on first use).
2. Exposes its public API in `__init__.py` in under 3 imports.
3. Requires **under 5 lines of user integration code** — if you need more, the adapter is too complex.
4. Has tests that skip gracefully if the framework is not installed (`pytest.importorskip`).

Use `packages/adapter_openai/` as the reference implementation.

---

## Modifying the Schema

The `spec/adr-schema-v1.json` schema is the foundation of the project. Schema changes follow these rules:

- **Non-breaking additions** (new optional fields): bump the patch version, update `spec/spec.md`, copy the new schema to `packages/core/src/witnessadr_core/schemas/`.
- **Breaking changes** (removing or changing existing fields): require a new `adr_version` value (`"2.0"`), a new schema file (`adr-schema-v2.json`), and a migration guide.

Do not make breaking schema changes without a discussion issue first.

---

## Pull Request Checklist

- [ ] Tests pass: `pytest packages/ -v`
- [ ] Ruff clean: `ruff check packages/`
- [ ] If schema changed: `packages/core/src/witnessadr_core/schemas/adr-schema-v1.json` updated
- [ ] PR title is a one-line summary suitable for a CHANGELOG entry

---

## Reporting Security Issues

Do **not** open a public GitHub issue for security vulnerabilities. See [SECURITY.md](SECURITY.md) for the responsible disclosure process.

---

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 license.
