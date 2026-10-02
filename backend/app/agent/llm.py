"""Provider client for any OpenAI-compatible chat endpoint (Ollama locally, Voyager via config).

- Disables Qwen3 "thinking" with `reasoning_effort="none"` (falls back if the provider rejects it)
  and strips any `<think>...</think>` block regardless.
- `chat_json` asks for JSON-schema structured output, falling back to `json_object` mode and
  then to plain text with the schema in the prompt.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI, BadRequestError, UnprocessableEntityError

from app.config import get_settings

log = logging.getLogger(__name__)

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


# Per-endpoint capability flags learned at runtime (e.g. a provider rejecting reasoning_effort).
_CAPS: dict[str, dict[str, bool]] = {}


class LLMError(Exception):
    pass


def strip_think(text: str) -> str:
    text = THINK_RE.sub("", text or "")
    if "</think>" in text:  # unterminated opening tag stripped by the server
        text = text.split("</think>", 1)[1]
    return text.strip()


def extract_json(text: str) -> Any:
    t = FENCE_RE.sub("", strip_think(text)).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start = min([i for i in (t.find("{"), t.find("[")) if i >= 0], default=-1)
    end = max(t.rfind("}"), t.rfind("]"))
    if start >= 0 and end > start:
        try:
            return json.loads(t[start : end + 1])
        except json.JSONDecodeError as e:
            raise LLMError(f"Model did not return valid JSON: {e}") from e
    raise LLMError("Model did not return JSON")


class LLMClient:
    def __init__(self, base_url: str | None = None, model: str | None = None, api_key: str | None = None, timeout: float = 180):
        s = get_settings()
        self.base_url = base_url or s.llm_base_url
        self.model = model or s.llm_model
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=api_key or s.llm_api_key or "none", timeout=timeout, max_retries=0)
        self._caps = _CAPS.setdefault(self.base_url, {"reasoning_effort": True, "json_schema": True})

    async def _create(self, messages: list[dict], **kw) -> str:
        if self._caps["reasoning_effort"]:
            try:
                r = await self.client.chat.completions.create(model=self.model, messages=messages, reasoning_effort="none", **kw)
                return strip_think(r.choices[0].message.content or "")
            except (BadRequestError, UnprocessableEntityError) as e:
                if "reasoning" not in str(e).lower():
                    raise
                self._caps["reasoning_effort"] = False
        r = await self.client.chat.completions.create(model=self.model, messages=messages, **kw)
        return strip_think(r.choices[0].message.content or "")

    async def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 800) -> str:
        try:
            return await self._create(messages, temperature=temperature, max_tokens=max_tokens)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"LLM request failed: {e}") from e

    async def chat_json(self, messages: list[dict], schema: dict, name: str = "result", temperature: float = 0.1, max_tokens: int = 3000) -> Any:
        try:
            if self._caps["json_schema"]:
                try:
                    text = await self._create(
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema}},
                    )
                    return extract_json(text)
                except (BadRequestError, UnprocessableEntityError) as e:
                    log.info("json_schema response_format unsupported, falling back: %s", e)
                    self._caps["json_schema"] = False
            hinted = list(messages)
            hinted.append({"role": "system", "content": "Respond with ONLY a JSON object matching this JSON schema:\n" + json.dumps(schema)})
            try:
                text = await self._create(hinted, temperature=temperature, max_tokens=max_tokens, response_format={"type": "json_object"})
            except (BadRequestError, UnprocessableEntityError):
                text = await self._create(hinted, temperature=temperature, max_tokens=max_tokens)
            return extract_json(text)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"LLM request failed: {e}") from e

    async def health(self) -> tuple[bool, str | None]:
        try:
            models = await self.client.models.list()
            ids = [m.id for m in models.data]
            if ids and self.model not in ids:
                return False, f"Model '{self.model}' not available (have: {', '.join(ids[:10])})"
            return True, None
        except Exception as e:
            return False, str(e)[:300]


def get_llm() -> LLMClient:
    """A fresh client per call: the async HTTP pool is bound to the running event loop."""
    return LLMClient()
