"""This file is the entry point of the codebase. Run it to start my-alphaevolve on a problem.

Usage:
    python scripts/run.py INITIAL_PROGRAM EVALUATION_FILE --model MODEL
        [--llm-url URL] [--api-key-env VARIABLE] [--max-reply-tokens N]
        [--iterations N] [--output FOLDER] [--timeout SECONDS] [--seed N]
"""

import argparse
import io
import os
import sys
from pathlib import Path

from my_alphaevolve.evaluator import DEFAULT_TIMEOUT_SECONDS, ProcessEvaluator
from my_alphaevolve.llm import DEFAULT_LLM_URL, DEFAULT_MAX_REPLY_TOKENS, OpenAICompatibleLLM
from my_alphaevolve.loop import run_my_alphaevolve
from my_alphaevolve.problem import load_problem

DEFAULT_ITERATIONS = 10
DEFAULT_API_KEY_VARIABLE = "OPENAI_API_KEY"


def main() -> None:
    """Read the settings of the run and start the search."""
    # Use UTF-8 encoding so that print() is able to show any character.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")

    # Parse arguments.
    parser = argparse.ArgumentParser(description="Evolve a program with my-alphaevolve.")
    parser.add_argument(
        "initial_program",
        type=Path,
        help="path to the Python file containing the initial solution",
    )
    parser.add_argument(
        "evaluation_file",
        type=Path,
        help="path to the Python file defining the evaluator function",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="name of the LLM to use",
    )
    parser.add_argument(
        "--llm-url",
        default=DEFAULT_LLM_URL,
        help=(
            "address of the OpenAI-compatible server that runs the LLM "
            f"(default: a local Ollama server, {DEFAULT_LLM_URL})"
        ),
    )
    parser.add_argument(
        "--api-key-env",
        default=DEFAULT_API_KEY_VARIABLE,
        help=(
            "name of the environment variable holding the API key; it may be "
            f"unset for a local server (default: {DEFAULT_API_KEY_VARIABLE})"
        ),
    )
    parser.add_argument(
        "--max-reply-tokens",
        type=int,
        default=DEFAULT_MAX_REPLY_TOKENS,
        help=(
            "longest reply asked of the LLM in tokens; 0 for no limit "
            f"(default: {DEFAULT_MAX_REPLY_TOKENS})"
        ),
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"how many programs the LLM should generate (default: {DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "folder where the results of the run are saved; if it already holds a saved run, "
            "that run is continued"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            "how many seconds one program may run before it is stopped "
            f"(default: {DEFAULT_TIMEOUT_SECONDS})"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "number that determines the randomness of each run, fix it so that runs can be repeated"
        ),
    )

    args = parser.parse_args()
    if args.iterations < 0:
        parser.error("--iterations must be 0 or more")
    if args.timeout <= 0:
        parser.error("--timeout must be above 0")
    if args.max_reply_tokens < 0:
        parser.error("--max-reply-tokens must be 0 or more")

    # Load the problem.
    problem = load_problem(args.initial_program, args.evaluation_file)

    # Get the LLM.
    api_key = os.environ.get(args.api_key_env)
    llm = OpenAICompatibleLLM(
        model=args.model,
        base_url=args.llm_url,
        api_key=api_key,
        max_reply_tokens=args.max_reply_tokens or None,
    )
    print(f"LLM: {args.model} at {args.llm_url}")

    # Load the evaluator.
    evaluator = ProcessEvaluator(args.evaluation_file.resolve(), args.timeout)

    # Run the loop and collect the final database.
    database = run_my_alphaevolve(problem, llm, evaluator, args.iterations, args.output, args.seed)

    # Print the best program found.
    best_program = database.get_best_program()
    if best_program is not None:
        print(f"Best program: {best_program}\n{best_program.code}")


if __name__ == "__main__":
    main()
