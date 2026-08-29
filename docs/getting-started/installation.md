# Installation

## Requirements

- Python 3.11 or later
- No external services required (everything runs locally)

## Packages

WitnessADR is split into focused packages so you only install what you need:

| Package | What it provides | Install |
|---|---|---|
| `witnessadr-core` | Hash chain, signing, verification, redaction | `pip install witnessadr-core` |
| `witnessadr-storage-sqlite` | SQLite store (includes core) | `pip install witnessadr-storage-sqlite` |
| `witnessadr-cli` | `witnessadr` CLI commands | `pip install witnessadr-cli` |
| `witnessadr-adapter-langchain` | LangChain callback handler | `pip install "witnessadr-adapter-langchain[langchain]"` |
| `witnessadr-adapter-openai` | OpenAI SDK wrapper | `pip install witnessadr-adapter-openai` |

## Typical install

For most users, install the storage package and CLI:

```bash
pip install witnessadr-storage-sqlite witnessadr-cli
```

With a framework adapter:

```bash
# LangChain
pip install witnessadr-storage-sqlite "witnessadr-adapter-langchain[langchain]"

# OpenAI
pip install witnessadr-storage-sqlite witnessadr-adapter-openai
```

## Development install

```bash
git clone https://github.com/witnessadr/witnessadr.git
cd witnessadr
python3 -m venv .venv && source .venv/bin/activate
pip install -e packages/core -e packages/storage_sqlite -e packages/cli \
            -e packages/adapter_openai \
            -e "packages/adapter_langchain[langchain]"
pip install pytest pytest-asyncio
pytest packages/ -v
```

## Verify your installation

```bash
python -c "from witnessadr_core import verify_chain; print('OK')"
witnessadr --help
```
