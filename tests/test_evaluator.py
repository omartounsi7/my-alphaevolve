"""Checks that the Evaluator and the function-minimization problem behave as intended."""

import unittest

from my_alphaevolve.evaluator import Evaluator
from my_alphaevolve.problem import INITIAL_CODE, score_function, target_function
from my_alphaevolve.program import Program


def make_code(answer: str) -> str:
    """Build the code of a program whose search function returns the given expression."""
    return f"def search():\n    return {answer}\n"


class TestEvaluator(unittest.TestCase):
    """Checks on Evaluator.execute, using the real problem's score function."""

    def setUp(self) -> None:
        # Runs before every test: a fresh evaluator for the minimization problem
        self.evaluator = Evaluator(score_function)

    def score_of(self, code: str) -> float:
        """Evaluate a piece of code and return its score."""
        return self.evaluator.execute(Program(code))

    def test_initial_program_gets_a_real_score(self) -> None:
        # The starting program must be valid, otherwise evolution has nothing to build on
        self.assertNotEqual(self.score_of(INITIAL_CODE), self.evaluator.failure_score)

    def test_score_is_the_negated_target_value(self) -> None:
        self.assertAlmostEqual(self.score_of(make_code("2")), -target_function(2))

    def test_lower_point_on_the_curve_scores_higher(self) -> None:
        # x = -0.5 is near the bottom of the deepest valley; x = 0.5 is near a peak
        self.assertGreater(self.score_of(make_code("-0.5")), self.score_of(make_code("0.5")))

    def test_execute_does_not_change_the_program(self) -> None:
        program = Program(INITIAL_CODE)
        self.evaluator.execute(program)
        self.assertIsNone(program.score)

    def test_failing_programs_get_the_failure_score(self) -> None:
        # Each entry: why the program is bad -> its code
        bad_programs = {
            "syntax error": "def search(:\n",
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
