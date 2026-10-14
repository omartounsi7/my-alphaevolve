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

Runs also need Docker, installed and running (see "How programs are run").
Without Docker, the tests that need it are skipped.

## Choosing the LLM

The LLM is reached through the "OpenAI-compatible" interface, which is offered
both by [Ollama](https://ollama.com), for models running on your own machine,
and by most cloud providers. Three options select it:

| Option | Meaning | Default |
|---|---|---|
| `--model` | Name of the model, as its server knows it. Required. | none |
| `--llm-url` | Address of the server | `http://localhost:11434/v1`, a local Ollama |
| `--api-key-env` | Name of the environment variable holding your API key | `OPENAI_API_KEY` |

### A local model with Ollama

Install Ollama, download a model once, and name it with `--model`. No API key
is needed, and running costs nothing.

```bash
ollama pull qwen2.5-coder:3b
```

```powershell
.venv\Scripts\python.exe scripts\run.py examples\function_minimization\initial_program.py examples\function_minimization\evaluation.py --model qwen2.5-coder:3b
```

Ollama cuts prompts that are longer than its context length without warning.
The prompts of this project are short today; if you make them longer, raise
that limit in Ollama's settings.

### A model in the cloud

Give the provider's address and model name, and put your API key in an
environment variable. The key is a secret: never write it in a file of this
repository or on the command line.

```powershell
# Windows (PowerShell): set the key for this terminal window only
$env:OPENAI_API_KEY = "paste-your-key-here"
.venv\Scripts\python.exe scripts\run.py examples\function_minimization\initial_program.py examples\function_minimization\evaluation.py --model NAME-OF-THE-MODEL --llm-url https://ADDRESS-OF-THE-PROVIDER/v1
```

```bash
# Linux and macOS
export OPENAI_API_KEY="paste-your-key-here"
.venv/bin/python scripts/run.py examples/function_minimization/initial_program.py examples/function_minimization/evaluation.py --model NAME-OF-THE-MODEL --llm-url https://ADDRESS-OF-THE-PROVIDER/v1
```

Cloud models cost money for every request. Each iteration is one request, so
`--iterations` bounds the cost of a run, and `--max-reply-tokens` (4096 by
default, 0 for no limit) bounds the length of each reply. Set a spending limit
with your provider as well.

### When the LLM does not answer

A request that fails for a passing reason is tried again twice. If it still
fails, that iteration is skipped. After three skipped iterations in a row the
run stops, keeping what it has found.

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

## How programs are run

Programs written by an LLM cannot be trusted, so by default each one runs in its
own [Docker](https://www.docker.com) container, created for that program and
removed afterwards. Inside it, the program:

- has **no network**;
- can only **write** in a temporary folder that disappears with the container;
- sees only the `my_alphaevolve` package and the problem's folder, both **read-only**;
- runs as a user **without any rights**;
- has at most **1 GB of memory**, one CPU and 64 processes;
- is **stopped after `--timeout` seconds** (30 by default), together with every
  process it started.

A program that breaks any of these rules fails, and the run carries on.

Docker must be installed and running: Docker Desktop on Windows and macOS, or
Docker Engine on Linux. On first use, the run builds the image the containers
start from (`src/my_alphaevolve/evaluation.Dockerfile`), which downloads Python's
official image once. Starting a container costs about one second per program.

There is no way to run programs outside a container: a run stops at once if
Docker is not available.

The evaluation file is loaded again for every program, so slow work at the top
of that file is repeated each time.

## How parents are chosen

Each iteration improves one existing program, the parent. The database picks it
with one of two strategies, chosen at random each time:

- **Exploitation, 70% of the time**: a random program among the 10 best. This
  refines what already works.
- **Exploration, 30% of the time**: a random program among all those that work,
  good or bad. This gives less successful ideas a chance to lead somewhere.

Programs whose evaluation failed are kept in the database and in the saved run,
but are never chosen as parents.

The choices are random and differ from run to run. Add `--seed` with a whole
number, for example `--seed 7`, to get the same choices again. This repeats the
choice of parents only: an LLM rarely gives the same reply twice, so two runs
with the same seed still drift apart.

## Saving, stopping and continuing a run

Add `--output` with a folder name to save a run. The folder then holds:

| File | Contents |
|---|---|
| `programs.jsonl` | Every program of the run, one per line: its id, parent, generation, the iteration it was made in, its score and its code |
| `best_program.py` | The code of the best program found so far, replaced whenever a better one appears |

Each program is written the moment it has been evaluated, so:

- **To stop a run**, press Ctrl+C. Every finished iteration is already saved.
- **To continue it**, launch the same command with the same `--output` folder.
  `--iterations` then means that many *more* iterations. The initial program is
  not evaluated again.

Use a new folder when the problem changes: scores saved for one problem mean
nothing for another, and the program cannot tell the difference.

The best program at any earlier point of the run can be read from
`programs.jsonl`: it is the highest score among the lines whose `iteration` is
not above that point.

## Everyday commands

These are written for Windows. On Linux and macOS, replace
`.venv\Scripts\python.exe` with `.venv/bin/python` and every `\` with `/`.
The run commands use a local Ollama model; see "Choosing the LLM" for others.

```powershell
# Run the program on the example problem (10 iterations by default)
.venv\Scripts\python.exe scripts\run.py examples\function_minimization\initial_program.py examples\function_minimization\evaluation.py --model qwen2.5-coder:3b

# The same, choosing the number of iterations
.venv\Scripts\python.exe scripts\run.py examples\function_minimization\initial_program.py examples\function_minimization\evaluation.py --model qwen2.5-coder:3b --iterations 50

# The same, saved in a folder; launch it again to continue the run for 50 more iterations
.venv\Scripts\python.exe scripts\run.py examples\function_minimization\initial_program.py examples\function_minimization\evaluation.py --model qwen2.5-coder:3b --iterations 50 --output runs\function_minimization

# The same, stopping any program that runs for more than 5 seconds
.venv\Scripts\python.exe scripts\run.py examples\function_minimization\initial_program.py examples\function_minimization\evaluation.py --model qwen2.5-coder:3b --timeout 5

# Run the tests
.venv\Scripts\python.exe -m unittest discover tests

# Check the types
.venv\Scripts\python.exe -m mypy

# Check for common mistakes and style problems
.venv\Scripts\python.exe -m ruff check

# Reformat the code automatically
.venv\Scripts\python.exe -m ruff format
```
