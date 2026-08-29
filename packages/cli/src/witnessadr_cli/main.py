"""WitnessADR CLI — init, verify, export.

Commands:
    witnessadr init    — create a SQLite store and Ed25519 keypair
    witnessadr verify  — verify a session's hash chain integrity
    witnessadr export  — produce a self-contained compliance bundle
"""

import base64
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from witnessadr_core.signing import generate_keypair
from witnessadr_storage_sqlite import WitnessADRStore

app = typer.Typer(
    name="witnessadr",
    help="WitnessADR — tamper-evident audit trail for AI agent decisions.",
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


# ── init ──────────────────────────────────────────────────────────────────────

@app.command()
def init(
    db_path: Path = typer.Argument(..., help="Path for the new SQLite database file."),
    key_path: Path = typer.Option(
        Path("witnessadr.key"),
        "--key-path",
        "-k",
        help="Path to write the Ed25519 private key (base64-encoded, keep secret).",
    ),
    pub_path: Optional[Path] = typer.Option(
        None,
        "--pub-path",
        help="Path to write the public key (distribute to auditors). "
        "Defaults to <key-path>.pub",
    ),
) -> None:
    """Initialize a new WitnessADR store and generate an Ed25519 signing keypair."""

    if db_path.exists():
        err_console.print(f"[yellow]Database already exists:[/] {db_path}")
        err_console.print("Skipping database creation. Generating a new keypair only.")
    else:
        WitnessADRStore(str(db_path))
        console.print(f"[green]✓[/] Created database: {db_path}")

    private_key_bytes, public_key_bytes = generate_keypair()

    if pub_path is None:
        pub_path = key_path.with_suffix(key_path.suffix + ".pub")

    key_path.write_text(base64.b64encode(private_key_bytes).decode("ascii") + "\n")
    pub_path.write_text(base64.b64encode(public_key_bytes).decode("ascii") + "\n")

    console.print(f"[green]✓[/] Private key written to: {key_path}")
    console.print(f"[green]✓[/] Public key written to:  {pub_path}")
    console.print()
    console.print(
        Panel(
            "[bold red]Keep your private key secret.[/]\n\n"
            f"  Private key: [bold]{key_path}[/]\n"
            f"  Public key:  [bold]{pub_path}[/]\n\n"
            "Distribute the public key to auditors. "
            "Anyone with the public key can independently verify the chain.\n\n"
            "[bold]Public key (share with auditors):[/]\n"
            + base64.b64encode(public_key_bytes).decode("ascii"),
            title="WitnessADR Keypair",
            border_style="yellow",
        )
    )


# ── verify ────────────────────────────────────────────────────────────────────

@app.command()
def verify(
    db_path: Path = typer.Argument(..., help="Path to the SQLite database."),
    session_id: str = typer.Argument(..., help="Session ID to verify."),
    public_key: Optional[Path] = typer.Option(
        None,
        "--public-key",
        "-k",
        help="Path to the Ed25519 public key file (base64-encoded). "
        "If provided, signatures are verified.",
    ),
) -> None:
    """Verify the integrity of an ADR chain.

    Exit code 0 = chain is valid.
    Exit code 1 = chain is broken (for CI/scripting use).
    """
    if not db_path.exists():
        err_console.print(f"[red]Database not found:[/] {db_path}")
        raise typer.Exit(1)

    pub_key_bytes: Optional[bytes] = None
    if public_key is not None:
        if not public_key.exists():
            err_console.print(f"[red]Public key file not found:[/] {public_key}")
            raise typer.Exit(1)
        pub_key_bytes = base64.b64decode(public_key.read_text().strip())

    store = WitnessADRStore(str(db_path))
    result = store.verify(session_id, public_key_bytes=pub_key_bytes)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Session ID", session_id)
    table.add_row("Database", str(db_path))
    table.add_row("Entries verified", str(result.total_entries))
    if pub_key_bytes:
        table.add_row("Signature check", "enabled")

    if result.is_valid:
        console.print(Panel(table, title="[green]✓ CHAIN VALID[/]", border_style="green"))
        raise typer.Exit(0)
    else:
        table.add_row("First broken index", str(result.first_broken_index))
        table.add_row("Reason", result.broken_reason or "unknown")
        console.print(Panel(table, title="[red]✗ CHAIN BROKEN[/]", border_style="red"))
        raise typer.Exit(1)


# ── export ────────────────────────────────────────────────────────────────────

_VERIFICATION_MD_TEMPLATE = """\
# WitnessADR Compliance Export — Verification Guide

This bundle was exported from a WitnessADR-instrumented system. It contains
a tamper-evident hash-chained log of AI agent decisions for the session below.

## Bundle Contents

| File | Description |
|---|---|
| `chain.json` | Full ADR entry chain in sequence order |
| `public_key.b64` | Ed25519 public key used to sign entries (base64-encoded) |
| `VERIFICATION.md` | This file |

## Session Details

- **Session ID:** `{session_id}`
- **Entries:** {entry_count}
- **First entry:** `{first_timestamp}`
- **Last entry:** `{last_timestamp}`
- **Signed:** {signed}

## Independent Verification Instructions

You can verify this bundle using only Python 3.11+ and the `witnessadr-core`
package. No account, API key, or vendor trust is required.

### 1. Install witnessadr-core

```bash
pip install witnessadr-core
```

### 2. Run the standalone verification script

Save the following as `verify_bundle.py` in the same directory as this bundle,
then run `python verify_bundle.py`:

```python
{verification_script}
```

### 3. Expected output

If the chain is intact:
```
PASS — {entry_count} entries verified
```

If the chain has been tampered with, you will see:
```
FAIL — broken at entry index N of {entry_count}: <reason>
```

## What the Verification Checks

1. **Sequence integrity**: All entries are present with no gaps in sequence numbers.
2. **Hash chain**: Each entry's hash covers its full content plus the previous entry's hash.
   Modifying any field, deleting any entry, or reordering entries invalidates all
   subsequent hashes.
3. **Signatures** (if present): Each entry's hash was signed by the private key
   corresponding to `public_key.b64`. A valid signature proves the entry was
   produced by the system holding that key.

## About WitnessADR

WitnessADR is an open-source (Apache 2.0) tamper-evident audit trail library
for AI agent decisions. Source code: https://github.com/witnessadr/witnessadr
"""

_VERIFICATION_SCRIPT = """\
import base64
import json
from pathlib import Path

from witnessadr_core import verify_chain

chain = json.loads(Path("chain.json").read_text())

pub_key_bytes = None
pub_key_file = Path("public_key.b64")
if pub_key_file.exists():
    pub_key_bytes = base64.b64decode(pub_key_file.read_text().strip())

result = verify_chain(chain, public_key_bytes=pub_key_bytes)
print(result)
if not result.is_valid:
    raise SystemExit(1)
"""


@app.command()
def export(
    db_path: Path = typer.Argument(..., help="Path to the SQLite database."),
    session_id: str = typer.Argument(..., help="Session ID to export."),
    out: Path = typer.Option(..., "--out", "-o", help="Output directory for the bundle."),
    public_key: Optional[Path] = typer.Option(
        None,
        "--public-key",
        "-k",
        help="Path to the Ed25519 public key file to include in the bundle.",
    ),
) -> None:
    """Export a self-contained compliance bundle for an auditor.

    Produces a directory containing the full ADR chain as JSON, the public
    key (if provided), and a VERIFICATION.md with step-by-step instructions
    for independent verification.
    """
    if not db_path.exists():
        err_console.print(f"[red]Database not found:[/] {db_path}")
        raise typer.Exit(1)

    store = WitnessADRStore(str(db_path))
    chain = store.get_chain(session_id)

    if not chain:
        err_console.print(f"[red]No entries found for session:[/] {session_id}")
        raise typer.Exit(1)

    out.mkdir(parents=True, exist_ok=True)

    # Write chain.json
    chain_file = out / "chain.json"
    chain_file.write_text(json.dumps(chain, indent=2))

    # Write public key if provided
    pub_key_bytes: Optional[bytes] = None
    pub_key_file = out / "public_key.b64"
    if public_key is not None and public_key.exists():
        pub_key_bytes = base64.b64decode(public_key.read_text().strip())
        pub_key_file.write_text(base64.b64encode(pub_key_bytes).decode("ascii") + "\n")

    # Verify before exporting so the bundle includes verification status
    from witnessadr_core.verify import verify_chain as _verify_chain

    result = _verify_chain(chain, public_key_bytes=pub_key_bytes)

    signed_str = "Yes (Ed25519)" if pub_key_bytes else "No"
    verification_md = _VERIFICATION_MD_TEMPLATE.format(
        session_id=session_id,
        entry_count=len(chain),
        first_timestamp=chain[0].get("timestamp", "unknown"),
        last_timestamp=chain[-1].get("timestamp", "unknown"),
        signed=signed_str,
        verification_script=_VERIFICATION_SCRIPT,
    )
    (out / "VERIFICATION.md").write_text(verification_md)

    # Summary
    console.print(f"\n[green]✓[/] Export written to: {out}/")
    console.print(f"  chain.json       — {len(chain)} entries")
    if pub_key_bytes:
        console.print("  public_key.b64   — included")
    console.print("  VERIFICATION.md  — auditor instructions + standalone script")
    console.print()

    if result.is_valid:
        console.print(f"[green]Chain integrity:[/] PASS — all {len(chain)} entries verified")
    else:
        console.print(
            f"[yellow]Chain integrity:[/] WARNING — chain broken at index "
            f"{result.first_broken_index}: {result.broken_reason}"
        )
        console.print("The export bundle still contains the raw chain for forensic review.")
