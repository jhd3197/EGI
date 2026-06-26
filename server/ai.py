"""Multi-provider, local-first AI base class (adapted from CalorIA's BaseResearcher).

Local-first per plan §3: the default provider is **Ollama** (no API key, runs on
the operator's machine); OpenAI is an opt-in fallback. Nothing here keeps a
response history or phones home — AI is optional and must degrade gracefully to
``None`` when no provider is reachable, so callers can always fall back to manual
entry.

Config (env):
  AI_PROVIDER   "ollama" (default) | "openai"
  AI_MODEL      model name; defaults to a sensible per-provider model
  OLLAMA_HOST   default "http://localhost:11434"
  OPENAI_API_KEY / OPENAI_BASE_URL   standard OpenAI vars
"""

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Optional

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class BaseExtractor:
    """Query an LLM and parse robust JSON out of its (often messy) reply.

    Usage:
        ex = BaseExtractor()
        if ex.available():
            data = ex.extract("Return JSON with fields ...")
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None,
                 timeout: float = 60.0):
        self.provider = (provider or os.getenv("AI_PROVIDER", "ollama")).lower()
        self.timeout = timeout
        if model:
            self.model = model
        elif self.provider == "openai":
            self.model = os.getenv("AI_MODEL", DEFAULT_OPENAI_MODEL)
        else:
            self.model = os.getenv("AI_MODEL", DEFAULT_OLLAMA_MODEL)

    # -- availability ------------------------------------------------------

    def available(self) -> bool:
        """Cheap check that the provider could be used. Never raises."""
        if self.provider == "openai":
            return bool(os.getenv("OPENAI_API_KEY"))
        if self.provider == "ollama":
            return self._ollama_reachable()
        return False

    def _ollama_reachable(self) -> bool:
        host = os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST).rstrip("/")
        try:
            req = urllib.request.Request(f"{host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3.0):
                return True
        except Exception:
            return False

    # -- query -------------------------------------------------------------

    def query(self, prompt: str) -> Optional[str]:
        """Send a prompt, return the raw model text, or None on any failure."""
        try:
            if self.provider == "openai":
                return self._query_openai(prompt)
            if self.provider == "ollama":
                return self._query_ollama(prompt)
        except Exception as exc:  # never let an AI hiccup break a request
            print(f"[ai] {self.provider} query failed: {exc}")
        return None

    def _query_ollama(self, prompt: str) -> Optional[str]:
        host = os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST).rstrip("/")
        body = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            # Ask Ollama to constrain output to JSON when the model supports it.
            "format": "json",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{host}/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("response")

    def _query_openai(self, prompt: str) -> Optional[str]:
        try:
            from openai import OpenAI
        except ImportError:
            print("[ai] openai package not installed; `pip install openai`")
            return None
        client = OpenAI()  # reads OPENAI_API_KEY / OPENAI_BASE_URL from env
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",
                 "content": "You extract structured data and reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content

    # -- parsing -----------------------------------------------------------

    def parse_json(self, text: Optional[str]) -> Optional[Any]:
        """Best-effort JSON extraction from a model reply.

        Handles, in order: None/empty, ``<think>...</think>`` reasoning blocks,
        ```json fenced code, leading/trailing prose around the JSON object, and
        trailing commas. Returns the parsed value or None.
        """
        if not text:
            return None
        cleaned = text.strip()

        # 1. Drop <think>...</think> reasoning blocks some local models emit.
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)

        # 2. Strip markdown code fences (```json ... ``` or ``` ... ```).
        fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            cleaned = fence.group(1).strip()

        # 3. Direct parse.
        candidate = cleaned
        for attempt in (candidate, self._slice_json(candidate)):
            if attempt is None:
                continue
            parsed = self._loads_lenient(attempt)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _slice_json(text: str) -> Optional[str]:
        """Slice from the first { or [ to its matching last } or ]."""
        starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
        if not starts:
            return None
        start = min(starts)
        end = max(text.rfind("}"), text.rfind("]"))
        if end <= start:
            return None
        return text[start:end + 1]

    @staticmethod
    def _loads_lenient(text: str) -> Optional[Any]:
        try:
            return json.loads(text)
        except Exception:
            pass
        # Remove trailing commas before } or ] and retry.
        repaired = re.sub(r",(\s*[}\]])", r"\1", text)
        try:
            return json.loads(repaired)
        except Exception:
            return None

    # -- convenience -------------------------------------------------------

    def extract(self, prompt: str) -> Optional[Any]:
        """query() + parse_json() in one call. Returns parsed JSON or None."""
        return self.parse_json(self.query(prompt))
