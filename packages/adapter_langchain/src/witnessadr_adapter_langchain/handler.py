"""LangChain callback handler that writes ADR entries to a WitnessADRStore.

Each LangChain callback pair (start + end) produces exactly one ADR entry,
recorded on the *end* event when both input and output are available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from witnessadr_core.redaction import HashOnlyRedactor, Redactor

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
except ImportError as exc:
    raise ImportError(
        "witnessadr-adapter-langchain requires langchain-core. "
        "Install it with: pip install 'witnessadr-adapter-langchain[langchain]'"
    ) from exc

if TYPE_CHECKING:
    from witnessadr_storage_sqlite import WitnessADRStore


class WitnessADRCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that records each LLM call and tool invocation
    as a tamper-evident ADR entry.

    Integrates with any LangChain chain, agent, or tool in one line:
        callbacks=[WitnessADRCallbackHandler(store, session_id="s-001")]

    One ADR entry is written per event (LLM call or tool call), on the *end*
    callback so both input and output are captured together.

    Args:
        store: A WitnessADRStore instance.
        session_id: Session identifier for all entries written by this handler.
        agent_id: Identifier for the agent. Defaults to "langchain-agent".
        redactor: Controls what input context is stored. Defaults to
            HashOnlyRedactor (stores nothing — only the hash).
        private_key_bytes: Raw 32-byte Ed25519 private key for signing entries.
            If None, entries are not signed.
    """

    raise_error = False  # do not let ADR recording errors crash the agent

    def __init__(
        self,
        store: "WitnessADRStore",
        session_id: str,
        *,
        agent_id: str = "langchain-agent",
        redactor: Redactor | None = None,
        private_key_bytes: bytes | None = None,
    ) -> None:
        super().__init__()
        self._store = store
        self._session_id = session_id
        self._agent_id = agent_id
        self._redactor = redactor or HashOnlyRedactor()
        self._private_key_bytes = private_key_bytes
        # run_id (str) → {"type": "llm"|"tool", ...start data}
        self._pending: dict[str, dict] = {}

    # ── LLM callbacks ─────────────────────────────────────────────────────

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        model_name = (
            serialized.get("name")
            or serialized.get("kwargs", {}).get("model_name")
            or (serialized.get("id") or ["unknown"])[-1]
        )
        self._pending[str(run_id)] = {
            "type": "llm",
            "model": model_name,
            "prompts": prompts,
        }

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        start = self._pending.pop(str(run_id), {})
        model = start.get("model", "unknown")
        prompts = start.get("prompts", [])

        output_texts = []
        for gen_list in response.generations:
            for gen in gen_list:
                if hasattr(gen, "text") and gen.text:
                    output_texts.append(gen.text)
                elif hasattr(gen, "message") and hasattr(gen.message, "content"):
                    output_texts.append(gen.message.content or "")

        outcome = (
            "; ".join(t for t in output_texts if t)[:500] or "LLM response received"
        )

        self._store.append(
            session_id=self._session_id,
            agent_id=self._agent_id,
            actor={"type": "model", "model": model},
            decision_type="reasoning_step",
            action={
                "description": "LLM inference",
                "parameters": {"prompt_count": len(prompts)},
            },
            outcome=outcome,
            raw_input_context={"prompts": prompts},
            redactor=self._redactor,
            private_key_bytes=self._private_key_bytes,
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._pending.pop(str(run_id), None)
        self._record_error(error, "LLM error")

    # ── Tool callbacks ────────────────────────────────────────────────────

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name", "unknown_tool")
        self._pending[str(run_id)] = {
            "type": "tool",
            "tool_name": tool_name,
            "input": input_str,
        }

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        start = self._pending.pop(str(run_id), {})
        tool_name = start.get("tool_name", "unknown_tool")
        input_str = start.get("input", "")

        self._store.append(
            session_id=self._session_id,
            agent_id=self._agent_id,
            actor={"type": "model", "model": "langchain-agent"},
            decision_type="tool_call",
            action={
                "description": f"Tool invocation: {tool_name}",
                "tool_name": tool_name,
                "parameters": {"input": str(input_str)[:500]},
            },
            outcome=str(output)[:500] if output is not None else "no output",
            raw_input_context={"tool_name": tool_name, "input": str(input_str)[:500]},
            redactor=self._redactor,
            private_key_bytes=self._private_key_bytes,
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        start = self._pending.pop(str(run_id), {})
        tool_name = start.get("tool_name", "unknown_tool")
        self._record_error(error, f"Tool error: {tool_name}")

    # ── Chain / agent error ───────────────────────────────────────────────

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._pending.pop(str(run_id), None)
        self._record_error(error, "Chain error")

    # ── Internal helper ───────────────────────────────────────────────────

    def _record_error(self, error: BaseException, context: str) -> None:
        self._store.append(
            session_id=self._session_id,
            agent_id=self._agent_id,
            actor={"type": "model", "model": "langchain-agent"},
            decision_type="escalation",
            action={
                "description": f"{context}: {type(error).__name__}",
                "parameters": {"error_type": type(error).__name__},
            },
            outcome=str(error)[:500],
            input_context_hash="sha256:" + "0" * 64,
            private_key_bytes=self._private_key_bytes,
        )
