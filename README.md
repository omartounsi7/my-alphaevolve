# my-alphaevolve

A minimal, from-scratch implementation of the AlphaEvolve algorithm: an
evolutionary loop in which an LLM proposes changes to a program, an evaluator
scores the result, and a database keeps the programs to build on next.

## Layout

| Path | Contents |
|---|---|
| `src/my_alphaevolve/` | The algorithm's code (`Program`, `Database`, `Evaluator`, `Problem`, `PromptSampler`, `LLM`, the loop) |
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

### The initial solution must describe the problem

The initial solution **must start with a docstring that describes the problem**.
That docstring is copied into every prompt, and it is the only explanation of the
task the LLM ever receives. The run stops with an error if it is missing.

A good description says:

- what the program must define (function name, arguments, return value);
- which rules the answer must respect;
- how the score is computed, and that higher is better.

```python
"""Problem: make answer as large as possible without exceeding 100.

Define a variable called answer holding a number. The score is answer itself,
or a failure if answer is above 100. A higher score is better.
"""

answer = 1
```

The description is read once, from the initial solution. Later programs written
by the LLM do not need to keep the docstring.

## Example: function minimization

`examples/function_minimization/` asks for a program that finds the lowest point
of a function of one or several variables. It has three files:

| File | Contents |
|---|---|
| `initial_program.py` | The problem description and a deliberately poor first `search` |
| `evaluation.py` | `evaluate`, which calls the program's `search` and scores its answer |
| `target.py` | The function to minimize and the region to search |

Programs do not know the function in advance. `search` receives it as an
argument, together with the bounds, and has to explore it by calling it:

```python
def search(target_function, lower_bounds, upper_bounds):
    ...
    return point
```

A point is **always a list of numbers**, one per variable, and the bounds are
lists of the same length. A function of one variable is no exception: its points
are lists holding a single number, such as `[0.5]`.

So the example works for any function of any number of variables. To minimize a
different one, edit `target_function`, `LOWER_BOUNDS` and `UPPER_BOUNDS` in
`target.py`; nothing else needs to change. The number of variables is the length
of the two bounds lists.

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
