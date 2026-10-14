"""The Problem class: what the user wants solved, in a form the algorithm can use.

The user supplies two things, each as a Python file:

- an initial solution: the program that evolution starts from. It must begin
  with a docstring describing the problem;
- the evaluation criteria: a file defining a function called evaluate, which
  receives every name a candidate program defined as a dictionary and returns
  that program's score (a number, higher is better).

Next to the evaluation file, an optional requirements.txt lists the packages
programs may import besides Python's standard library.
"""

import ast
import re
import runpy
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# The type of function that scores a program: it receives the namespace
# of the program (a dictionary) and returns that program's score (a number)
ScoreFunction = Callable[[dict[str, Any]], float]

# The name of the function the user's evaluation file must define
EVALUATE_FUNCTION_NAME = "evaluate"

# The file, next to the evaluation file, listing the packages programs may import.
REQUIREMENTS_FILE_NAME = "requirements.txt"


def read_description(initial_code: str) -> str:
    """Return the problem description: the docstring at the top of the initial program."""
    try:
        parsed_code = ast.parse(initial_code)
    except SyntaxError as error:
        raise ValueError(f"The initial program is not valid Python: {error}") from error
    description = ast.get_docstring(parsed_code)
    if not description:
        raise ValueError(
            "The initial program must start with a docstring that describes the problem."
        )
    return description


def read_requirements(folder: Path) -> list[str]:
    """Return the requirements listed in the folder's requirements.txt, such as "numpy==2.5.4".

    Blank lines and comments are left out; no file means no requirements.
    Raises ValueError for a pip option such as "--index-url": only packages may be listed.
    """
    path = folder / REQUIREMENTS_FILE_NAME
    if not path.is_file():
        return []
    requirements = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        requirement = line.split("#", 1)[0].strip()
        if not requirement:
            continue
        if requirement.startswith("-"):
            raise ValueError(f"{path} may only list packages, not options such as {requirement!r}")
        requirements.append(requirement)
    return requirements


def package_name(requirement: str) -> str:
    """Return the package's name in a requirement: "numpy" for "numpy==2.5.4"."""
    return re.split(r"[\s\[<>=!~;@]", requirement, maxsplit=1)[0]


class Problem:
    """One problem to solve: an initial solution plus the file that scores solutions."""

    def __init__(
        self,
        initial_code: str,
        evaluation_path: Path | None = None,
        packages: list[str] | None = None,
    ) -> None:
        """Store the user's inputs."""
        # The source code of the starting program.
        self.initial_code: str = initial_code
        # The user's file defining the evaluate function.
        self.evaluation_path: Path | None = evaluation_path
        # What the problem is, in plain words. Shown to the LLM in every prompt
        self.description: str = read_description(initial_code)
        # The packages programs may import besides the standard library.
        self.packages: list[str] = list(packages or [])


def load_score_function(evaluation_path: Path) -> ScoreFunction:
    """Run the user's evaluation file and return the evaluate function it defines."""
    if not evaluation_path.is_file():
        raise FileNotFoundError(f"no such file: {evaluation_path}")

    evaluation_folder = evaluation_path.resolve().parent
    # Remember the modules imported so far, to spot the new ones afterwards.
    names_imported_before = set(sys.modules)
    # Let the evaluation file import helper files that sit next to it.
    sys.path.insert(0, str(evaluation_folder))
    try:
        # Run the file; the result is a dictionary of the names it defines.
        evaluation_names = runpy.run_path(str(evaluation_path))
    finally:
        sys.path.remove(str(evaluation_folder))
        # Forget the helpers the file imported.
        for name in set(sys.modules) - names_imported_before:
            module_file = getattr(sys.modules[name], "__file__", None)
            if module_file and Path(module_file).resolve().is_relative_to(evaluation_folder):
                del sys.modules[name]
    score_function = evaluation_names.get(EVALUATE_FUNCTION_NAME)
    if not callable(score_function):
        raise ValueError(
            f"{evaluation_path} must define a function called {EVALUATE_FUNCTION_NAME}"
        )
    checked_function: ScoreFunction = score_function
    return checked_function


def load_problem(initial_program_path: Path, evaluation_path: Path) -> Problem:
    """Build a Problem object using the initial program and evaluation files the user provides."""
    # Check both files up front.
    for path in (initial_program_path, evaluation_path):
        if not path.is_file():
            raise FileNotFoundError(f"no such file: {path}")

    # Read the initial program
    initial_code = initial_program_path.read_text(encoding="utf-8-sig")

    # Load the score function.
    load_score_function(evaluation_path)

    # Read the packages programs may import.
    requirements = read_requirements(evaluation_path.resolve().parent)
    packages = [package_name(requirement) for requirement in requirements]

    # Return the Problem.
    return Problem(initial_code, evaluation_path.resolve(), packages)
