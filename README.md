# Watchtower

Watchtower is a **local-first AI Founder Operating System** delivered as an
internal CLI. It is **not** a SaaS product — it runs on your machine and is
driven from the terminal.

> Status: scaffolding only. No business logic is implemented yet.

## Tech stack

- **Python 3.13**
- **[uv](https://docs.astral.sh/uv/)** for dependency management
- **[LangGraph](https://langchain-ai.github.io/langgraph/)** for agent orchestration
- **OpenAI-compatible LLM interface** (`watchtower/llm.py`)
- **[Typer](https://typer.tiangolo.com/)** for the CLI
- **[Rich](https://rich.readthedocs.io/)** for terminal output
- **YAML** configuration
- **[Ruff](https://docs.astral.sh/ruff/)** for linting and formatting
- **[pytest](https://docs.pytest.org/)** for tests
- **python-dotenv** for environment loading

## Project layout

```
watchtower/
    agents/      # Agent definitions
    graphs/      # LangGraph graph definitions
    prompts/     # Prompt templates
    memory/      # Persistence and memory
    startup/     # Startup domain models and workflows
    tools/       # Tools callable by agents
    cli/         # Typer CLI
    config.py    # YAML + env configuration loading
    llm.py       # OpenAI-compatible client factory
tests/           # Test suite
pyproject.toml   # Project + tooling configuration
watchtower.yaml  # Default configuration
```

## Getting started

Install dependencies (creates a `.venv` and resolves the dependency groups):

```bash
uv sync
```

Copy the environment template and add your credentials:

```bash
cp .env.example .env
```

## Usage

```bash
uv run watchtower version
uv run watchtower --help
```

## Development

```bash
uv run ruff check .      # lint
uv run ruff format .     # format
uv run pytest            # tests
```
