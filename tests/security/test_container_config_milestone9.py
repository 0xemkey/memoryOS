from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]


def compose() -> dict:
    return yaml.safe_load((ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8"))


def test_privacy_container_has_no_network_and_limited_mounts() -> None:
    service = compose()["services"]["privacy_vault"]

    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert "ALL" in service["cap_drop"]
    mounts = "\n".join(service["volumes"])
    assert "/data/vault" in mounts
    assert "/data/raw-imports" in mounts
    assert "ollama" not in str(service).lower()


def test_reasoning_container_has_no_vault_or_raw_mounts() -> None:
    service = compose()["services"]["reasoning_service"]
    mounts = "\n".join(service["volumes"])

    assert service["read_only"] is True
    assert "ALL" in service["cap_drop"]
    assert "vault" not in mounts.lower()
    assert "raw" not in mounts.lower()
    assert "/data/sanitized" in mounts


def test_orchestrator_has_no_vault_key_environment() -> None:
    service = compose()["services"]["orchestrator"]
    text = str(service).lower()

    assert "key" not in text
    assert "vault_db" not in text


def test_dockerfiles_use_non_root_users() -> None:
    for name in ["privacy", "reasoning", "orchestrator"]:
        text = (ROOT / "docker" / f"{name}.Dockerfile").read_text(encoding="utf-8")
        assert "USER memoryos" in text
