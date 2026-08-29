# OpenAI Integration

`WitnessADROpenAI` wraps an `openai.OpenAI` client and records each chat completion as a tamper-evident ADR entry.

## Installation

```bash
pip install witnessadr-storage-sqlite witnessadr-adapter-openai openai
```

## Basic Usage

```python
import openai
from witnessadr_storage_sqlite import WitnessADRStore
from witnessadr_adapter_openai import WitnessADROpenAI

store = WitnessADRStore("audit.db")

# Wrap your existing OpenAI client
client = WitnessADROpenAI(openai.OpenAI(), store, session_id="session-001")

# Use client.chat() instead of client.chat.completions.create()
response = client.chat(
    "gpt-4o",
    messages=[{"role": "user", "content": "Explain tamper-evident logging"}],
)
# The response is the raw ChatCompletion object — no change to downstream code
```

## Configuration

```python
from witnessadr_core.redaction import RegexPIIRedactor
from witnessadr_core.signing import generate_keypair

private_key, public_key = generate_keypair()

client = WitnessADROpenAI(
    openai.OpenAI(),
    store,
    session_id="session-001",
    agent_id="policy-checker-v2",       # defaults to "openai-agent"
    redactor=RegexPIIRedactor(),        # default: HashOnlyRedactor
    private_key_bytes=private_key,      # default: no signing
    retention_class="eu_ai_act_high_risk",  # default: "general"
)
```

## Recording Tool Calls Explicitly

For agentic loops where you manage tool calls manually:

```python
from witnessadr_adapter_openai import record_openai_tool_call

# After a tool executes, record it:
record_openai_tool_call(
    store,
    session_id="session-001",
    agent_id="my-agent",
    tool_name="database_query",
    tool_input={"sql": "SELECT * FROM decisions WHERE risk_level = 'high'"},
    tool_output="Returned 12 rows.",
    model="gpt-4o",
    private_key_bytes=private_key,
)
```

## Async Usage

```python
import openai
from witnessadr_storage_sqlite import AsyncWitnessADRStore
from witnessadr_adapter_openai import WitnessADROpenAI

async def run():
    async with AsyncWitnessADRStore("audit.db") as store:
        # For async, pass an AsyncOpenAI client:
        client = WitnessADROpenAI(openai.AsyncOpenAI(), store, session_id="s1")
        response = await client.achat(
            "gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )
```

## Privacy

By default, `HashOnlyRedactor` is used — message content is never stored, only its SHA-256 hash. The stored entry looks like:

```json
{
  "input_context_hash": "sha256:3a7b9c2f...",
  "action": {
    "description": "OpenAI chat completion (gpt-4o)",
    "parameters": {"model": "gpt-4o", "message_count": 1}
  },
  "outcome": "Tamper-evident logging uses a hash chain where..."
}
```

The `outcome` (model's response) is stored because it's the decision output, not the user's input.

## Example: Multi-turn Agent Loop

```python
import openai
from witnessadr_core.signing import generate_keypair
from witnessadr_storage_sqlite import WitnessADRStore
from witnessadr_adapter_openai import WitnessADROpenAI, record_openai_tool_call

private_key, public_key = generate_keypair()
store = WitnessADRStore("audit.db")
client = WitnessADROpenAI(
    openai.OpenAI(), store, session_id="run-001",
    retention_class="eu_ai_act_high_risk",
    private_key_bytes=private_key,
)

messages = [
    {"role": "system", "content": "You are a compliance checker."},
    {"role": "user", "content": "Check if our AI system meets EU AI Act requirements."},
]

# Multi-turn with tool calls
for _ in range(3):
    response = client.chat(
        "gpt-4o",
        messages=messages,
        tools=[{"type": "function", "function": {"name": "check_requirement", ...}}],
    )

    # If model wants to call a tool:
    if response.choices[0].finish_reason == "tool_calls":
        for tc in response.choices[0].message.tool_calls:
            result = run_tool(tc.function.name, tc.function.arguments)
            record_openai_tool_call(
                store, session_id="run-001", agent_id="compliance-agent",
                tool_name=tc.function.name,
                tool_input={"args": tc.function.arguments},
                tool_output=result,
                model="gpt-4o",
                private_key_bytes=private_key,
            )
        # continue loop...

# Verify the entire session
vr = store.verify("run-001", public_key_bytes=public_key)
print(vr)  # PASS — N entries verified
```
