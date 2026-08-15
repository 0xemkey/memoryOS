from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2]
FORBIDDEN_REASONING_IMPORTS = {
    "packages.vault_crypto",
    "packages.privacy_detection",
    "packages.pseudonymization",
    "apps.privacy_vault",
}


def test_reasoning_boundary_has_no_forbidden_imports() -> None:
    roots = [ROOT / "apps" / "reasoning_service", ROOT / "packages" / "reasoning"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports = {alias.name for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports = {node.module}
                else:
                    continue
                forbidden = imports & FORBIDDEN_REASONING_IMPORTS
                assert not forbidden, f"{path} imports forbidden modules: {forbidden}"
