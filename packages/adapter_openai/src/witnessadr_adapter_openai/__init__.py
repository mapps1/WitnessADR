"""WitnessADR adapter for the OpenAI Python SDK.

Usage (under 5 lines of integration code):

    import openai
    from witnessadr_storage_sqlite import WitnessADRStore
    from witnessadr_adapter_openai import WitnessADROpenAI

    store = WitnessADRStore("audit.db")
    client = WitnessADROpenAI(openai.OpenAI(), store, session_id="session-001")

    response = client.chat("gpt-4o", messages=[{"role": "user", "content": "Hello"}])
"""

__version__ = "0.1.0"

from .wrapper import WitnessADROpenAI, record_openai_tool_call

__all__ = ["WitnessADROpenAI", "record_openai_tool_call"]
