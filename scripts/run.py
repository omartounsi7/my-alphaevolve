"""Entry point: run this file to start my-alphaevolve on a problem.

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

# How many iterations a run lasts when --iterations is not given
DEFAULT_ITERATIONS = 10

# The environment variable the API key is read from when --api-key-env is not given
DEFAULT_API_KEY_VARIABLE = "OPENAI_API_KEY"


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
    """Read the settings of the run from the command line and start the search."""
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
    # Starting with "--" means the argument is given by name. required=True makes
    # it compulsory all the same: there is no sensible default model.
    parser.add_argument(
        "--model",
        required=True,
        help="name of the LLM to use, as its server knows it",
    )
    # The arguments below are optional: each has a default
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
            "longest reply asked of the LLM, in tokens; 0 for no limit "
            f"(default: {DEFAULT_MAX_REPLY_TOKENS})"
        ),
    )
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
            "whole number that fixes the random choice of parents, so that it can be "
            "repeated (default: different choices every run)"
        ),
    )
    # The values the user typed, available as args.model, args.llm_url and so on
    # (a dash in the name of an argument becomes an underscore)
    args = parser.parse_args()
    if args.iterations < 0:
        # parser.error prints the usage message with this explanation, then stops
        parser.error("--iterations must be 0 or more")
    if args.timeout <= 0:
        parser.error("--timeout must be above 0")
    if args.max_reply_tokens < 0:
        parser.error("--max-reply-tokens must be 0 or more")

    problem = load_problem(args.initial_program, args.evaluation_file)

    # The API key is a secret, so it is read from the environment and never typed
    # on the command line, where it would be visible and remembered. os.environ.get
    # gives None when the variable is not set, which suits a local server.
    api_key = os.environ.get(args.api_key_env)
    llm = OpenAICompatibleLLM(
        model=args.model,
        base_url=args.llm_url,
        api_key=api_key,
        # 0 on the command line means "no limit", which the class expresses as None
        max_reply_tokens=args.max_reply_tokens or None,
    )
    print(f"LLM: {args.model} at {args.llm_url}")

    # Each program is scored in its own process, so a bad one cannot hang or end the run.
    # resolve() makes the path absolute, so it stays valid inside those processes.
    evaluator = ProcessEvaluator(args.evaluation_file.resolve(), args.timeout)
    database = run_my_alphaevolve(problem, llm, evaluator, args.iterations, args.output, args.seed)

    # Show the result of the run: the best program found and its code
    best_program = database.get_best_program()
    if best_program is not None:
        print(f"Best program: {best_program}\n{best_program.code}")


# Only run main() when this file is launched directly, not when it is imported
if __name__ == "__main__":
    main()
