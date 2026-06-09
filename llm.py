from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LLMResult:
    ok: bool
    text: str
    error: str = ""


class OllamaClient:
    """Small Ollama-compatible local LLM client.

    Works with locally downloaded models such as qwen, gemma, llama, mistral, etc.
    The app never sends data to a cloud service unless the user changes the base URL.
    """

    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434", timeout: int = 120):
        self.model = (model or "qwen2.5:7b").strip()
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.timeout = timeout

    def generate(self, prompt: str, system: str = "", temperature: float = 0.2, max_chars: int = 20000) -> LLMResult:
        if not prompt.strip():
            return LLMResult(False, "", "Empty prompt")
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt[:max_chars],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data.get("response", "").strip()
            if not text:
                return LLMResult(False, "", "Ollama returned an empty response")
            return LLMResult(True, text)
        except urllib.error.URLError as exc:
            return LLMResult(False, "", f"Could not connect to local Ollama at {self.base_url}: {exc}")
        except Exception as exc:
            return LLMResult(False, "", f"Local LLM call failed: {exc}")

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False


def strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|html|markdown|md)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()
