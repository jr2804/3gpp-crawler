# CLI Integration Pattern

**Date**: 2026-03-02\
**Feature**: Dependency Injection Refactoring Planning\
**Branch**: `001-di-refactoring-plan`\
**Status**: Draft

## Overview

This document defines how the dependency injection system integrates with the CLI layer. The design maintains full backward compatibility while enabling optional container usage for improved testability.

## Current CLI Pattern

```python
# Current: Direct instantiation in each command
@app.command("query-tdocs")
def query_tdocs(
    agenda: str = typer.Option(..., help="Agenda pattern"),
    cache_dir: Path | None = typer.Option(None, "-c", "--cache-dir"),
    output: str = typer.Option("table", "-o", "--output"),
) -> None:
    # Instantiation happens here
    manager = CacheManager(cache_dir).register()
    with TDocDatabase(manager.db_file) as database:
        results = database.query_tdocs(TDocQueryConfig(agenda=agenda))
    
    # Output logic
    print_results(results, output)
```

## CLI Integration Approaches

### Approach 1: Optional Container Parameter

```python
from typing import Annotated

@app.command("query-tdocs")
def query_tdocs(
    agenda: str = typer.Option(..., help="Agenda pattern"),
    cache_dir: Path | None = typer.Option(None, "-c", "--cache-dir"),
    output: str = typer.Option("table", "-o", "--output"),
    use_container: bool = typer.Option(False, "--use-container", help="Use DI container"),
) -> None:
    """Query TDocs with optional DI container."""
    
    if use_container:
        # Use container
        container = ServiceContainer(cache_dir)
        with container.get_tdoc_db() as db:
            results = db.query_tdocs(TDocQueryConfig(agenda=agenda))
    else:
        # Original behavior
        manager = CacheManager(cache_dir).register()
        with TDocDatabase(manager.db_file) as db:
            results = db.query_tdocs(TDocQueryConfig(agenda=agenda))
    
    print_results(results, output)
```

### Approach 2: Internal Container Usage

```python
@app.command("query-tdocs")
def query_tdocs(
    agenda: str = typer.Option(..., help="Agenda pattern"),
    cache_dir: Path | None = typer.Option(None, "-c", "--cache-dir"),
    output: str = typer.Option("table", "-o", "--output"),
) -> None:
    """Query TDocs."""
    
    # Internally uses container but hidden from CLI surface
    results = _query_tdocs_internal(agenda, cache_dir)
    print_results(results, output)


def _query_tdocs_internal(agenda: str, cache_dir: Path | None):
    """Internal implementation uses container."""
    container = ServiceContainer(cache_dir)
    with container.get_tdoc_db() as db:
        return db.query_tdocs(TDocQueryConfig(agenda=agenda))
```

### Approach 3: Container Injection for Testing

```python
# Internal function accepts container for testing
def _query_tdocs(
    agenda: str,
    container: ServiceContainer | None = None,
) -> list[TDocMetadata]:
    """Query TDocs - accepts container for testing."""
    if container is None:
        container = ServiceContainer()
    
    with container.get_tdoc_db() as db:
        return db.query_tdocs(TDocQueryConfig(agenda=agenda))


@app.command("query-tdocs")
def query_tdocs(
    agenda: str = typer.Option(..., help="Agenda pattern"),
    output: str = typer.Option("table", "-o", "--output"),
) -> None:
    """Query TDocs."""
    results = _query_tdocs(agenda)
    print_results(results, output)


# Test can inject container
def test_query_tdocs():
    container = InMemoryServiceContainer()
    results = _query_tdocs("*test*", container=container)
    assert len(results) > 0
```

## CLI Command Template

```python
from typing import Annotated
import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command("command-name")
def command_name(
    # Options
    option1: str = typer.Option(..., help="Description"),
    option2: int = typer.Option(10, help="Description"),
    cache_dir: Path | None = typer.Option(None, "-c", "--cache-dir"),
    # Output
    output: str = typer.Option("table", "-o", "--output"),
) -> None:
    """Command description."""
    
    try:
        # Option 1: Use container
        # container = ServiceContainer(cache_dir)
        # with container.get_tdoc_db() as db:
        #     results = process(db, option1, option2)
        
        # Option 2: Keep existing pattern (default)
        manager = CacheManager(cache_dir).register()
        with TDocDatabase(manager.db_file) as db:
            results = process(db, option1, option2)
        
        # Output
        render_results(results, output, console)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def process(db, option1, option2):
    """Business logic - easily testable."""
    # ... logic
    return results
```

## Testing CLI Commands

### With Container-Based Tests

```python
def test_query_tdocs_with_container():
    """Test command using in-memory container."""
    # Create in-memory container
    container = InMemoryServiceContainer()
    
    # Populate test data
    db = container.tdoc_db()
    db.upsert_tdoc(TDocMetadata(id="R1-2400001", title="Test", ...))
    
    # Run command
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query-tdocs", "--agenda", "*test*", "--use-container"]
    )
    
    assert result.exit_code == 0
    assert "R1-2400001" in result.output
```

### Without Container (Existing Pattern)

```python
def test_query_tdocs_existing():
    """Test command using existing pattern."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query-tdocs", "--agenda", "*test*"]
    )
    
    # Should work exactly as before
    assert result.exit_code == 0
```

## Backward Compatibility

- All existing CLI commands work without changes
- Container is purely optional
- No new required parameters
- Existing test patterns remain valid

## Related Documents

- [ServiceContainer Interface](service-container.md)
- [Testability Approach](testability.md)
- [Backward Compatibility Strategy](backward-compatibility.md)
