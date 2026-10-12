# my-alphaevolve

A minimal, from-scratch implementation of the AlphaEvolve algorithm: an
evolutionary loop in which an LLM proposes changes to a program, an evaluator
scores the result, and a database keeps the programs to build on next.

## Layout

| Path | Contents |
|---|---|
| `src/my_alphaevolve/` | The algorithm's code (`Program`, `Database`, the loop) |
| `scripts/` | Files you launch directly |
| `tests/` | Automatic checks |
| `pyproject.toml` | Project description and tool settings |

## Setup

Run once, from the repository root (Windows PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Everyday commands

```powershell
# Run the program
.venv\Scripts\python.exe scripts\run.py

# Run the tests
.venv\Scripts\python.exe -m unittest discover tests

# Check the types
.venv\Scripts\python.exe -m mypy

# Check for common mistakes and style problems
.venv\Scripts\python.exe -m ruff check

# Reformat the code automatically
.venv\Scripts\python.exe -m ruff format
```
