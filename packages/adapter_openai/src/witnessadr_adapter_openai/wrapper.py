"""OpenAI SDK wrapper that records chat completions as ADR entries."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from witnessadr_core.redaction import HashOnlyRedactor, Redactor

if TYPE_CHECKING:
    from witnessadr_storage_sqlite import WitnessADRStore


def _hash_messages(messages: list[dict]) -> str:
    canonical = json.dumps(messages, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class WitnessADROpenAI:
    """Thin wrapper around an openai.OpenAI (or AsyncOpenAI) client that
    records each chat completion as a tamper-evident ADR entry.

    Wraps only the methods you use — it does not replace the original client.
    Access the underlying client at any time via `.client`.

    Args:
        client: An openai.OpenAI (or compatible) client instance.
        store: A WitnessADRStore instance.
        session_id: Session identifier for all entries written by this wrapper.
        agent_id: Identifier for the agent. Defaults to "openai-agent".
        redactor: Controls what input context is stored. Defaults to
            HashOnlyRedactor (stores only the hash of messages, not their content).
        private_key_bytes: Optional Ed25519 private key for signing entries.
        retention_class: ADR retention class for all entries. Defaults to "general".
    """

    def __init__(
        self,
        client: Any,
        store: "WitnessADRStore",
        session_id: str,
        *,
        agent_id: str = "openai-agent",
        redactor: Redactor | None = None,
        private_key_bytes: bytes | None = None,
        retention_class: str = "general",
    ) -> None:
        self.client = client
        self._store = store
        self._session_id = session_id
        self._agent_id = agent_id
        self._redactor = redactor or HashOnlyRedactor()
        self._private_key_bytes = private_key_bytes
        self._retention_class = retention_class

    def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        decision_type: str = "reasoning_step",
        policy_checks: list[dict] | None = None,
        **openai_kwargs: Any,
    ) -> Any:
        """Call chat.completions.create and record an ADR entry.

        Args:
            model: OpenAI model name (e.g. "gpt-4o").
            messages: List of message dicts (role + content).
            decision_type: ADR decision type. Defaults to "reasoning_step".
            policy_checks: Optional list of policy check results to include.
            **openai_kwargs: Passed through to client.chat.completions.create.

        Returns:
            The raw openai ChatCompletion response object.
        """
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            **openai_kwargs,
        )

        choice = response.choices[0] if response.choices else None
        content = ""
        finish_reason = ""
        if choice:
            content = (choice.message.content or "")[:500]
            finish_reason = choice.finish_reason or ""

        tool_calls = []
        if choice and choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": tc.function.name,
                    "args": tc.function.arguments[:200],
                }
                for tc in choice.message.tool_calls
            ]

        outcome = content or (
            f"Tool calls: {', '.join(t['function'] for t in tool_calls)}"
            if tool_calls
            else finish_reason or "no content"
        )

        self._store.append(
            session_id=self._session_id,
            agent_id=self._agent_id,
            actor={"type": "model", "model": model},
            decision_type=decision_type,
            action={
                "description": f"OpenAI chat completion ({model})",
                "parameters": {
                    "model": model,
                    "message_count": len(messages),
                    "tool_calls": tool_calls or None,
                },
            },
            outcome=outcome,
            raw_input_context={"messages": messages},
            redactor=self._redactor,
            policy_checks=policy_checks,
            retention_class=self._retention_class,
            private_key_bytes=self._private_key_bytes,
        )

        return response

    async def achat(
        self,
        model: str,
        messages: list[dict],
        *,
        decision_type: str = "reasoning_step",
        policy_checks: list[dict] | None = None,
        **openai_kwargs: Any,
    ) -> Any:
        """Async version of chat(). Requires an async OpenAI client."""
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            **openai_kwargs,
        )

        choice = response.choices[0] if response.choices else None
        content = (choice.message.content or "")[:500] if choice else ""
        outcome = content or "no content"

        import asyncio

        await asyncio.to_thread(
            self._store.append,
            session_id=self._session_id,
            agent_id=self._agent_id,
            actor={"type": "model", "model": model},
            decision_type=decision_type,
            action={
                "description": f"OpenAI chat completion ({model})",
                "parameters": {"model": model, "message_count": len(messages)},
            },
            outcome=outcome,
            raw_input_context={"messages": messages},
            redactor=self._redactor,
            policy_checks=policy_checks,
            retention_class=self._retention_class,
            private_key_bytes=self._private_key_bytes,
        )

        return response


def record_openai_tool_call(
    store: "WitnessADRStore",
    session_id: str,
    *,
    agent_id: str,
    tool_name: str,
    tool_input: dict,
    tool_output: str,
    model: str = "unknown",
    private_key_bytes: bytes | None = None,
    retention_class: str = "general",
) -> dict:
    """Record a single OpenAI function/tool call as an ADR entry.

    Use this when you are managing tool calls manually (not using WitnessADROpenAI)
    and want to record each tool dispatch as its own ADR entry.
    """
    redactor = HashOnlyRedactor()
    _, input_hash = redactor.redact(tool_input)

    return store.append(
        session_id=session_id,
        agent_id=agent_id,
        actor={"type": "model", "model": model},
        decision_type="tool_call",
        action={
            "description": f"Function call: {tool_name}",
            "tool_name": tool_name,
            "parameters": {k: str(v)[:200] for k, v in tool_input.items()},
        },
        outcome=tool_output[:500],
        input_context_hash=input_hash,
        retention_class=retention_class,
        private_key_bytes=private_key_bytes,
    )
