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
import time
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


def normalize_roles(messages: list[dict]) -> list[dict]:
    """Merge all system messages into one leading system message and merge consecutive turns
    of the same role, giving the strict sequence Cortex accepts: [system] user (assistant user)*."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system" and m.get("content"))
    out: list[dict] = [{"role": "system", "content": system}] if system else []
    for m in messages:
        if m["role"] == "system":
            continue
        if out and out[-1]["role"] == m["role"]:
            out[-1] = {"role": m["role"], "content": f"{out[-1]['content']}\n\n{m['content']}"}
        else:
            out.append({"role": m["role"], "content": m["content"]})
    if len(out) == (1 if system else 0) or out[-1]["role"] != "user":
        out.append({"role": "user", "content": "Continue."})
    return out


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 180,
        *,
        provider: str = "openai",
        default_headers: dict[str, str] | None = None,
        caps: dict[str, bool] | None = None,
    ):
        s = get_settings()
        self.base_url = base_url or s.llm_base_url
        self.model = model or s.llm_model
        self.provider = provider
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=api_key or s.llm_api_key or "none",
            timeout=timeout,
            max_retries=0,
            default_headers=default_headers,
        )
        self._caps = _CAPS.setdefault(self.base_url, {"reasoning_effort": True, "json_schema": True, **(caps or {})})

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    async def _create(self, messages: list[dict], **kw) -> str:
        if self.provider == "cortex":
            # Cortex's OpenAI-compatible API rejects the deprecated max_tokens parameter and
            # requires one leading system message followed by alternating user/assistant turns.
            if "max_tokens" in kw:
                kw["max_completion_tokens"] = kw.pop("max_tokens")
            messages = normalize_roles(messages)
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
        if self.provider == "cortex":  # Cortex has no model listing; a 1-token completion proves access
            try:
                await self._create([{"role": "user", "content": "ping"}], max_tokens=1)
                return True, None
            except Exception as e:
                return False, str(e)[:300]
        try:
            models = await self.client.models.list()
            ids = [m.id for m in models.data]
            if ids and self.model not in ids:
                return False, f"Model '{self.model}' not available (have: {', '.join(ids[:10])})"
            return True, None
        except Exception as e:
            return False, str(e)[:300]


# Primary endpoints that recently failed -> monotonic time of failure. While a provider is down
# (e.g. Cortex disabled on a trial account), calls go straight to the fallback instead of paying
# for a failing request each time; the primary is retried after PRIMARY_RETRY_AFTER_S.
_PRIMARY_DOWN: dict[str, float] = {}
PRIMARY_RETRY_AFTER_S = 300


class FallbackLLM:
    """Try the primary provider (Snowflake Cortex); on any LLM failure use the fallback (Ollama).

    `label` reports whichever provider produced the last answer, e.g. "cortex:llama3.3-70b".
    """

    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self.primary, self.fallback = primary, fallback
        self.model, self.base_url, self.provider = primary.model, primary.base_url, primary.provider
        self.label = primary.label

    async def _call(self, method: str, *args, **kwargs):
        down_since = _PRIMARY_DOWN.get(self.primary.base_url)
        if down_since is None or time.monotonic() - down_since > PRIMARY_RETRY_AFTER_S:
            try:
                result = await getattr(self.primary, method)(*args, **kwargs)
                _PRIMARY_DOWN.pop(self.primary.base_url, None)
                self.label = self.primary.label
                return result
            except LLMError as e:
                _PRIMARY_DOWN[self.primary.base_url] = time.monotonic()
                log.warning("%s failed (%s); falling back to %s", self.primary.label, str(e)[:200], self.fallback.label)
        result = await getattr(self.fallback, method)(*args, **kwargs)
        self.label = self.fallback.label
        return result

    async def chat(self, *args, **kwargs) -> str:
        return await self._call("chat", *args, **kwargs)

    async def chat_json(self, *args, **kwargs) -> Any:
        return await self._call("chat_json", *args, **kwargs)

    async def health(self) -> tuple[bool, str | None]:
        ok, err = await self.primary.health()
        if ok:
            return True, None
        fb_ok, fb_err = await self.fallback.health()
        note = f"{self.primary.label} unavailable ({err}); using fallback {self.fallback.label}"
        return fb_ok, note if fb_ok else f"{note}; fallback also failed: {fb_err}"


def cortex_llm(company_id: str) -> LLMClient | None:
    """LLM client for Snowflake Cortex (open-weight models) using the company's own Snowflake
    connection: its account host and PAT. Talks to Cortex's OpenAI-compatible REST API."""
    from app.snowflake import service as sf

    conn = sf.get_connection_row(company_id)
    if conn is None:
        return None
    s = get_settings()
    return LLMClient(
        base_url=f"https://{conn.account.lower()}.snowflakecomputing.com/api/v2/cortex/v1",
        model=s.cortex_model,
        api_key=sf.decrypt_token(conn.token_encrypted),
        provider="cortex",
        default_headers={"X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN"},
        # Cortex rejects OpenAI's reasoning_effort; structured output is probed at runtime.
        caps={"reasoning_effort": False},
    )


def get_llm(company_id: str | None = None) -> LLMClient | FallbackLLM:
    """A fresh client per call: the async HTTP pool is bound to the running event loop.

    LLM_PROVIDER=cortex runs on Snowflake Cortex inside the company's Snowflake account, falling
    back to the OpenAI-compatible endpoint (local Ollama) when Cortex is unavailable and
    LLM_FALLBACK is on. Otherwise the OpenAI-compatible endpoint is used directly.
    """
    s = get_settings()
    default = LLMClient(provider="ollama" if "11434" in s.llm_base_url else "openai")
    if s.llm_provider == "cortex" and company_id:
        cortex = cortex_llm(company_id)
        if cortex is not None:
            return FallbackLLM(cortex, default) if s.llm_fallback else cortex
    return default
