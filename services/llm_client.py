"""
LLM Client — Groq (primary/free), OpenAI, Anthropic fallbacks.
Set LLM_PROVIDER=groq|openai|anthropic in .env
"""
from __future__ import annotations
import os, re, json
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

PROVIDER     = os.getenv("LLM_PROVIDER", "groq").lower()
GROQ_KEY     = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OAI_KEY      = os.getenv("OPENAI_API_KEY", "")
OAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANT_KEY      = os.getenv("ANTHROPIC_API_KEY", "")
ANT_MODEL    = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")


async def chat_completion(
    system_prompt: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> str:
    if PROVIDER == "groq":
        from groq import AsyncGroq
        client = AsyncGroq(api_key=GROQ_KEY)
        full = [{"role": "system", "content": system_prompt}] + messages
        resp = await client.chat.completions.create(
            model=GROQ_MODEL, messages=full,
            temperature=temperature, max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()

    elif PROVIDER == "anthropic":
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=ANT_KEY)
        resp = await client.messages.create(
            model=ANT_MODEL, max_tokens=max_tokens,
            system=system_prompt, messages=messages,
        )
        return resp.content[0].text.strip()

    else:  # openai
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OAI_KEY)
        full = [{"role": "system", "content": system_prompt}] + messages
        resp = await client.chat.completions.create(
            model=OAI_MODEL, messages=full,
            temperature=temperature, max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()


async def structured_completion(
    system_prompt: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 3000,
) -> str:
    """Low-temperature call for JSON outputs."""
    return await chat_completion(
        system_prompt=system_prompt,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def json_completion(
    system_prompt: str,
    messages: List[Dict[str, str]],
    max_tokens: int = 3000,
) -> dict:
    """Returns parsed dict. Strips markdown fences and trailing commas."""
    raw = await structured_completion(
        system_prompt + "\n\nCRITICAL: Return ONLY valid JSON. No markdown fences, no explanation.",
        messages,
        temperature=0.1,
        max_tokens=max_tokens,
    )
    cleaned = re.sub(r"```json|```", "", raw).strip()
    cleaned = re.sub(r",\s*}", "}", cleaned)
    cleaned = re.sub(r",\s*]", "]", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise ValueError(f"LLM returned invalid JSON: {cleaned[:300]}")