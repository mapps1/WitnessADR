"""SQLite-backed WitnessADR store.

Provides both a synchronous (WitnessADRStore) and async (AsyncWitnessADRStore)
interface backed by a local SQLite file.

The sync version is safe to call from async code via asyncio.to_thread:
    entry = await asyncio.to_thread(store.append, ...)

The async version uses aiosqlite and is directly awaitable.
"""

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Literal

import aiosqlite
from witnessadr_core.hashing import compute_entry_hash
from witnessadr_core.redaction import HashOnlyRedactor, Redactor
from witnessadr_core.schema import validate_entry
from witnessadr_core.signing import sign_hash
from witnessadr_core.verify import VerificationResult, verify_chain

# ── Schema ────────────────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS adr_entries (
    id            TEXT NOT NULL,
    session_id    TEXT NOT NULL,
    agent_id      TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    timestamp     TEXT NOT NULL,
    entry_data    TEXT NOT NULL,
    UNIQUE(session_id, sequence_number)
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_session_seq ON adr_entries(session_id, sequence_number);",
    "CREATE INDEX IF NOT EXISTS idx_agent       ON adr_entries(agent_id);",
    "CREATE INDEX IF NOT EXISTS idx_timestamp   ON adr_entries(timestamp);",
]


def _setup_sync(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE_TABLE)
    for stmt in _CREATE_INDEXES:
        conn.execute(stmt)
    conn.commit()


async def _setup_async(db: aiosqlite.Connection) -> None:
    await db.execute(_CREATE_TABLE)
    for stmt in _CREATE_INDEXES:
        await db.execute(stmt)
    await db.commit()


# ── Entry construction helper ─────────────────────────────────────────────────

def _build_entry(
    *,
    session_id: str,
    agent_id: str,
    actor: dict,
    decision_type: str,
    action: dict,
    outcome: str,
    input_context_hash: str,
    retention_class: str,
    sequence_number: int,
    prev_hash: str | None,
    input_context_ref: str | None,
    policy_checks: list[dict] | None,
    human_approval: dict | None,
    private_key_bytes: bytes | None,
) -> dict:
    entry: dict = {
        "adr_version": "1.0",
        "id": str(uuid.uuid4()),
        "sequence_number": sequence_number,
        "prev_hash": prev_hash,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
        "agent_id": agent_id,
        "actor": actor,
        "decision_type": decision_type,
        "input_context_hash": input_context_hash,
        "action": action,
        "outcome": outcome,
        "retention_class": retention_class,
    }
    if input_context_ref is not None:
        entry["input_context_ref"] = input_context_ref
    if policy_checks:
        entry["policy_checks"] = policy_checks
    if human_approval:
        entry["human_approval"] = human_approval

    entry["entry_hash"] = compute_entry_hash(entry, prev_hash)
    if private_key_bytes is not None:
        entry["signature"] = sign_hash(entry["entry_hash"], private_key_bytes)

    validate_entry(entry)
    return entry


def _resolve_input_context(
    input_context_hash: str | None,
    raw_input_context: dict | None,
    redactor: Redactor | None,
) -> tuple[str, str | None]:
    """Return (input_context_hash, input_context_ref_or_None)."""
    if raw_input_context is not None:
        r = redactor or HashOnlyRedactor()
        stored, computed_hash = r.redact(raw_input_context)
        ref = json.dumps(stored, separators=(",", ":")) if stored else None
        return computed_hash, ref
    if input_context_hash is None:
        raise ValueError("Provide either input_context_hash or raw_input_context")
    return input_context_hash, None


# ── Synchronous store ─────────────────────────────────────────────────────────

