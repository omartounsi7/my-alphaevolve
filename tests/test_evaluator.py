"""Checks that the Evaluator behaves as intended, using tiny made-up score functions."""

import unittest
from typing import Any

from my_alphaevolve.evaluator import Evaluator
from my_alphaevolve.problem import ScoreFunction
from my_alphaevolve.program import Program


def read_answer(namespace: dict[str, Any]) -> float:
    """Score a program by the value of the variable called answer that it defines."""
    return float(namespace["answer"])


def always_returns(value: Any) -> ScoreFunction:
    """Build a score function that ignores the program and returns the given value."""
    return lambda namespace: value


class TestEvaluator(unittest.TestCase):
    """Checks on Evaluator.execute."""

    def setUp(self) -> None:
        # Runs before every test: an evaluator whose score is the program's answer variable
        self.evaluator = Evaluator(read_answer)

    def test_score_comes_from_the_score_function(self) -> None:
        self.assertEqual(self.evaluator.execute(Program("answer = 3.5\n")), 3.5)

    def test_whole_number_scores_are_returned_as_decimals(self) -> None:
        score = Evaluator(always_returns(3)).execute(Program("x = 1\n"))
        self.assertEqual(score, 3.0)
        self.assertIsInstance(score, float)

    def test_execute_does_not_change_the_program(self) -> None:
        program = Program("answer = 3.5\n")
        self.evaluator.execute(program)
        self.assertIsNone(program.score)

    def test_each_program_starts_from_an_empty_namespace(self) -> None:
        # The second program must not see the answer defined by the first one
        self.evaluator.execute(Program("answer = 3.5\n"))
        self.assertEqual(self.evaluator.execute(Program("x = 1\n")), self.evaluator.failure_score)

    def test_failing_programs_get_the_failure_score(self) -> None:
        # Each entry: why the program is bad -> its code
        bad_programs = {
            "syntax error": "answer = (\n",
            "crash while running": "answer = 1 / 0\n",
            "expected name missing": "x = 1\n",
            "score function rejects the answer": "answer = 'text'\n",
        }
        for reason, code in bad_programs.items():
            # subTest reports each bad program separately if several fail
            with self.subTest(reason=reason):
                score = self.evaluator.execute(Program(code))
                self.assertEqual(score, self.evaluator.failure_score)

    def test_invalid_scores_become_the_failure_score(self) -> None:
        # Each entry: a value a faulty score function might return
        invalid_scores: list[Any] = [float("nan"), float("inf"), None, "great", True, [1.0]]
        for invalid_score in invalid_scores:
            with self.subTest(invalid_score=invalid_score):
                evaluator = Evaluator(always_returns(invalid_score))
                score = evaluator.execute(Program("x = 1\n"))
                self.assertEqual(score, evaluator.failure_score)


if __name__ == "__main__":
    unittest.main()
