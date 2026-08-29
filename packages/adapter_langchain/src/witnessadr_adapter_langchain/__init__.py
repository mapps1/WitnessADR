"""WitnessADR adapter for LangChain.

Usage (under 5 lines of integration code):

    from witnessadr_storage_sqlite import WitnessADRStore
    from witnessadr_adapter_langchain import WitnessADRCallbackHandler

    store = WitnessADRStore("audit.db")
    handler = WitnessADRCallbackHandler(store, session_id="session-001")

    # Pass to any LangChain chain, agent, or tool:
    chain.invoke({"input": "..."}, config={"callbacks": [handler]})
"""

__version__ = "0.1.0"

from .handler import WitnessADRCallbackHandler

__all__ = ["WitnessADRCallbackHandler"]
