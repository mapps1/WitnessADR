"""Tests for the OpenAI SDK adapter.

Uses mock objects to simulate the OpenAI client — no real API calls.
"""

from unittest.mock import MagicMock

import pytest
from witnessadr_adapter_openai import WitnessADROpenAI, record_openai_tool_call
from witnessadr_core.signing import generate_keypair
from witnessadr_storage_sqlite import WitnessADRStore


@pytest.fixture
def store(tmp_path):
    return WitnessADRStore(str(tmp_path / "test.db"))


def _mock_client(content="The answer is 42.", finish_reason="stop"):
    choice = MagicMock()
    choice.message.content = content
    choice.message.tool_calls = None
    choice.finish_reason = finish_reason

    response = MagicMock()
    response.choices = [choice]

    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client, response


# ── Basic recording ───────────────────────────────────────────────────────────

def test_chat_writes_one_entry(store):
    mock_client, _ = _mock_client()
    w = WitnessADROpenAI(mock_client, store, session_id="s1")

    w.chat("gpt-4o", messages=[{"role": "user", "content": "Hello"}])

    chain = store.get_chain("s1")
    assert len(chain) == 1
    assert chain[0]["decision_type"] == "reasoning_step"
    assert chain[0]["actor"]["model"] == "gpt-4o"
    assert "42" in chain[0]["outcome"]


def test_chat_passes_kwargs_to_openai(store):
    mock_client, _ = _mock_client()
    w = WitnessADROpenAI(mock_client, store, session_id="s1")

    w.chat("gpt-4o", messages=[], temperature=0.7, max_tokens=100)

    mock_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o", messages=[], temperature=0.7, max_tokens=100
    )


def test_chat_returns_raw_response(store):
    mock_client, expected_response = _mock_client("hi there")
    w = WitnessADROpenAI(mock_client, store, session_id="s1")

    result = w.chat("gpt-4o", messages=[])
    assert result is expected_response


def test_multiple_calls_build_valid_chain(store):
    mock_client, _ = _mock_client()
    w = WitnessADROpenAI(mock_client, store, session_id="s1")

    for _ in range(4):
        w.chat("gpt-4o", messages=[])

    result = store.verify("s1")
    assert result.is_valid
    assert result.total_entries == 4


def test_chat_with_signing(store):
    private_key, public_key = generate_keypair()
    mock_client, _ = _mock_client()
    w = WitnessADROpenAI(mock_client, store, session_id="s1", private_key_bytes=private_key)

    w.chat("gpt-4o", messages=[{"role": "user", "content": "sign this"}])

    result = store.verify("s1", public_key_bytes=public_key)
    assert result.is_valid


def test_tool_calls_in_response(store):
    """Entries for tool-calling responses should include tool call details in action."""
    tool_call = MagicMock()
    tool_call.id = "call_abc123"
    tool_call.function.name = "get_weather"
    tool_call.function.arguments = '{"city": "London"}'

    choice = MagicMock()
    choice.message.content = None
    choice.message.tool_calls = [tool_call]
    choice.finish_reason = "tool_calls"

    response = MagicMock()
    response.choices = [choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = response

    w = WitnessADROpenAI(mock_client, store, session_id="s1")
    w.chat("gpt-4o", messages=[], decision_type="tool_call")

    chain = store.get_chain("s1")
    assert len(chain) == 1
    assert "get_weather" in chain[0]["outcome"]


def test_raw_messages_not_stored_in_entry(store):
    """HashOnlyRedactor default: raw message content must not appear in the stored entry."""
    import json

    mock_client, _ = _mock_client()
    w = WitnessADROpenAI(mock_client, store, session_id="s1")
    w.chat("gpt-4o", messages=[{"role": "user", "content": "SECRET_TOKEN_XYZZY"}])

    entry_str = json.dumps(store.get_chain("s1"))
    assert "SECRET_TOKEN_XYZZY" not in entry_str


# ── record_openai_tool_call helper ────────────────────────────────────────────

def test_record_openai_tool_call(store):
    entry = record_openai_tool_call(
        store,
        session_id="s1",
        agent_id="my-agent",
        tool_name="database_query",
        tool_input={"sql": "SELECT * FROM users LIMIT 10"},
        tool_output="Returned 10 rows.",
        model="gpt-4o",
    )
    assert entry["decision_type"] == "tool_call"
    assert entry["action"]["tool_name"] == "database_query"
    assert entry["outcome"] == "Returned 10 rows."


def test_record_openai_tool_call_chain_verifies(store):
    for i in range(3):
        record_openai_tool_call(
            store,
            session_id="s1",
            agent_id="a1",
            tool_name=f"tool_{i}",
            tool_input={"param": str(i)},
            tool_output=f"result {i}",
        )

    result = store.verify("s1")
    assert result.is_valid
    assert result.total_entries == 3
