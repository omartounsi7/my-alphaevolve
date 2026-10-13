"""The Evaluator classes: run a program and measure how good it is.

There are two of them, offering the same execute method:

- ProcessEvaluator runs each program in a separate Python process with a time
  limit. This is the one to use for code written by an LLM.
- InProcessEvaluator runs programs inside the current process. It is fast and
  simple, but only suitable for code that is trusted, as in the tests.
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

# How long one program may run, in seconds, when no other limit is given
DEFAULT_TIMEOUT_SECONDS = 30.0

# The longest failure message kept, in characters; the rest is cut off
MAX_MESSAGE_LENGTH = 2000


def score_program(code: str, score_function: ScoreFunction) -> float:
    """Run a program's code in this process and return its score (higher is better).

    Raises an error if the code crashes, breaks the problem's rules, or is
    given a score that is not a finite number.
    """
    # An empty dictionary that will collect every name the code defines
    namespace: dict[str, Any] = {}
    # Run the code; its functions and variables end up in namespace
    exec(code, namespace)
    # Let the problem decide how good the result is
    score: Any = score_function(namespace)
    # The score function is written by the user, so its result is checked too:
    # it must be a number (bool does not count) and neither nan nor infinite
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
    """What every evaluator must be able to do: turn a program into a score.

    This class is only a description. The real work is done by the classes
    built on it, which all offer the same execute method.
    """

    def __init__(self) -> None:
        # The score given to programs that fail: worse than any real score
        self.failure_score: float = float("-inf")

    @abstractmethod
    def execute(self, program: Program) -> float:
        """Run the program's code and return its score (higher is better).

        A program that fails in any way gets failure_score.
        """


class InProcessEvaluator(Evaluator):
    """Runs programs inside the current Python process.

    Only for trusted code: there is no time limit and no separation, so an
    infinite loop hangs everything and a program can disturb the rest of the run.
    """

    def __init__(self, score_function: ScoreFunction) -> None:
        super().__init__()
        # The problem-specific function that turns a finished run into a score
        self.score_function: ScoreFunction = score_function

    def execute(self, program: Program) -> float:
        """Run the program's code and return its score (higher is better).

        A program that crashes, breaks the problem's rules, or is given a score
        that is not a finite number gets failure_score.
        """
        try:
            return score_program(program.code, self.score_function)
        except Exception as error:
            # The code crashed or misbehaved: report it and give the worst score
            print(f"Evaluation failed: {describe_error(error)}")
            return self.failure_score


def _evaluate_in_child(code: str, evaluation_path: str, connection: Connection) -> None:
    """Score one program and send back the outcome; this is all a child process does.

    Sends ("ok", score) on success, or ("error", message) if the program fails.
    """
    # The parent prints in UTF-8, and the child writes to the same place, so it
    # must use UTF-8 too or a program printing an unusual character would fail
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    try:
        # The evaluate function cannot be sent from the parent, so it is loaded here
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
        """Prepare an evaluator for the problem scored by the given evaluation file.

        Raises ValueError if timeout_seconds is not above 0.
        """
        super().__init__()
        if timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be above 0, got {timeout_seconds}")
        # The user's file defining evaluate; each child process loads it itself
        self.evaluation_path: Path = evaluation_path
        # How long one program may run before it is stopped
        self.timeout_seconds: float = timeout_seconds
        # "spawn" starts every child as a brand new Python, on every operating system
        self._context = multiprocessing.get_context("spawn")

    def execute(self, program: Program) -> float:
        """Run the program's code in a child process and return its score.

        A program that crashes, breaks the problem's rules, is given an invalid
        score, runs too long or ends its process gets failure_score.
        """
        # A one-way pipe: the child writes its outcome, the parent reads it
        parent_end, child_end = self._context.Pipe(duplex=False)
        # A second Python process that will run the program
        child = self._context.Process(
            target=_evaluate_in_child,
            args=(program.code, str(self.evaluation_path), child_end),
        )
        child.start()
        # The parent does not write, so it closes its copy of the child's end.
        # That lets it notice when the child has gone without sending anything.
        child_end.close()
        try:
            # Wait for an outcome, but never longer than the time limit
            if not parent_end.poll(self.timeout_seconds):
                print(f"Evaluation failed: no answer after {self.timeout_seconds} seconds")
                return self.failure_score
            status, value = parent_end.recv()
        except EOFError:
            # The child ended without sending anything, e.g. the program called sys.exit()
            print("Evaluation failed: the program stopped without giving an answer")
            return self.failure_score
        finally:
            # Always clean up, whatever happened: stop the child if it is still running
            if child.is_alive():
                child.kill()
            child.join()
            parent_end.close()

        if status == "error":
            print(f"Evaluation failed: {value}")
            return self.failure_score
        return float(value)
