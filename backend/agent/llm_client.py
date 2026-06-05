"""
llm_client.py
-------------
Thin async wrapper around the OpenAI chat-completions API.

The module-level ``AsyncOpenAI`` client is created once at import time and
reused for every request, which is the pattern recommended by the openai-python
library to avoid unnecessary TCP connection churn.
"""
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load .env values before the client is constructed so OPENAI_API_KEY is set.
load_dotenv(override=True)

# Single shared client — AsyncOpenAI is safe to share across coroutines.
_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    model: str = "gpt-4o",
) -> str:
    """
    Make a single (non-streaming) chat-completion request.

    Parameters
    ----------
    system_prompt: Instruction text placed in the ``system`` role.
    user_prompt:   Task/query text placed in the ``user`` role.
    temperature:   Sampling temperature (0 = deterministic, 1 = creative).
    model:         OpenAI model identifier.

    Returns
    -------
    The assistant's response text.
    """
    response = await _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content


async def call_llm_stream(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
):
    """
    Yield response tokens one at a time as they arrive from the API.

    This is an async generator; iterate with ``async for token in call_llm_stream(...)``.

    Parameters
    ----------
    system_prompt: Instruction text placed in the ``system`` role.
    user_prompt:   Task/query text placed in the ``user`` role.
    temperature:   Sampling temperature.
    """
    stream = await _client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=temperature,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
