"""
conftest.py — stub out optional heavy dependencies so tests run
without openai or sentence-transformers installed.
"""
import sys
from unittest.mock import MagicMock

# Stub openai so llm_client.py can be imported without the package installed
if "openai" not in sys.modules:
    openai_stub = MagicMock()
    # AsyncOpenAI(api_key=...) must return a usable object
    openai_stub.AsyncOpenAI.return_value = MagicMock()
    sys.modules["openai"] = openai_stub
