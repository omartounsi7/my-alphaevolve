"""The Problem class: what the user wants solved, in a form the algorithm can use.

As in AlphaEvolve, the user supplies two things, each as a Python file:

- an initial solution: the program that evolution starts from. It must begin
  with a docstring describing the problem, because that text is what tells
  the LLM what it is being asked to improve;
- the evaluation criteria: a file defining a function called evaluate, which
  receives every name a candidate program defined (a dictionary) and returns
  that program's score (a number, higher is better).

Nothing in this file is specific to any one problem.
"""

import ast
import runpy
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# The kind of function that scores a program: it receives the names the program
# defined (a dictionary) and returns that program's score (a number)
ScoreFunction = Callable[[dict[str, Any]], float]

# The name of the function the user's evaluation file must define
EVALUATE_FUNCTION_NAME = "evaluate"


def read_description(initial_code: str) -> str:
    """Return the problem description: the docstring at the top of the initial program.

    Raises ValueError if the code is not valid Python or has no such docstring.
    """
    try:
        # ast.parse reads code into a structure Python can inspect, without running it
        parsed_code = ast.parse(initial_code)
    except SyntaxError as error:
        raise ValueError(f"The initial program is not valid Python: {error}") from error
    # The text of the docstring that opens the file, or None if there is none
    description = ast.get_docstring(parsed_code)
    if not description:
        raise ValueError(
            "The initial program must start with a docstring that describes the problem."
        )
    return description


class Problem:
    """One problem to solve: an initial solution plus a way to score solutions."""

    def __init__(self, initial_code: str, score_function: ScoreFunction) -> None:
        """Store the user's inputs.

        Raises ValueError if initial_code does not start with a docstring
        describing the problem.
        """
        # The source code of the starting program, as text
        self.initial_code: str = initial_code
        # The user's function that turns a finished run of a program into a score
        self.score_function: ScoreFunction = score_function
        # What the problem is, in plain words; shown to the LLM in every prompt
        self.description: str = read_description(initial_code)


def load_problem(initial_program_path: Path, evaluation_path: Path) -> Problem:
    """Build a Problem from the two files the user provides.

    Raises FileNotFoundError if a file is missing, and ValueError if the
    evaluation file does not define a function called evaluate or the initial
    program does not start with a docstring describing the problem.
    """
    # Check both files up front, so a wrong path gives a clear message
    for path in (initial_program_path, evaluation_path):
        if not path.is_file():
            raise FileNotFoundError(f"no such file: {path}")

    # The initial program is only read, not run: programs travel as text.
    # "utf-8-sig" is UTF-8 that also drops the invisible marker (BOM) which
    # some Windows editors put at the start of a file and Python cannot run
    initial_code = initial_program_path.read_text(encoding="utf-8-sig")

    # The folder of the evaluation file, as an absolute path
    evaluation_folder = str(evaluation_path.resolve().parent)
    # Let the evaluation file import helper files that sit next to it:
    # sys.path is the list of folders Python searches when it sees "import"
    sys.path.insert(0, evaluation_folder)
    try:
        # Run the evaluation file and collect every name it defines in a dictionary
        evaluation_names = runpy.run_path(str(evaluation_path))
    finally:
        # Put the search list back as it was, whether or not the file ran cleanly
        sys.path.remove(evaluation_folder)
    # None if the file does not define the required function
    score_function = evaluation_names.get(EVALUATE_FUNCTION_NAME)
    if not callable(score_function):
        raise ValueError(
            f"{evaluation_path} must define a function called {EVALUATE_FUNCTION_NAME}"
        )

    return Problem(initial_code, score_function)
