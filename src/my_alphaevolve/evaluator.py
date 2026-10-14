"""The Evaluator classes: run a program and measure how good it is.

- ProcessEvaluator runs each program in a separate process with a time limit.
  Use it for code written by an LLM.
- InProcessEvaluator runs programs in the current process. Only for trusted code, as in the tests.
"""

import io
import math
import multiprocessing
import sys
from abc import ABC, abstractmethod
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

from my_alphaevolve.problem import ScoreFunction, load_score_function
from my_alphaevolve.program import Program

# How long one program may run, in seconds.
DEFAULT_TIMEOUT_SECONDS = 30.0

# The longest failure message kept, in characters.
MAX_MESSAGE_LENGTH = 2000


def score_program(code: str, score_function: ScoreFunction) -> float:
    """Run a program's code in this process and return its score (higher is better)."""
    namespace: dict[str, Any] = {}
    exec(code, namespace)
    score: Any = score_function(namespace)
    if isinstance(score, bool) or not isinstance(score, int | float):
        raise ValueError(f"the score must be a number, got {type(score).__name__}")
    if not math.isfinite(score):
        raise ValueError(f"the score must be a finite number, got {score}")
    return float(score)


def describe_error(error: Exception) -> str:
    """Return a short text saying what went wrong, such as "ZeroDivisionError: division by zero"."""
    message = f"{type(error).__name__}: {error}"
    return message[:MAX_MESSAGE_LENGTH]


class Evaluator(ABC):
    """What every evaluator must be able to do: turn a program into a score."""

    def __init__(self) -> None:
        # The score of programs that fail: worse than any real score.
        self.failure_score: float = float("-inf")

    @abstractmethod
    def execute(self, program: Program) -> float:
        """Run the program's code and return its score (higher is better)."""


class InProcessEvaluator(Evaluator):
    """Runs programs inside the current Python process.

    Only for trusted code: there is no time limit and no separation, so an
    infinite loop hangs everything and a program can disturb the rest of the run.
    """

    def __init__(self, score_function: ScoreFunction) -> None:
        super().__init__()
        # Turns a program's namespace into a score.
        self.score_function: ScoreFunction = score_function

    def execute(self, program: Program) -> float:
        """Run the program's code and return its score (higher is better).

        A program that crashes, breaks the problem's rules, or is given a score
        that is not a finite number gets failure_score.
        """
        try:
            return score_program(program.code, self.score_function)
        except Exception as error:
            # The program crashed or misbehaved.
            print(f"Evaluation failed: {describe_error(error)}")
            return self.failure_score


def _evaluate_in_child(code: str, evaluation_path: str, connection: Connection) -> None:
    """Score one program and send back ("ok", score) or ("error", message)."""
    # Use UTF-8 like the parent.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    try:
        score_function = load_score_function(Path(evaluation_path))
        connection.send(("ok", score_program(code, score_function)))
    except Exception as error:
        connection.send(("error", describe_error(error)))


class ProcessEvaluator(Evaluator):
    """Runs each program in a separate Python process, with a time limit.

    A program that loops forever is stopped when its time is up, and one that
    crashes or exits only ends its own process. Nothing a program does to
    Python's state reaches the main process or the next program.

    This is NOT a security barrier: the program still runs with the user's
    permissions and can read and write files.
    """

    def __init__(
        self,
        evaluation_path: Path,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Prepare an evaluator for the problem scored by the given evaluation file."""
        super().__init__()
        if timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be above 0, got {timeout_seconds}")
        # The user's file defining evaluate; each child loads it itself.
        self.evaluation_path: Path = evaluation_path
        # How long one program may run before it is stopped.
        self.timeout_seconds: float = timeout_seconds
        # "spawn" starts every child as a fresh Python on every operating system.
        self._context = multiprocessing.get_context("spawn")

    def execute(self, program: Program) -> float:
        """Run the program's code in a child process and return its score.

        A program that crashes, breaks the problem's rules, is given an invalid
        score, runs too long or ends its process gets failure_score.
        """
        parent_end, child_end = self._context.Pipe(duplex=False)
        child = self._context.Process(
            target=_evaluate_in_child,
            args=(program.code, str(self.evaluation_path), child_end),
        )
        child.start()
        # Close the parent's copy of the child's end, so a silent child death raises EOFError.
        child_end.close()
        try:
            if not parent_end.poll(self.timeout_seconds):
                print(f"Evaluation failed: no answer after {self.timeout_seconds} seconds")
                return self.failure_score
            status, value = parent_end.recv()
        except EOFError:
            # The child ended without sending anything, e.g. the program called sys.exit().
            print("Evaluation failed: the program stopped without giving an answer")
            return self.failure_score
        finally:
            # Always clean up.
            if child.is_alive():
                child.kill()
            child.join()
            parent_end.close()

        if status == "error":
            print(f"Evaluation failed: {value}")
            return self.failure_score
        return float(value)
