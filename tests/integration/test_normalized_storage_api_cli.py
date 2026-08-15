from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from apps.orchestrator import cli
from apps.orchestrator.main import app
from packages.normalized_storage import NormalizedImportStore


ROOT = Path(__file__).parents[1]


def test_normalized_store_imports_and_is_idempotent(tmp_path: Path) -> None:
    store = NormalizedImportStore(tmp_path / "normalized.sqlite3")
    fixture = ROOT / "fixtures" / "private_brain_generic.json"

    first = store.import_path(fixture)
    second = store.import_path(fixture)
    conversations = store.list_conversations()

    assert first.status == "completed"
    assert first.imported_conversations == 1
    assert second.skipped_duplicates == 1
    assert len(conversations) == 1


def test_message_order_is_preserved(tmp_path: Path) -> None:
    store = NormalizedImportStore(tmp_path / "normalized.sqlite3")
    fixture = ROOT / "fixtures" / "private_brain_generic.json"
    job = store.import_path(fixture)
    conversation_id = store.list_conversations()[0]["conversation_id"]
    conversation = store.get_conversation(conversation_id)

    assert job.imported_messages == 2
    assert conversation is not None
    assert [message["position"] for message in conversation["messages"]] == [1, 2]
    assert conversation["messages"][0]["content"].startswith("We should build")


def test_malformed_import_records_failure_without_rows(tmp_path: Path) -> None:
    store = NormalizedImportStore(tmp_path / "normalized.sqlite3")
    job = store.import_path(ROOT / "fixtures" / "private_brain_malformed.json")

    assert job.status == "failed"
    assert job.failures
    assert store.list_conversations() == []


@pytest.mark.anyio
async def test_orchestrator_read_only_api(monkeypatch, tmp_path: Path) -> None:
    import apps.orchestrator.main as orchestrator_main

    orchestrator_main.normalized_store = NormalizedImportStore(tmp_path / "api.sqlite3")
    fixture = ROOT / "fixtures" / "private_brain_generic.json"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/imports", json={"path": str(fixture), "provider": "generic_json"})
        assert response.status_code == 200
        conversations = (await client.get("/conversations")).json()
        assert len(conversations) == 1
        detail = (await client.get(f"/conversations/{conversations[0]['conversation_id']}")).json()
        assert len(detail["messages"]) == 2


def test_cli_import_and_list(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MEMORYOS_NORMALIZED_DB", str(tmp_path / "cli.sqlite3"))
    runner = CliRunner()
    fixture = ROOT / "fixtures" / "private_brain_generic.json"

    result = runner.invoke(cli.app, ["import", str(fixture), "--provider", "generic_json"])
    assert result.exit_code == 0, result.output

    list_result = runner.invoke(cli.app, ["conversations", "list"])
    assert list_result.exit_code == 0
    assert "Synthetic project planning" in list_result.output
