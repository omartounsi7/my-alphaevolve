"""Stand-ins used by the tests in place of the real building blocks."""

import contextlib
import io

from my_alphaevolve.evaluator import Evaluator, describe_error, score_program
from my_alphaevolve.problem import ScoreFunction
from my_alphaevolve.program import Program


class InProcessEvaluator(Evaluator):
    """Scores programs inside the test process: fast, but only for the tests' own programs.

    No time limit and no isolation, so real runs always use DockerEvaluator.
    """

    def __init__(self, score_function: ScoreFunction) -> None:
        super().__init__()
        self.score_function: ScoreFunction = score_function

    def execute(self, program: Program) -> float:
        """Return the program's score, or failure_score if it fails."""
        try:
            return score_program(program.code, self.score_function)
        except Exception as error:
            print(f"Evaluation failed: {describe_error(error)}")
            return self.failure_score


def execute_quietly(evaluator: Evaluator, code: str) -> float:
    """Evaluate a piece of code without showing the failure messages printed."""
    with contextlib.redirect_stdout(io.StringIO()):
        return evaluator.execute(Program(code))
