"""Entry point: run this file to start my-alphaevolve on a problem.

Usage:
    python scripts/run.py INITIAL_PROGRAM EVALUATION_FILE
"""

import argparse
from pathlib import Path

from my_alphaevolve.llm import FakeLLM
from my_alphaevolve.loop import run_my_alphaevolve
from my_alphaevolve.problem import load_problem

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


def main() -> None:
    """Read the two file paths from the command line and start the search."""
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
    # The values the user typed, available as args.initial_program and args.evaluation_file
    args = parser.parse_args()

    problem = load_problem(args.initial_program, args.evaluation_file)
    # Temporary: a fake LLM with one prepared reply, until a real one is connected
    llm = FakeLLM([FAKE_REPLY])
    run_my_alphaevolve(problem, llm)


# Only run main() when this file is launched directly, not when it is imported
if __name__ == "__main__":
    main()
