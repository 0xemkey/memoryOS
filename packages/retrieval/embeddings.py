from __future__ import annotations

import requests


class OllamaUnavailableError(RuntimeError):
    pass


class OllamaEmbeddingClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "nomic-embed-text", timeout: float = 5):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, text: str) -> list[float]:
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding")
        except Exception as exc:
            raise OllamaUnavailableError("Ollama embeddings unavailable; using keyword-only retrieval") from exc
        if not isinstance(embedding, list) or not all(isinstance(item, (int, float)) for item in embedding):
            raise OllamaUnavailableError("Ollama returned an invalid embedding response")
        return [float(item) for item in embedding]


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    length = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(length))
