"""The Evaluator class: runs a program and measures how good it is."""

from collections.abc import Callable
from typing import Any

from my_alphaevolve.program import Program

# The kind of function an Evaluator needs: it receives the names a program
# defined (a dictionary) and returns that program's score (a number)
ScoreFunction = Callable[[dict[str, Any]], float]


class Evaluator:
    """Runs a program's code and measures how good it is.

    Known limitations, acceptable only while the programs are trusted:
    the code runs inside this Python process with no time limit and no
    isolation, so an infinite loop hangs the run and harmful code is not blocked.
    """

    def __init__(self, score_function: ScoreFunction) -> None:
        # The problem-specific function that turns a finished run into a score
        self.score_function: ScoreFunction = score_function
        # The score given to programs that fail: worse than any real score
        self.failure_score: float = float("-inf")

    def execute(self, program: Program) -> float:
        """Run the program's code and return its score (higher is better).

        A program that crashes or breaks the problem's rules gets failure_score.
        """
        try:
            # An empty dictionary that will collect every name the code defines
            namespace: dict[str, Any] = {}
            # Run the code; its functions and variables end up in namespace
            exec(program.code, namespace)
            # Let the problem decide how good the result is
            return self.score_function(namespace)
        except Exception as error:
            # The code crashed or misbehaved: report it and give the worst score
            print(f"Evaluation failed: {error}")
            return self.failure_score