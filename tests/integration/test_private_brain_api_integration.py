from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from apps.orchestrator.private_brain import PrivateBrainConfig, PrivateBrainService
from packages.vault_crypto import StaticKeyProvider


ROOT = Path(__file__).parents[1]


@pytest.mark.anyio
async def test_private_brain_api_import_search_ask_and_reveal(monkeypatch, tmp_path: Path) -> None:
    import apps.api.memoryos_api.main as api_main

    config = PrivateBrainConfig(
        data_dir=tmp_path,
        normalized_db=tmp_path / "normalized.sqlite3",
        vault_db=tmp_path / "vault.sqlite3",
        sanitized_db=tmp_path / "sanitized.sqlite3",
        use_legacy_mvp=False,
        ollama_base_url="http://127.0.0.1:1",
        chat_model="offline-test",
        embedding_model="offline-embed",
    )
    api_main.private_brain = PrivateBrainService(config, StaticKeyProvider(b"x" * 32))
    monkeypatch.setenv("MEMORYOS_USE_LEGACY_MVP", "false")
    transport = httpx.ASGITransport(app=api_main.app)
    fixture = ROOT / "fixtures" / "private_brain_claude.json"

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        imported = await client.post("/imports", json={"path": str(fixture), "provider": "claude"})
        assert imported.status_code == 200, imported.text

        conversations = (await client.get("/conversations")).json()
        assert len(conversations) == 1

        search = (await client.post("/search", json={"query": "sanitized memory", "limit": 5})).json()
        assert search["results"]
        assert "Mehmet" not in str(search)
        assert "mehmet@example.com" not in str(search)

        ask = (await client.post("/ask", json={"query": "What should be stored?", "limit": 5})).json()
        assert ask["citations"]
        assert "Mehmet" not in ask["answer"]
        assert "mehmet@example.com" not in ask["answer"]

        token = api_main.private_brain.sanitized_store.list_chunks({})[0]["token_references_json"]
        assert "EMAIL" in token or "PROJECT" in token

        reveal = (
            await client.post(
                "/answers/reveal",
                json={"sanitized_answer": ask["answer"], "mode": "full"},
            )
        ).json()
        assert reveal["persisted"] is False


@pytest.mark.anyio
async def test_diagnostics_reports_private_brain_and_unverified_container(monkeypatch, tmp_path: Path) -> None:
    import apps.api.memoryos_api.main as api_main

    config = PrivateBrainConfig(
            data_dir=tmp_path,
            normalized_db=tmp_path / "normalized.sqlite3",
            vault_db=tmp_path / "vault.sqlite3",
            sanitized_db=tmp_path / "sanitized.sqlite3",
            use_legacy_mvp=False,
            ollama_base_url="http://127.0.0.1:1",
            chat_model="offline-test",
            embedding_model="offline-embed",
        )
    api_main.private_brain = PrivateBrainService(config, StaticKeyProvider(b"x" * 32))
    monkeypatch.setenv("MEMORYOS_USE_LEGACY_MVP", "false")
    transport = httpx.ASGITransport(app=api_main.app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        diagnostics = (await client.get("/diagnostics")).json()

    assert diagnostics["container_isolation"] == "UNVERIFIED"
    assert diagnostics["legacy_mvp_default"] is False