class WitnessADRStore:
    """Synchronous SQLite-backed ADR store.

    Each public method opens and closes its own connection, making this
    class safe to use from multiple threads. For async code, either use
    AsyncWitnessADRStore or wrap calls with asyncio.to_thread().

    Args:
        db_path: Filesystem path to the SQLite database file. Will be
            created if it does not exist.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        with sqlite3.connect(self.db_path) as conn:
            _setup_sync(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def append(
        self,
        session_id: str,
        agent_id: str,
        actor: dict,
        decision_type: str,
        action: dict,
        outcome: str,
        *,
        input_context_hash: str | None = None,
        raw_input_context: dict | None = None,
        redactor: Redactor | None = None,
        retention_class: str = "general",
        input_context_ref: str | None = None,
        policy_checks: list[dict] | None = None,
        human_approval: dict | None = None,
        private_key_bytes: bytes | None = None,
    ) -> dict:
        """Record a new ADR entry for the given session.

        Either ``input_context_hash`` or ``raw_input_context`` must be provided.
        If ``raw_input_context`` is given, it is passed through the redactor
        (defaulting to HashOnlyRedactor) before storage.

        Returns the fully-constructed entry dict including entry_hash and
        optional signature.
        """
        ctx_hash, ctx_ref = _resolve_input_context(
            input_context_hash, raw_input_context, redactor
        )
        if input_context_ref is not None:
            ctx_ref = input_context_ref  # explicit ref overrides

        with self._connect() as conn:
            cur = conn.execute(
                "SELECT sequence_number, entry_data FROM adr_entries "
                "WHERE session_id = ? ORDER BY sequence_number DESC LIMIT 1",
                (session_id,),
            )
            row = cur.fetchone()
            if row:
                last_entry = json.loads(row["entry_data"])
                seq = row["sequence_number"] + 1
                prev_hash: str | None = last_entry["entry_hash"]
            else:
                seq = 0
                prev_hash = None

            entry = _build_entry(
                session_id=session_id,
                agent_id=agent_id,
                actor=actor,
                decision_type=decision_type,
                action=action,
                outcome=outcome,
                input_context_hash=ctx_hash,
                retention_class=retention_class,
                sequence_number=seq,
                prev_hash=prev_hash,
                input_context_ref=ctx_ref,
                policy_checks=policy_checks,
                human_approval=human_approval,
                private_key_bytes=private_key_bytes,
            )

            conn.execute(
                "INSERT INTO adr_entries "
                "(id, session_id, agent_id, sequence_number, timestamp, entry_data) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    entry["id"],
                    session_id,
                    agent_id,
                    seq,
                    entry["timestamp"],
                    json.dumps(entry),
                ),
            )
            conn.commit()

        return entry

    def get_chain(self, session_id: str) -> list[dict]:
        """Return all ADR entries for a session, in sequence order."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT entry_data FROM adr_entries "
                "WHERE session_id = ? ORDER BY sequence_number ASC",
                (session_id,),
            )
            return [json.loads(row["entry_data"]) for row in cur.fetchall()]

    def verify(
        self,
        session_id: str,
        public_key_bytes: bytes | None = None,
    ) -> VerificationResult:
        """Verify the hash chain integrity for a session."""
        entries = self.get_chain(session_id)
        return verify_chain(entries, public_key_bytes=public_key_bytes)

    def list_sessions(self) -> list[str]:
        """Return all distinct session IDs in this store."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT DISTINCT session_id FROM adr_entries ORDER BY session_id"
            )
            return [row[0] for row in cur.fetchall()]


# ── Async store ───────────────────────────────────────────────────────────────

class AsyncWitnessADRStore:
    """Async SQLite-backed ADR store using aiosqlite.

    Use as an async context manager:
        async with AsyncWitnessADRStore(db_path) as store:
            await store.append(...)
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def __aenter__(self) -> "AsyncWitnessADRStore":
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await _setup_async(self._db)
        return self

    async def __aexit__(self, *args) -> None:
        await self._db.close()

    async def append(
        self,
        session_id: str,
        agent_id: str,
        actor: dict,
        decision_type: str,
        action: dict,
        outcome: str,
        *,
        input_context_hash: str | None = None,
        raw_input_context: dict | None = None,
        redactor: Redactor | None = None,
        retention_class: str = "general",
        input_context_ref: str | None = None,
        policy_checks: list[dict] | None = None,
        human_approval: dict | None = None,
        private_key_bytes: bytes | None = None,
    ) -> dict:
        ctx_hash, ctx_ref = _resolve_input_context(
            input_context_hash, raw_input_context, redactor
        )
        if input_context_ref is not None:
            ctx_ref = input_context_ref

        async with self._db.execute(
            "SELECT sequence_number, entry_data FROM adr_entries "
            "WHERE session_id = ? ORDER BY sequence_number DESC LIMIT 1",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()

        if row:
            last_entry = json.loads(row["entry_data"])
            seq = row["sequence_number"] + 1
            prev_hash: str | None = last_entry["entry_hash"]
        else:
            seq = 0
            prev_hash = None

        # CPU-bound work runs in a thread to avoid blocking the event loop
        entry = await asyncio.to_thread(
            _build_entry,
            session_id=session_id,
            agent_id=agent_id,
            actor=actor,
            decision_type=decision_type,
            action=action,
            outcome=outcome,
            input_context_hash=ctx_hash,
            retention_class=retention_class,
            sequence_number=seq,
            prev_hash=prev_hash,
            input_context_ref=ctx_ref,
            policy_checks=policy_checks,
            human_approval=human_approval,
            private_key_bytes=private_key_bytes,
        )

        await self._db.execute(
            "INSERT INTO adr_entries "
            "(id, session_id, agent_id, sequence_number, timestamp, entry_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entry["id"], session_id, agent_id, seq, entry["timestamp"], json.dumps(entry)),
        )
        await self._db.commit()
        return entry

    async def get_chain(self, session_id: str) -> list[dict]:
        async with self._db.execute(
            "SELECT entry_data FROM adr_entries "
            "WHERE session_id = ? ORDER BY sequence_number ASC",
            (session_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [json.loads(row["entry_data"]) for row in rows]

    async def verify(
        self,
        session_id: str,
        public_key_bytes: bytes | None = None,
    ) -> VerificationResult:
        entries = await self.get_chain(session_id)
        return verify_chain(entries, public_key_bytes=public_key_bytes)


# ── Human-in-the-loop helper ──────────────────────────────────────────────────

def record_human_approval(
    store: WitnessADRStore,
    session_id: str,
    reviewed_decision_id: str,
    approver_id: str,
    decision: Literal["approved", "rejected"],
    *,
    agent_id: str = "human-review",
    private_key_bytes: bytes | None = None,
) -> dict:
    """Record a human approval or rejection of an agent decision.

    Creates a new ADR entry with decision_type="human_override" that links
    back to the original decision entry by its ID. This satisfies the
    EU AI Act Article 14 requirement for human oversight records.

    Args:
        store: A WitnessADRStore instance.
        session_id: Session ID for this approval entry.
        reviewed_decision_id: The `id` field of the ADR entry being reviewed.
        approver_id: Identifier for the human reviewer (e.g., user ID, email hash).
        decision: "approved" or "rejected".
        agent_id: Defaults to "human-review".
        private_key_bytes: Optional signing key.

    Returns:
        The newly written ADR entry.
    """
    return store.append(
        session_id=session_id,
        agent_id=agent_id,
        actor={"type": "human"},
        decision_type="human_override",
        action={
            "description": f"Human {decision} agent decision {reviewed_decision_id}",
            "parameters": {"reviewed_decision_id": reviewed_decision_id},
        },
        outcome=decision,
        input_context_hash="sha256:" + "0" * 64,
        human_approval={
            "required": True,
            "approver_id": approver_id,
            "decision": decision,
        },
        private_key_bytes=private_key_bytes,
    )
