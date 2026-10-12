# my-alphaevolve

A minimal, from-scratch implementation of the AlphaEvolve algorithm: an
evolutionary loop in which an LLM proposes changes to a program, an evaluator
scores the result, and a database keeps the programs to build on next.

## Layout

| Path | Contents |
|---|---|
| `src/my_alphaevolve/` | The algorithm's code (`Program`, `Database`, `Evaluator`, `Problem`, the loop) |
| `examples/` | Ready-made problems, one folder each |
| `scripts/` | Files you launch directly |
| `tests/` | Automatic checks |
| `pyproject.toml` | Project description and tool settings |

## Setup

Run once, from the repository root.

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Linux and macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## Defining a problem

As in AlphaEvolve, you describe a problem with two Python files:

- **An initial solution**: the program that evolution starts from.
- **The evaluation criteria**: a file defining `evaluate(namespace)`. It receives
  a dictionary of every name a candidate program defined, and returns that
  program's score as a number (higher is better). It should raise an error if
  the program breaks the problem's rules.

See `examples/function_minimization/` for a complete example.

## Everyday commands

These are written for Windows. On Linux and macOS, replace
`.venv\Scripts\python.exe` with `.venv/bin/python` and every `\` with `/`.

```powershell
# Run the program on the example problem
.venv\Scripts\python.exe scripts\run.py examples\function_minimization\initial_program.py examples\function_minimization\evaluation.py

# Run the tests
.venv\Scripts\python.exe -m unittest discover tests

# Check the types
.venv\Scripts\python.exe -m mypy

# Check for common mistakes and style problems
.venv\Scripts\python.exe -m ruff check

# Reformat the code automatically
.venv\Scripts\python.exe -m ruff format
```
