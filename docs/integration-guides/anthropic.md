# Anthropic Integration

!!! note "Coming in Phase 2"
    The `witnessadr-adapter-anthropic` package is planned for a near-term release.
    In the meantime, you can record Anthropic API calls manually using the raw `witnessadr-core` API.

## Manual Recording (Available Now)

```python
import anthropic
import hashlib
import json
from witnessadr_storage_sqlite import WitnessADRStore

store = WitnessADRStore("audit.db")
client = anthropic.Anthropic()

messages = [{"role": "user", "content": "Explain tamper-evident logging"}]

# Hash the input context before sending
ctx_hash = "sha256:" + hashlib.sha256(
    json.dumps(messages, sort_keys=True).encode()
).hexdigest()

response = client.messages.create(
    model="claude-sonnet-4",
    max_tokens=1024,
    messages=messages,
)

store.append(
    session_id="session-001",
    agent_id="my-agent",
    actor={"type": "model", "model": "claude-sonnet-4"},
    decision_type="reasoning_step",
    action={"description": "Anthropic inference"},
    outcome=response.content[0].text[:500],
    input_context_hash=ctx_hash,
)
```

## Track Progress

Watch [GitHub issue #X](https://github.com/witnessadr/witnessadr/issues) for the Anthropic adapter release, or contribute the adapter following the [contribution guide](../CONTRIBUTING.md).
