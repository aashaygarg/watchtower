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

### The morning routine

`watchtower morning` loads a local **startup workspace** and prints a founder
dashboard: goals, hypotheses, a research briefing, and prioritized
recommendations.

```bash
uv run watchtower morning            # uses ./startup
uv run watchtower morning -p path/to/startup
```

### Initialize your own workspace

A workspace is a directory (default `startup/`) describing your startup's
current understanding of itself. Watchtower ships a starter workspace in
[`startup/`](startup) already populated for **Health OS**, where each file
contains one clearly marked `EXAMPLE` entry and `TODO(founder)` placeholders.

To make it yours:

1. **Edit `vision.md`.** The first `#` heading becomes the startup name and the
   first paragraph becomes the mission. Replace the `TODO(founder)` text.
2. **Fill in the YAML files.** Replace each `EXAMPLE` entry with your real
   content. Every file documents its own schema in comments at the top.
3. **Run it:** `uv run watchtower morning`.

| File | Holds | Required |
|------|-------|----------|
| `vision.md` | Startup name + mission (narrative) | Yes |
| `goals.yaml` | Outcomes you are trying to reach | No |
| `strategies.yaml` | Approaches for reaching goals | No |
| `hypotheses.yaml` | Testable beliefs your strategies rely on | No |
| `experiments.yaml` | Tests that validate hypotheses | No |
| `decisions.yaml` | Record of choices made | No |

Only `vision.md` is required. Every YAML file is optional and empty-safe: a
missing or empty file simply contributes nothing, so you can start with just a
vision and grow the workspace over time. To start from scratch, either delete a
file, empty it, or replace its list with `[]` (for example, `goals: []`).

### Enabling live research

Research is powered by **GPT-Researcher**, which is an optional dependency. By
default it is not installed and the research step degrades gracefully to a
clearly-labeled placeholder, so `watchtower morning` always works. To enable
live research:

```bash
uv sync --extra research      # install GPT-Researcher
# set the API keys GPT-Researcher needs (e.g. OPENAI_API_KEY, TAVILY_API_KEY) in .env
```

With the extra installed and keys configured, `GPTResearchService` builds a
query from your `vision.md`, `goals.yaml`, `strategies.yaml`, and
`hypotheses.yaml`, and returns structured findings (new evidence, competitor
updates, scientific papers, market changes, and a confidence score).

The decision step is still an LLM-free placeholder, wired behind an injectable
interface so it can later be replaced by LangGraph nodes. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the full design.



## Development

```bash
uv run ruff check .      # lint
uv run ruff format .     # format
uv run pytest            # tests
```
