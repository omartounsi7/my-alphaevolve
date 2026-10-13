"""Checks that the example problems in the examples folder work with the Evaluator."""

import runpy
import unittest
from pathlib import Path

from my_alphaevolve.evaluator import Evaluator
from my_alphaevolve.problem import load_problem
from my_alphaevolve.program import Program

# The folder holding the function-minimization example, found relative to this test file
EXAMPLE_FOLDER = Path(__file__).parent.parent / "examples" / "function_minimization"

# A program that tries 2001 evenly spaced points and keeps the lowest one
GRID_SEARCH_CODE = """
def search(target_function, lower_bound, upper_bound):
    step = (upper_bound - lower_bound) / 2000
    points = [lower_bound + i * step for i in range(2001)]
    return min(points, key=target_function)
"""


def make_code(answer: str) -> str:
    """Build the code of a program whose search function returns the given expression."""
    return f"def search(target_function, lower_bound, upper_bound):\n    return {answer}\n"


class TestFunctionMinimization(unittest.TestCase):
    """Checks on the function-minimization example's evaluation criteria.

    The tests read the function and bounds from target.py, so they keep
    passing when the example is pointed at a different function.
    """

    def setUp(self) -> None:
        # Runs before every test: the example problem and a fresh evaluator for it
        self.problem = load_problem(
            EXAMPLE_FOLDER / "initial_program.py",
            EXAMPLE_FOLDER / "evaluation.py",
        )
        self.evaluator = Evaluator(self.problem.score_function)
        # The example's own settings: the function to minimize and the allowed interval
        target_names = runpy.run_path(str(EXAMPLE_FOLDER / "target.py"))
        self.target_function = target_names["target_function"]
        self.lower_bound: float = target_names["LOWER_BOUND"]
        self.upper_bound: float = target_names["UPPER_BOUND"]

    def score_of(self, code: str) -> float:
        """Evaluate a piece of code and return its score."""
        return self.evaluator.execute(Program(code))

    def test_initial_program_describes_the_problem(self) -> None:
        self.assertIn("lowest point of a function", self.problem.description)

    def test_initial_program_gets_a_real_score(self) -> None:
        # The starting program must be valid, otherwise evolution has nothing to build on
        score = self.score_of(self.problem.initial_code)
        self.assertNotEqual(score, self.evaluator.failure_score)

    def test_score_is_the_negated_target_value(self) -> None:
        score = self.score_of(make_code("upper_bound"))
        self.assertAlmostEqual(score, -self.target_function(self.upper_bound))

    def test_search_receives_the_function_and_can_beat_the_initial_program(self) -> None:
        # A program that really explores the function must do better than a fixed guess
        initial_score = self.score_of(self.problem.initial_code)
        self.assertGreater(self.score_of(GRID_SEARCH_CODE), initial_score)

    def test_rule_breaking_programs_get_the_failure_score(self) -> None:
        # Each entry: why the program is bad -> its code
        bad_programs = {
            "function missing": "x = 1\n",
            "search takes no arguments": "def search():\n    return 0.0\n",
            "crash inside the function": make_code("1 / 0"),
            "answer is text": make_code("'a'"),
            "answer is a pair": make_code("(lower_bound, upper_bound)"),
            "answer is a bool": make_code("True"),
            "answer is nan": make_code("float('nan')"),
            "answer is infinite": make_code("float('inf')"),
            "answer below the lower bound": make_code("lower_bound - 1"),
            "answer above the upper bound": make_code("upper_bound + 1"),
        }
        for reason, code in bad_programs.items():
            # subTest reports each bad program separately if several fail
            with self.subTest(reason=reason):
                self.assertEqual(self.score_of(code), self.evaluator.failure_score)


if __name__ == "__main__":
    unittest.main()
