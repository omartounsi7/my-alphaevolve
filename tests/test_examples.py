"""Checks that the example problems in the examples folder work with the evaluator.

The programs are scored the way a real run scores them: each in its own process.
"""

import runpy
import unittest
from pathlib import Path

from my_alphaevolve.evaluator import ProcessEvaluator
from my_alphaevolve.problem import load_problem
from my_alphaevolve.program import Program

# The folder holding the function-minimization example, found relative to this test file
EXAMPLE_FOLDER = Path(__file__).parent.parent / "examples" / "function_minimization"

# A program that tries 2000 random points and keeps the lowest one.
# random.Random(0) always produces the same "random" points, so the test is repeatable.
RANDOM_SEARCH_CODE = """
import random

def search(target_function, lower_bounds, upper_bounds):
    generator = random.Random(0)
    points = [
        [generator.uniform(low, high) for low, high in zip(lower_bounds, upper_bounds)]
        for _ in range(2000)
    ]
    return min(points, key=target_function)
"""


def make_code(answer: str) -> str:
    """Build the code of a program whose search function returns the given expression."""
    return f"def search(target_function, lower_bounds, upper_bounds):\n    return {answer}\n"


class TestFunctionMinimization(unittest.TestCase):
    """Checks on the function-minimization example's evaluation criteria.

    The tests read the function and bounds from target.py, so they keep passing
    when the example is pointed at a different function or number of coordinates.
    """

    def setUp(self) -> None:
        # Runs before every test: the example problem and a fresh evaluator for it
        self.problem = load_problem(
            EXAMPLE_FOLDER / "initial_program.py",
            EXAMPLE_FOLDER / "evaluation.py",
        )
        self.evaluator = ProcessEvaluator(EXAMPLE_FOLDER / "evaluation.py")
        # The example's own settings: the function to minimize and the allowed region
        target_names = runpy.run_path(str(EXAMPLE_FOLDER / "target.py"))
        self.target_function = target_names["target_function"]
        self.lower_bounds: list[float] = target_names["LOWER_BOUNDS"]
        self.upper_bounds: list[float] = target_names["UPPER_BOUNDS"]

    def score_of(self, code: str) -> float:
        """Evaluate a piece of code and return its score."""
        return self.evaluator.execute(Program(code))

    def test_bounds_have_one_entry_per_coordinate(self) -> None:
        self.assertEqual(len(self.lower_bounds), len(self.upper_bounds))
        self.assertGreater(len(self.lower_bounds), 0)

    def test_description_names_the_function_to_write(self) -> None:
        self.assertIn(
            "search(target_function, lower_bounds, upper_bounds)", self.problem.description
        )

    def test_initial_program_gets_a_real_score(self) -> None:
        # The starting program must be valid, otherwise evolution has nothing to build on
        score = self.score_of(self.problem.initial_code)
        self.assertNotEqual(score, self.evaluator.failure_score)

    def test_score_is_the_negated_target_value(self) -> None:
        score = self.score_of(make_code("upper_bounds"))
        self.assertAlmostEqual(score, -self.target_function(self.upper_bounds))

    def test_answer_may_be_a_tuple(self) -> None:
        score = self.score_of(make_code("tuple(upper_bounds)"))
        self.assertAlmostEqual(score, -self.target_function(self.upper_bounds))

    def test_search_receives_the_function_and_can_beat_the_initial_program(self) -> None:
        # A program that really explores the function must do better than a fixed guess
        initial_score = self.score_of(self.problem.initial_code)
        self.assertGreater(self.score_of(RANDOM_SEARCH_CODE), initial_score)

    def test_program_cannot_change_the_bounds_for_later_programs(self) -> None:
        # This program empties the lists it was given before answering
        vandal = (
            "def search(target_function, lower_bounds, upper_bounds):\n"
            "    answer = list(lower_bounds)\n"
            "    lower_bounds.clear()\n"
            "    upper_bounds.clear()\n"
            "    return answer\n"
        )
        self.score_of(vandal)
        score = self.score_of(self.problem.initial_code)
        self.assertNotEqual(score, self.evaluator.failure_score)

    def test_rule_breaking_programs_get_the_failure_score(self) -> None:
        # Each entry: why the program is bad -> its code
        bad_programs = {
            "function missing": "x = 1\n",
            "search takes no arguments": "def search():\n    return [0.0]\n",
            "crash inside the function": make_code("1 / 0"),
            "answer is a single number": make_code("0.0"),
            "answer is text": make_code("'ab'"),
            "too few coordinates": make_code("lower_bounds[:-1]"),
            "too many coordinates": make_code("lower_bounds + [0.0]"),
            "a coordinate is text": make_code("['a'] * len(lower_bounds)"),
            "a coordinate is a bool": make_code("[True] * len(lower_bounds)"),
            "a coordinate is nan": make_code("[float('nan')] * len(lower_bounds)"),
            "a coordinate is infinite": make_code("[float('inf')] * len(lower_bounds)"),
            "below the lower bounds": make_code("[low - 1 for low in lower_bounds]"),
            "above the upper bounds": make_code("[high + 1 for high in upper_bounds]"),
        }
        for reason, code in bad_programs.items():
            # subTest reports each bad program separately if several fail
            with self.subTest(reason=reason):
                self.assertEqual(self.score_of(code), self.evaluator.failure_score)


if __name__ == "__main__":
    unittest.main()
