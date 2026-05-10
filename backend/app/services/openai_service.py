"""Azure OpenAI helpers — embeddings, chat completion, token counting."""
from __future__ import annotations

import logging
from typing import Iterable, List

from ..config import settings
from .azure_clients import openai_client

log = logging.getLogger(__name__)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of strings. Splits into batches of 16 to stay within limits."""
    client = openai_client()
    out: List[List[float]] = []
    BATCH = 16
    for i in range(0, len(texts), BATCH):
        batch = texts[i : i + BATCH]
        # text-embedding-3-* supports `dimensions` to ensure consistent index width
        resp = client.embeddings.create(
            model=settings.openai_embedding_deployment,
            input=batch,
            dimensions=settings.openai_embedding_dimensions,
        )
        out.extend([d.embedding for d in resp.data])
    return out


def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]


def chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> tuple[str, dict]:
    """Returns (text, usage_dict).

    Newer GPT-5 family models require `max_completion_tokens` (not `max_tokens`)
    and only accept the default temperature. We try the modern parameter set
    first and fall back if the deployment is older.
    """
    client = openai_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    def _call(use_modern: bool, with_temp: bool):
        kwargs: dict = {
            "model": settings.openai_deployment,
            "messages": messages,
        }
        if with_temp:
            kwargs["temperature"] = temperature
        if use_modern:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
        return client.chat.completions.create(**kwargs)

    try:
        resp = _call(use_modern=True, with_temp=False)
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if "max_completion_tokens" in msg or "max_tokens" in msg or "unsupported parameter" in msg:
            # Older deployment; use legacy max_tokens (with temperature).
            resp = _call(use_modern=False, with_temp=True)
        else:
            raise

    text = resp.choices[0].message.content or ""
    usage = {}
    if resp.usage:
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
    return text.strip(), usage


def count_tokens(text: str, model_hint: str = "gpt-4o") -> int:
    """Rough token count using tiktoken (cl100k base for GPT-4 family)."""
    try:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model_hint)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text or ""))
    except Exception:
        # Fallback: approximate 4 chars per token
        return max(1, len(text) // 4)
