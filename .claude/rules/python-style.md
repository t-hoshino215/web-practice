---
paths:
  - "**/*.py"
---

# Python Coding Style

> TThis file extends [code-style.md](./code-style.md) for Python projects.

## Basic Principles

- Follow **PEP 8**
- Use **type annotations** on all function signatures

## Immutability

Prefer immutable data structures:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    name: str
    email: str

from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float
```

## Documentation & Comments

- Always use Google-style docstrings for functions and classes
- Module-level docstrings are also required
- Write comments for code blocks ranging from a few lines to several dozen lines, explaining why the code is necessary

## Package & Environment Management

- Use `uv`. (Do not use `pip` / `poetry` / `conda` / `virtualenv`)
- Use `pyproject.toml` as the single source of configuration (Do not use `setup.py` / `setup.cfg`)

## Formatting

- Use `ruff`. (Do not use `flake8` / `black` / `isort`)
- Configure `ruff` in `pyproject.toml`

## Type Hints

- Type hints are mandatory. Avoid using `Any` unless necessary, and provide a comment explaining why.
- Use Python 3.12+ syntax (e.g., `list[int]`, `str | None`). Do not use older syntax (e.g., `List[int]`, `Optional[str]`).
- Use `mypy` for type checking.
- Configure `mypy` in `pyproject.toml`.

## Commands

- Create environment: `uv venv`
- Add package: `uv add <pkg>`
- Add development dependency: `uv add --dev <pkg>`
- Sync (from lockfile): `uv sync`
- Run script: `uv run python ...`
- Run tests: `uv run pytest ...`
- Lint: `uv run ruff check ...`
- Format: `uv run ruff format ...`
- Type check: `uv run mypy ...`
