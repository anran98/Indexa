"""CLI commands for Indexa."""

import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from indexa.config.settings import Settings
from indexa.config.sources import load_sources
from indexa.indexing.indexer import Indexer
from indexa.indexing.store import IndexStore

console = Console()


@click.group()
def main():
    """Indexa - MCP server for documentation search."""
    pass


@main.command()
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["openai", "local", "auto"]),
    default="auto",
    help="Embedding provider (default: auto)",
)
@click.option("--model", "-m", default=None, help="Override embedding model")
def index(provider: str, model: str | None):
    """Build the search index from configured sources."""
    from indexa.retrieval import HybridSearchEngine, get_embedding_provider

    settings = Settings()

    if provider == "auto":
        if os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
            console.print("[dim]Using OpenAI embeddings[/dim]")
        else:
            provider = "local"
            console.print("[dim]Using local embeddings[/dim]")

    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]Error:[/red] OPENAI_API_KEY not set.")
        console.print("Use --provider local for offline indexing.")
        sys.exit(1)

    try:
        sources = load_sources(settings.sources_path)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Config not found: {settings.sources_path}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/red] Invalid config: {e}")
        sys.exit(1)

    console.print(f"[bold]Indexing {len(sources)} source(s)...[/bold]\n")

    indexer = Indexer()
    all_chunks = []

    for source in sources:
        console.print(f"  [cyan]{source.name}[/cyan] ({source.root})")
        try:
            chunks = indexer.index_source(source)
            all_chunks.extend(chunks)
            console.print(f"    [green]OK[/green] {len(chunks)} chunks")
        except Exception as e:
            console.print(f"    [red]FAIL[/red] {e}")

    if not all_chunks:
        console.print("[yellow]No chunks to index.[/yellow]")
        sys.exit(1)

    store = IndexStore(settings.index_path)
    store.save(all_chunks)

    console.print(f"\n[bold]Building search index...[/bold]")

    try:
        embedding_provider = get_embedding_provider(provider=provider, model=model)
        console.print(f"  Model: {embedding_provider.model_name}")

        data_dir = settings.index_path.parent
        search_engine = HybridSearchEngine(
            data_dir=data_dir,
            embedding_provider=embedding_provider,
        )

        search_engine.index(all_chunks, show_progress=True)
        stats = search_engine.get_stats()
        console.print(f"  BM25: {stats['bm25']['actual_count']} docs")
        console.print(f"  Vectors: {stats['vector']['vectors_count']}")
        search_engine.close()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    console.print(f"\n[bold green]Done![/bold green] {len(all_chunks)} chunks indexed")


@main.command()
@click.argument("query")
@click.option("--top-k", "-k", default=5, help="Number of results")
@click.option("--source", "-s", default=None, help="Filter by source ID")
def search(query: str, top_k: int, source: str | None):
    """Search the index."""
    from indexa.retrieval import HybridSearchEngine

    settings = Settings()
    store = IndexStore(settings.index_path)

    if not store.exists():
        console.print("[red]Index not found.[/red] Run: indexa index")
        sys.exit(1)

    chunks = store.load()
    data_dir = settings.index_path.parent

    try:
        search_engine = HybridSearchEngine(data_dir=data_dir, provider_name="local")
        search_engine.load_chunks(chunks)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if not search_engine.exists():
        console.print("[yellow]Search index not built.[/yellow] Run: indexa index")
        sys.exit(1)

    results = search_engine.search(query, source_id=source, top_k=top_k)
    search_engine.close()

    if not results:
        console.print("[yellow]No results.[/yellow]")
        return

    table = Table(title=f"Results for '{query}'")
    table.add_column("Score", style="cyan", width=7)
    table.add_column("Title", style="bold", max_width=35)
    table.add_column("Path", max_width=40)

    for r in results:
        path = r.chunk.path
        if r.chunk.anchor:
            path += f"#{r.chunk.anchor}"
        table.add_row(
            f"{r.score:.3f}",
            r.chunk.title[:33] + ".." if len(r.chunk.title) > 35 else r.chunk.title,
            path[:38] + ".." if len(path) > 40 else path,
        )

    console.print(table)


@main.command()
def status():
    """Show index status."""
    from indexa.retrieval import HybridSearchEngine

    settings = Settings()
    store = IndexStore(settings.index_path)
    metadata = store.get_metadata()

    if not metadata.get("exists"):
        console.print("[yellow]No index.[/yellow] Run: indexa index")
        return

    console.print("[bold]Index Status[/bold]\n")
    console.print(f"  Chunks: {metadata.get('chunk_count', 0)}")
    console.print(f"  Indexed: {metadata.get('indexed_at', 'unknown')}")

    chunks = store.load()
    source_counts: dict[str, int] = {}
    for chunk in chunks:
        source_counts[chunk.source_id] = source_counts.get(chunk.source_id, 0) + 1

    if source_counts:
        console.print("\n[bold]By source:[/bold]")
        for source_id, count in sorted(source_counts.items()):
            console.print(f"  {source_id}: {count}")

    data_dir = settings.index_path.parent
    try:
        search_engine = HybridSearchEngine(data_dir=data_dir, provider_name="local")
        if search_engine.exists():
            stats = search_engine.get_stats()
            console.print("\n[bold]Search index:[/bold]")
            console.print(f"  BM25: {stats['bm25'].get('actual_count', 0)} docs")
            vector_count = stats['vector'].get('points_count', 0) or stats['vector'].get('vectors_count', 0)
            console.print(f"  Vectors: {vector_count}")
        search_engine.close()
    except Exception:
        pass


@main.command()
def sources():
    """List configured sources."""
    settings = Settings()

    try:
        sources_list = load_sources(settings.sources_path)
    except FileNotFoundError:
        console.print(f"[red]Config not found:[/red] {settings.sources_path}")
        sys.exit(1)

    table = Table(title="Sources")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Adapters", style="magenta")
    table.add_column("Root")

    for source in sources_list:
        adapters = [ac.type for ac in source.adapter_configs] if source.adapter_configs else ["markdown"]
        table.add_row(source.id, source.name, ", ".join(adapters), str(source.root))

    console.print(table)


@main.command("install-cursor")
@click.option("--workspace", "-w", default=".", help="Workspace path")
def install_cursor(workspace: str):
    """Install Indexa to Cursor MCP config."""
    workspace_path = Path(workspace).resolve()
    cursor_dir = workspace_path / ".cursor"
    cursor_dir.mkdir(exist_ok=True)

    mcp_config_path = cursor_dir / "mcp.json"

    if mcp_config_path.exists():
        config = json.loads(mcp_config_path.read_text())
    else:
        config = {"mcpServers": {}}

    indexa_root = Settings().project_root

    config["mcpServers"]["indexa"] = {
        "command": sys.executable,
        "args": ["-m", "indexa.server"],
        "cwd": str(indexa_root),
    }

    mcp_config_path.write_text(json.dumps(config, indent=2))

    console.print(f"[green]OK[/green] Installed to {mcp_config_path}")
    console.print("\nNext: indexa index && restart Cursor")


if __name__ == "__main__":
    main()
