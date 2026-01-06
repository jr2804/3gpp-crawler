set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Default command - list all available commands
default:
	@just --list

# Clean generated artefacts
clean:
    uv run ruff clean
    uv run python scripts/clean.py

# Lint the codebase
lint:
    uv run ruff format --check
    uv run ruff check --fix tests src
    uv run isort --check-only tests src
    uv run undersort --check tests src
    uv run ty check

# Lint the documentation
lint-md:
    uv run mdformat .\src
    uv run mdformat docs
    uv run mdformat AGENTS.md README.md
    uv run mdformat .claude/skills
    
# Format the codebase
format:
    uv run ruff format tests src
    uv run isort tests src
    uv run undersort tests src

# Build the project
build:
    @uv run scripts/remove_version.py
    uv build --clear --refresh .

