# LangChain Integration

`WitnessADRCallbackHandler` integrates with any LangChain chain, agent, or tool using LangChain's standard callback interface. One ADR entry is written per event (LLM call or tool invocation).

## Installation

```bash
pip install witnessadr-storage-sqlite "witnessadr-adapter-langchain[langchain]"
```

## Basic Usage

```python
from witnessadr_storage_sqlite import WitnessADRStore
from witnessadr_adapter_langchain import WitnessADRCallbackHandler

store = WitnessADRStore("audit.db")
handler = WitnessADRCallbackHandler(store, session_id="session-001")

# Pass to any chain, agent, or LLM:
result = chain.invoke(
    {"input": "Summarize the EU AI Act high-risk provisions"},
    config={"callbacks": [handler]},
)
```

That's it. Every LLM call and tool invocation in the chain is now recorded as a tamper-evident ADR entry.

## Configuration Options

```python
from witnessadr_core.redaction import RegexPIIRedactor
from witnessadr_core.signing import generate_keypair

private_key, public_key = generate_keypair()

handler = WitnessADRCallbackHandler(
    store,
    session_id="session-001",
    agent_id="compliance-agent-v2",          # defaults to "langchain-agent"
    redactor=RegexPIIRedactor(),             # default: HashOnlyRedactor
    private_key_bytes=private_key,           # default: no signing
)
```

## What Gets Recorded

| LangChain event | ADR `decision_type` | Triggered |
|---|---|---|
| `on_llm_start` + `on_llm_end` | `reasoning_step` | On LLM end (both input and output available) |
| `on_tool_start` + `on_tool_end` | `tool_call` | On tool end |
| `on_llm_error` | `escalation` | On error |
| `on_tool_error` | `escalation` | On error |
| `on_chain_error` | `escalation` | On error |

Each start/end pair produces exactly one ADR entry, recorded on the end event when both input and output are known.

## Privacy: What is Stored

By default, `HashOnlyRedactor` is used — only the SHA-256 hash of the prompt/input is stored, never the content itself. This makes the adapter safe for regulated environments out of the box.

To store a PII-scrubbed version of the input instead:

```python
from witnessadr_core.redaction import RegexPIIRedactor
handler = WitnessADRCallbackHandler(store, session_id="s1", redactor=RegexPIIRedactor())
```

## Verifying the Chain

After a session completes:

```python
result = store.verify("session-001", public_key_bytes=public_key)
print(result)
# PASS — 5 entries verified
```

## Example: LangChain Agent with Tool Use

```python
import os
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from witnessadr_core.signing import generate_keypair
from witnessadr_storage_sqlite import WitnessADRStore
from witnessadr_adapter_langchain import WitnessADRCallbackHandler

# Setup
private_key, public_key = generate_keypair()
store = WitnessADRStore("agent_audit.db")
handler = WitnessADRCallbackHandler(
    store, session_id="run-001", private_key_bytes=private_key
)

# Define a tool
@tool
def get_policy_summary(policy_name: str) -> str:
    """Returns a summary of a named policy document."""
    return f"Policy '{policy_name}': requires logging of all high-risk AI decisions."

# Build and run the agent
llm = ChatOpenAI(model="gpt-4o")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a compliance assistant."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])
agent = create_tool_calling_agent(llm, [get_policy_summary], prompt)
executor = AgentExecutor(agent=agent, tools=[get_policy_summary])

result = executor.invoke(
    {"input": "What does the EU AI Act require for high-risk AI logging?"},
    config={"callbacks": [handler]},
)

# Verify
vr = store.verify("run-001", public_key_bytes=public_key)
print(vr)
```
