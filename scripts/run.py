"""Entry point: run this file to start my-alphaevolve on a problem.

Usage:
    python scripts/run.py INITIAL_PROGRAM EVALUATION_FILE
"""

import argparse
from pathlib import Path

from my_alphaevolve.loop import run_my_alphaevolve
from my_alphaevolve.problem import load_problem


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
    run_my_alphaevolve(problem)


# Only run main() when this file is launched directly, not when it is imported
if __name__ == "__main__":
    main()
