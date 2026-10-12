"""The Evaluator class: runs a program and measures how good it is."""

import math
from typing import Any

from my_alphaevolve.problem import ScoreFunction
from my_alphaevolve.program import Program


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

        A program that crashes, breaks the problem's rules, or is given a score
        that is not a finite number gets failure_score.
        """
        try:
            # An empty dictionary that will collect every name the code defines
            namespace: dict[str, Any] = {}
            # Run the code; its functions and variables end up in namespace
            exec(program.code, namespace)
            # Let the problem decide how good the result is
            score: Any = self.score_function(namespace)
            # The score function is written by the user, so its result is checked too:
            # it must be a number (bool does not count) and neither nan nor infinite
            if isinstance(score, bool) or not isinstance(score, int | float):
                raise ValueError(f"the score must be a number, got {type(score).__name__}")
            if not math.isfinite(score):
                raise ValueError(f"the score must be a finite number, got {score}")
            return float(score)
        except Exception as error:
            # The code crashed or misbehaved: report it and give the worst score
            print(f"Evaluation failed: {error}")
            return self.failure_score
