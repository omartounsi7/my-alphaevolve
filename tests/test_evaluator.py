"""Checks that the Evaluator and the point-spreading problem behave as intended."""

import unittest

from my_alphaevolve.evaluator import Evaluator
from my_alphaevolve.problem import INITIAL_CODE, NUM_POINTS, score_function
from my_alphaevolve.program import Program


def make_code(points: object) -> str:
    """Build the code of a program whose place_points returns the given points.

    points is typed as object (anything) because tests also pass invalid answers.
    """
    return f"def place_points():\n    return {points!r}\n"


class TestEvaluator(unittest.TestCase):
    """Checks on Evaluator.execute, using the real problem's score function."""

    def setUp(self) -> None:
        # Runs before every test: a fresh evaluator for the point-spreading problem
        self.evaluator = Evaluator(score_function)

    def score_of(self, code: str) -> float:
        """Evaluate a piece of code and return its score."""
        return self.evaluator.execute(Program(code))

    def test_initial_program_scores_the_gap_between_neighbours(self) -> None:
        # 10 points evenly spread along a line of length 1 are 1/9 apart
        self.assertAlmostEqual(self.score_of(INITIAL_CODE), 1 / 9)

    def test_better_spread_points_score_higher(self) -> None:
        # Two rows of five points: neighbours are 0.25 apart, wider than 1/9
        two_rows = [(i / 4, y) for y in (0.0, 1.0) for i in range(5)]
        self.assertAlmostEqual(self.score_of(make_code(two_rows)), 0.25)

    def test_execute_does_not_change_the_program(self) -> None:
        program = Program(INITIAL_CODE)
        self.evaluator.execute(program)
        self.assertIsNone(program.score)

    def test_failing_programs_get_the_failure_score(self) -> None:
        # Each entry: why the program is bad -> its code
        bad_programs = {
            "syntax error": "def place_points(:\n",
            "function missing": "x = 1\n",
            "crash inside the function": "def place_points():\n    return 1 / 0\n",
            "answer is not a list": "def place_points():\n    return 5\n",
            "too few points": make_code([(0.5, 0.5)]),
            "point outside the square": make_code([(2.0, 0.5)] * NUM_POINTS),
            "point with three coordinates": make_code([(0.1, 0.2, 0.3)] * NUM_POINTS),
            "coordinate is not a number": make_code([("a", "b")] * NUM_POINTS),
            "coordinate is nan": "def place_points():\n"
            f"    return [(float('nan'), 0.5)] * {NUM_POINTS}\n",
        }
        for reason, code in bad_programs.items():
            # subTest reports each bad program separately if several fail
            with self.subTest(reason=reason):
                self.assertEqual(self.score_of(code), self.evaluator.failure_score)


if __name__ == "__main__":
    unittest.main()
