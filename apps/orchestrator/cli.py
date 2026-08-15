from __future__ import annotations

from pathlib import Path

import typer

from packages.normalized_storage import NormalizedImportStore
from packages.normalized_storage.config import normalized_db_path

app = typer.Typer(help="MemoryOS Private Brain CLI")
imports_app = typer.Typer(help="Import job commands")
conversations_app = typer.Typer(help="Conversation commands")
app.add_typer(imports_app, name="imports")
app.add_typer(conversations_app, name="conversations")


def store() -> NormalizedImportStore:
    return NormalizedImportStore(normalized_db_path())


@app.command("import")
def import_command(path: Path, provider: str = "auto") -> None:
    job = store().import_path(path, provider)
    typer.echo(job.model_dump_json(indent=2))
    if job.status == "failed":
        raise typer.Exit(code=1)


@imports_app.command("list")
def list_imports() -> None:
    typer.echo([job.model_dump(mode="json") for job in store().list_imports()])


@conversations_app.command("list")
def list_conversations() -> None:
    typer.echo(store().list_conversations())


@conversations_app.command("show")
def show_conversation(conversation_id: str) -> None:
    conversation = store().get_conversation(conversation_id)
    if conversation is None:
        typer.echo(f"Conversation not found: {conversation_id}", err=True)
        raise typer.Exit(code=1)
    typer.echo(conversation)
