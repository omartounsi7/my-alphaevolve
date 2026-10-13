"""Entry point: run this file to start my-alphaevolve on a problem.

Usage:
    python scripts/run.py INITIAL_PROGRAM EVALUATION_FILE [--iterations N] [--output FOLDER]
"""

import argparse
import io
import sys
from pathlib import Path

from my_alphaevolve.llm import FakeLLM
from my_alphaevolve.loop import run_my_alphaevolve
from my_alphaevolve.problem import load_problem

# How many iterations a run lasts when --iterations is not given
DEFAULT_ITERATIONS = 10

# Temporary: a prepared reply for the function-minimization example, written the
# way the prompt asks: only code, with the explanation in comments.
# It only makes sense for that example and goes away when a real LLM is connected.
FAKE_REPLY = """\
import random


def search(target_function, lower_bounds, upper_bounds):
    # Improvement: instead of one fixed guess, try many random points and keep the lowest
    generator = random.Random(0)
    points = [
        [generator.uniform(low, high) for low, high in zip(lower_bounds, upper_bounds)]
        for _ in range(2000)
    ]
    return min(points, key=target_function)
"""


def use_utf8_for_output() -> None:
    """Make print() able to show any character, whatever the system's default is.

    On Windows, output that is redirected to a file or to another program uses
    an old encoding that lacks many characters. Printing one of them, such as an
    arrow in a comment written by the LLM, would stop the run with an error.
    UTF-8 is an encoding that can represent every character.
    """
    for stream in (sys.stdout, sys.stderr):
        # Only ordinary text output can be switched; anything else is left alone
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


def main() -> None:
    """Read the two file paths from the command line and start the search."""
    use_utf8_for_output()
    # Describes the arguments this script accepts; also provides --help for free
    parser = argparse.ArgumentParser(description="Evolve a program with my-alphaevolve.")
    parser.add_argument(
        "initial_program",
        type=Path,
        help="path to the Python file holding the initial solution",
    )
    parser.add_argument(
        "evaluation_file",
        type=Path,
        help="path to the Python file defining evaluate(namespace) -> score",
    )
    # Starting with "--" makes this one optional: it has a default and is given by name
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"how many new programs to ask the LLM for (default: {DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "folder where the run is saved; if it already holds a saved run, "
            "that run is continued (default: the run is not saved)"
        ),
    )
    # The values the user typed, available as args.initial_program, args.evaluation_file,
    # args.iterations and args.output
    args = parser.parse_args()
    if args.iterations < 0:
        # parser.error prints the usage message with this explanation, then stops
        parser.error("--iterations must be 0 or more")

    problem = load_problem(args.initial_program, args.evaluation_file)
    # Temporary: a fake LLM with one prepared reply, until a real one is connected
    llm = FakeLLM([FAKE_REPLY])
    database = run_my_alphaevolve(problem, llm, args.iterations, args.output)

    # Show the result of the run: the best program found and its code
    best_program = database.get_best_program()
    if best_program is not None:
        print(f"Best program: {best_program}\n{best_program.code}")


# Only run main() when this file is launched directly, not when it is imported
if __name__ == "__main__":
    main()
