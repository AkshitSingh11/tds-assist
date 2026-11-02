"""Minimal OpenRouter chat client with an on-disk response cache.

The cache serves two purposes: free-tier rate limits (re-runs cost nothing), and
reproducibility (anyone can re-run the evaluation offline and get the same outputs).
"""

import hashlib
import http.client
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Protocol

URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMUnavailable(Exception):
    pass


class _Retryable(Exception):
    pass


class LLM(Protocol):
    model: str

    def complete(self, messages: list[dict]) -> str: ...


class OpenRouterLLM:
    def __init__(self, model: str, api_key: str | None, cache_dir: Path,
                 opener: Callable = urllib.request.urlopen, sleep: Callable[[float], None] = time.sleep,
                 attempts: int = 3, timeout: float = 120):
        self.model = model
        self._key = api_key
        self._cache = Path(cache_dir)
        self._open = opener
        self._sleep = sleep
        self._attempts = attempts
        self._timeout = timeout

    def cache_key(self, messages: list[dict]) -> str:
        blob = json.dumps({"model": self.model, "messages": messages}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    def complete(self, messages: list[dict]) -> str:
        key = self.cache_key(messages)
        path = self._cache / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["response"]
        if not self._key:
            raise LLMUnavailable("No OPENROUTER_API_KEY and no cached response for this prompt")

        body = json.dumps({"model": self.model, "messages": messages, "temperature": 0}).encode()
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
                   "X-Title": "tds-assist prototype"}
        last = None
        for attempt in range(self._attempts):
            try:
                req = urllib.request.Request(URL, data=body, headers=headers, method="POST")
                payload = json.loads(self._open(req, timeout=self._timeout).read())
                if "error" in payload:
                    err = payload["error"]
                    code = err.get("code") if isinstance(err, dict) else None
                    if code == 429 or (isinstance(code, int) and code >= 500):
                        raise _Retryable(f"OpenRouter error: {err}")  # upstream overload, sent with HTTP 200
                    raise LLMUnavailable(f"OpenRouter error: {err}")
                text = payload["choices"][0]["message"]["content"] or ""
                if not isinstance(text, str):
                    raise TypeError(f"message content is {type(text).__name__}, not text")
                break
            except urllib.error.HTTPError as e:
                last = e
                if e.code != 429 and e.code < 500:
                    raise LLMUnavailable(f"HTTP {e.code}: {e.reason}") from e
            except (_Retryable, OSError, http.client.HTTPException, ValueError, TypeError, KeyError, IndexError) as e:
                last = e  # network failure, truncated or non-JSON body, unexpected payload shape
            if attempt < self._attempts - 1:
                self._sleep(10 * 2**attempt)
        else:
            raise LLMUnavailable(f"Gave up after {self._attempts} attempts: {last}")

        if not text.strip():
            return text  # an empty reply is a provider hiccup, not an answer worth replaying
        self._cache.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"model": self.model, "messages": messages, "response": text},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        return text
