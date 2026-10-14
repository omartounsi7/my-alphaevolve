"""Runs inside the evaluation container: scores the program read from standard input.

Usage: python -m my_alphaevolve.container_worker EVALUATION_FILE < program.py

The result is printed as the last line of standard output, in JSON:
{"status": "ok", "score": 1.5} or {"status": "error", "message": "..."}.
"""

import contextlib
import json
import sys
from pathlib import Path

from my_alphaevolve.evaluator import describe_error, score_program
from my_alphaevolve.problem import load_score_function


def main(arguments: list[str]) -> None:
    """Score the program on standard input with the given evaluation file."""
    code = sys.stdin.read()
    result: dict[str, object]
    try:
        # The program's prints go to standard error; standard output is kept for the result.
        with contextlib.redirect_stdout(sys.stderr):
            score_function = load_score_function(Path(arguments[0]))
            result = {"status": "ok", "score": score_program(code, score_function)}
    except Exception as error:
        result = {"status": "error", "message": describe_error(error)}
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
