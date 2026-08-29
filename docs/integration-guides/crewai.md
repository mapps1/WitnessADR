# CrewAI Integration

!!! note "Coming in Phase 5"
    The `witnessadr-adapter-crewai` package is planned. Manual recording works now.

## Manual Recording (Available Now)

```python
from crewai import Agent, Task, Crew
from witnessadr_storage_sqlite import WitnessADRStore

store = WitnessADRStore("audit.db")

# After each task completes, record it:
def record_task_result(task_name: str, input_summary: str, output: str):
    store.append(
        session_id="crew-run-001",
        agent_id="research-crew",
        actor={"type": "model", "model": "gpt-4o"},
        decision_type="final_action",
        action={"description": f"CrewAI task: {task_name}"},
        outcome=output[:500],
        input_context_hash="sha256:" + "a" * 64,
        retention_class="general",
    )
```

Track progress in [the WitnessADR roadmap](https://github.com/witnessadr/witnessadr/issues).
