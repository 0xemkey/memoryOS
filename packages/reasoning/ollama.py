from __future__ import annotations

import requests


class OllamaReasoningUnavailable(RuntimeError):
    pass


class OllamaChatClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llama3.1",
        timeout: float = 30,
        context_limit: int = 4096,
        output_limit: int = 512,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.context_limit = context_limit
        self.output_limit = output_limit
        self.last_payload: dict | None = None

    def chat(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": self.context_limit, "num_predict": self.output_limit},
        }
        self.last_payload = payload
        try:
            response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            content = (data.get("message") or {}).get("content")
        except Exception as exc:
            raise OllamaReasoningUnavailable("Ollama reasoning unavailable; deterministic fallback used") from exc
        if not isinstance(content, str):
            raise OllamaReasoningUnavailable("Ollama returned an invalid chat response")
        return content
