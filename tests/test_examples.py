"""Checks that the example problems in the examples folder work with the Evaluator."""

import math
import unittest
from pathlib import Path

from my_alphaevolve.evaluator import Evaluator
from my_alphaevolve.problem import load_problem
from my_alphaevolve.program import Program

# The folder holding the function-minimization example, found relative to this test file
EXAMPLE_FOLDER = Path(__file__).parent.parent / "examples" / "function_minimization"


def make_code(answer: str) -> str:
    """Build the code of a program whose search function returns the given expression."""
    return f"def search():\n    return {answer}\n"


class TestFunctionMinimization(unittest.TestCase):
    """Checks on the function-minimization example's evaluation criteria."""

    def setUp(self) -> None:
        # Runs before every test: the example problem and a fresh evaluator for it
        self.problem = load_problem(
            EXAMPLE_FOLDER / "initial_program.py",
            EXAMPLE_FOLDER / "evaluation.py",
        )
        self.evaluator = Evaluator(self.problem.score_function)

    def score_of(self, code: str) -> float:
        """Evaluate a piece of code and return its score."""
        return self.evaluator.execute(Program(code))

    def test_initial_program_gets_a_real_score(self) -> None:
        # The starting program must be valid, otherwise evolution has nothing to build on
        score = self.score_of(self.problem.initial_code)
        self.assertNotEqual(score, self.evaluator.failure_score)

    def test_score_is_the_negated_target_value(self) -> None:
        # The example's target function is sin(3x) + x^2 / 10, here at x = 2
        self.assertAlmostEqual(self.score_of(make_code("2")), -(math.sin(6) + 0.4))

    def test_lower_point_on_the_curve_scores_higher(self) -> None:
        # x = -0.5 is near the bottom of the deepest valley; x = 0.5 is near a peak
        self.assertGreater(self.score_of(make_code("-0.5")), self.score_of(make_code("0.5")))

    def test_rule_breaking_programs_get_the_failure_score(self) -> None:
        # Each entry: why the program is bad -> its code
        bad_programs = {
            "function missing": "x = 1\n",
            "crash inside the function": make_code("1 / 0"),
            "answer is text": make_code("'a'"),
            "answer is a pair": make_code("(1.0, 2.0)"),
            "answer is a bool": make_code("True"),
            "answer is nan": make_code("float('nan')"),
            "answer is infinite": make_code("float('inf')"),
        }
        for reason, code in bad_programs.items():
            # subTest reports each bad program separately if several fail
            with self.subTest(reason=reason):
                self.assertEqual(self.score_of(code), self.evaluator.failure_score)


if __name__ == "__main__":
    unittest.main()
