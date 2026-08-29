"""Tests for the LangChain callback handler adapter."""

import uuid
from unittest.mock import MagicMock

import pytest

# Skip entire module if langchain-core is not installed
langchain_core = pytest.importorskip("langchain_core", reason="langchain-core not installed")

from langchain_core.outputs import LLMResult  # noqa: E402
from witnessadr_adapter_langchain import WitnessADRCallbackHandler  # noqa: E402
from witnessadr_storage_sqlite import WitnessADRStore  # noqa: E402


@pytest.fixture
def store(tmp_path):
    return WitnessADRStore(str(tmp_path / "test.db"))


@pytest.fixture
def handler(store):
    return WitnessADRCallbackHandler(store, session_id="test-session")


def _run_id():
    return uuid.uuid4()


def _llm_result(text="The answer is 42."):
    gen = MagicMock()
    gen.text = text
    return LLMResult(generations=[[gen]])


# ── LLM callbacks ─────────────────────────────────────────────────────────────

def test_llm_start_end_writes_one_entry(store, handler):
    run = _run_id()
    handler.on_llm_start({"name": "gpt-4o"}, ["What is 6 * 7?"], run_id=run)
    handler.on_llm_end(_llm_result("42"), run_id=run)

    chain = store.get_chain("test-session")
    assert len(chain) == 1
    assert chain[0]["decision_type"] == "reasoning_step"
    assert chain[0]["actor"]["model"] == "gpt-4o"
    assert "42" in chain[0]["outcome"]


def test_llm_start_does_not_write_entry_on_its_own(store, handler):
    run = _run_id()
    handler.on_llm_start({"name": "gpt-4o"}, ["prompt"], run_id=run)
    assert store.get_chain("test-session") == []


def test_llm_error_clears_pending(store, handler):
    run = _run_id()
    handler.on_llm_start({"name": "gpt-4o"}, ["prompt"], run_id=run)
    handler.on_llm_error(ValueError("rate limited"), run_id=run)

    chain = store.get_chain("test-session")
    assert len(chain) == 1
    assert chain[0]["decision_type"] == "escalation"
    assert "LLM error" in chain[0]["action"]["description"]


def test_multiple_llm_calls_separate_entries(store, handler):
    for i in range(3):
        run = _run_id()
        handler.on_llm_start({"name": "model"}, [f"prompt {i}"], run_id=run)
        handler.on_llm_end(_llm_result(f"answer {i}"), run_id=run)

    chain = store.get_chain("test-session")
    assert len(chain) == 3
    assert chain[0]["sequence_number"] == 0
    assert chain[2]["sequence_number"] == 2


# ── Tool callbacks ─────────────────────────────────────────────────────────────

def test_tool_start_end_writes_one_entry(store, handler):
    run = _run_id()
    handler.on_tool_start({"name": "web_search"}, "climate change 2024", run_id=run)
    handler.on_tool_end("Found 8 results about climate change.", run_id=run)

    chain = store.get_chain("test-session")
    assert len(chain) == 1
    assert chain[0]["decision_type"] == "tool_call"
    assert chain[0]["action"]["tool_name"] == "web_search"
    assert "8 results" in chain[0]["outcome"]


def test_tool_error_writes_escalation(store, handler):
    run = _run_id()
    handler.on_tool_start({"name": "database_query"}, "SELECT *", run_id=run)
    handler.on_tool_error(RuntimeError("Connection timeout"), run_id=run)

    chain = store.get_chain("test-session")
    assert len(chain) == 1
    assert chain[0]["decision_type"] == "escalation"


def test_chain_error_writes_escalation(store, handler):
    run = _run_id()
    handler.on_chain_error(Exception("Output parsing failed"), run_id=run)

    chain = store.get_chain("test-session")
    assert len(chain) == 1
    assert chain[0]["decision_type"] == "escalation"


# ── Mixed sequence ────────────────────────────────────────────────────────────

def test_llm_then_tool_then_llm_chain_verifies(store, handler):
    r1 = _run_id()
    handler.on_llm_start({"name": "gpt-4o"}, ["plan"], run_id=r1)
    handler.on_llm_end(_llm_result("I will search the web."), run_id=r1)

    r2 = _run_id()
    handler.on_tool_start({"name": "web_search"}, "AI governance 2024", run_id=r2)
    handler.on_tool_end("Found 5 relevant articles.", run_id=r2)

    r3 = _run_id()
    handler.on_llm_start({"name": "gpt-4o"}, ["summarize"], run_id=r3)
    handler.on_llm_end(_llm_result("Summary: ..."), run_id=r3)

    result = store.verify("test-session")
    assert result.is_valid
    assert result.total_entries == 3


# ── Signing ───────────────────────────────────────────────────────────────────

def test_handler_signs_entries_when_key_provided(store, tmp_path):
    from witnessadr_core.signing import generate_keypair
    private_key, public_key = generate_keypair()

    h = WitnessADRCallbackHandler(
        store, session_id="signed-session", private_key_bytes=private_key
    )
    run = _run_id()
    h.on_llm_start({"name": "claude"}, ["hello"], run_id=run)
    h.on_llm_end(_llm_result("hi"), run_id=run)

    result = store.verify("signed-session", public_key_bytes=public_key)
    assert result.is_valid
