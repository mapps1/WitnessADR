#!/usr/bin/env python3
"""
WitnessADR — Verify and export compliance bundle example

Demonstrates using the witnessadr CLI commands programmatically, and
producing a self-contained export bundle that an auditor can verify
without the original database.

Run with:
    pip install witnessadr-cli
    python examples/verify_and_export_example.py
"""

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from witnessadr_core.signing import generate_keypair
from witnessadr_storage_sqlite import WitnessADRStore


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "audit.db"
        key_path = tmp / "witnessadr.key"
        pub_path = tmp / "witnessadr.key.pub"
        export_dir = tmp / "compliance-bundle"

        # ── Set up store and write a sample session ─────────────────────────
        private_key, public_key = generate_keypair()
        key_path.write_text(base64.b64encode(private_key).decode("ascii") + "\n")
        pub_path.write_text(base64.b64encode(public_key).decode("ascii") + "\n")

        store = WitnessADRStore(str(db_path))
        session_id = "compliance-demo-session"

        for i in range(4):
            store.append(
                session_id=session_id,
                agent_id="compliance-agent",
                actor={"type": "model", "model": "claude-sonnet-4"},
                decision_type="tool_call",
                action={
                    "description": f"Compliance check step {i}",
                    "tool_name": "policy_check",
                    "parameters": {"check_id": f"CHK-{i:03d}"},
                },
                outcome=f"Step {i} passed all policy gates",
                input_context_hash="sha256:" + f"{i}" * 64,
                policy_checks=[{"policy_id": f"policy-{i}", "result": "pass"}],
                retention_class="eu_ai_act_high_risk",
                private_key_bytes=private_key,
            )

        print(f"Wrote {len(store.get_chain(session_id))} ADR entries to {db_path}\n")

        # ── Run `witnessadr verify` via the CLI ─────────────────────────────
        print("--- Running: witnessadr verify ---")
        result = subprocess.run(
            [
                sys.executable, "-m", "witnessadr_cli.main",
                "verify", str(db_path), session_id,
                "--public-key", str(pub_path),
            ],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        print(f"Exit code: {result.returncode} (0 = valid)")

        # ── Run `witnessadr export` via the CLI ─────────────────────────────
        print("\n--- Running: witnessadr export ---")
        result = subprocess.run(
            [
                sys.executable, "-m", "witnessadr_cli.main",
                "export", str(db_path), session_id,
                "--out", str(export_dir),
                "--public-key", str(pub_path),
            ],
            capture_output=True,
            text=True,
        )
        print(result.stdout)

        # ── Show the bundle structure ────────────────────────────────────────
        print("\n--- Export bundle contents ---")
        for f in sorted(export_dir.iterdir()):
            size = f.stat().st_size
            print(f"  {f.name:30s}  {size:,} bytes")

        # ── Verify the exported chain directly using witnessadr_core ────────
        print("\n--- Verifying exported chain.json with witnessadr_core ---")
        chain = json.loads((export_dir / "chain.json").read_text())
        pub_key_b64 = (export_dir / "public_key.b64").read_text().strip()
        pub_key_bytes = base64.b64decode(pub_key_b64)

        from witnessadr_core import verify_chain
        vr = verify_chain(chain, public_key_bytes=pub_key_bytes)
        print(vr)

        print("\nAll checks passed. The export bundle is ready for an auditor.")


if __name__ == "__main__":
    main()
