"""Checks that both evaluators behave as intended, using tiny made-up problems."""

import contextlib
import io
import math
import random
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

from my_alphaevolve.evaluator import InProcessEvaluator, ProcessEvaluator
from my_alphaevolve.problem import ScoreFunction
from my_alphaevolve.program import Program

# An evaluation file whose score is the value of the program's answer variable.
# It uses math.sqrt and a helper file, so the tests can check both stay intact.
EVALUATION_CODE = """\
import math

from my_alphaevolve_evaluator_test_helper import BONUS


def evaluate(namespace):
    if "answer" not in namespace:
        raise ValueError("the program must define answer → a number")
    return math.sqrt(namespace["answer"]) + BONUS
"""


def read_answer(namespace: dict[str, Any]) -> float:
    """Score a program by the value of the variable called answer that it defines."""
    return float(namespace["answer"])


def always_returns(value: Any) -> ScoreFunction:
    """Build a score function that ignores the program and returns the given value."""
    return lambda namespace: value


class TestInProcessEvaluator(unittest.TestCase):
    """Checks on InProcessEvaluator.execute."""

    def setUp(self) -> None:
        # Runs before every test: an evaluator whose score is the program's answer variable
        self.evaluator = InProcessEvaluator(read_answer)

    def execute_quietly(self, evaluator: InProcessEvaluator, code: str) -> float:
        """Evaluate a piece of code without showing the failure messages it prints."""
        with contextlib.redirect_stdout(io.StringIO()):
            return evaluator.execute(Program(code))

    def test_score_comes_from_the_score_function(self) -> None:
        self.assertEqual(self.evaluator.execute(Program("answer = 3.5\n")), 3.5)

    def test_whole_number_scores_are_returned_as_decimals(self) -> None:
        score = InProcessEvaluator(always_returns(3)).execute(Program("x = 1\n"))
        self.assertEqual(score, 3.0)
        self.assertIsInstance(score, float)

    def test_execute_does_not_change_the_program(self) -> None:
        program = Program("answer = 3.5\n")
        self.evaluator.execute(program)
        self.assertIsNone(program.score)

    def test_each_program_starts_from_an_empty_namespace(self) -> None:
        # The second program must not see the answer defined by the first one
        self.evaluator.execute(Program("answer = 3.5\n"))
        score = self.execute_quietly(self.evaluator, "x = 1\n")
        self.assertEqual(score, self.evaluator.failure_score)

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
                score = self.execute_quietly(self.evaluator, code)
                self.assertEqual(score, self.evaluator.failure_score)

    def test_invalid_scores_become_the_failure_score(self) -> None:
        # Each entry: a value a faulty score function might return
        invalid_scores: list[Any] = [float("nan"), float("inf"), None, "great", True, [1.0]]
        for invalid_score in invalid_scores:
            with self.subTest(invalid_score=invalid_score):
                evaluator = InProcessEvaluator(always_returns(invalid_score))
                score = self.execute_quietly(evaluator, "x = 1\n")
                self.assertEqual(score, evaluator.failure_score)


class TestProcessEvaluator(unittest.TestCase):
    """Checks on ProcessEvaluator.execute. Each evaluation starts a real child process."""

    def setUp(self) -> None:
        # Runs before every test: a folder, deleted afterwards, holding an evaluation
        # file and the helper file it imports
        temporary_folder = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_folder.cleanup)
        self.folder = Path(temporary_folder.name)
        (self.folder / "my_alphaevolve_evaluator_test_helper.py").write_text(
            "BONUS = 1.0\n", encoding="utf-8"
        )
        self.evaluation_path = self.folder / "evaluation.py"
        self.evaluation_path.write_text(EVALUATION_CODE, encoding="utf-8")
        # A generous limit: these tests are about results, not about speed
        self.evaluator = ProcessEvaluator(self.evaluation_path, timeout_seconds=60.0)

    def execute_quietly(self, code: str, evaluator: ProcessEvaluator | None = None) -> float:
        """Evaluate a piece of code without showing the failure messages the parent prints."""
        with contextlib.redirect_stdout(io.StringIO()):
            return (evaluator or self.evaluator).execute(Program(code))

    def test_score_comes_from_the_evaluation_file_and_its_helper(self) -> None:
        # sqrt(9) from the evaluation file, plus the BONUS of 1 from the helper file
        self.assertEqual(self.evaluator.execute(Program("answer = 9\n")), 4.0)

    def test_failing_programs_get_the_failure_score(self) -> None:
        # Each entry: why the program is bad -> its code
        bad_programs = {
            "syntax error": "answer = (\n",
            "crash while running": "answer = 1 / 0\n",
            "evaluation file rejects the program": "x = 1\n",
            "evaluation crashes on the answer": "answer = 'text'\n",
            "program ends its process politely": "import sys\nsys.exit(0)\n",
            "program ends its process abruptly": "import os\nos._exit(1)\n",
        }
        for reason, code in bad_programs.items():
            # subTest reports each bad program separately if several fail
            with self.subTest(reason=reason):
                self.assertEqual(self.execute_quietly(code), self.evaluator.failure_score)

    def test_failure_message_says_what_went_wrong(self) -> None:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.evaluator.execute(Program("answer = 1 / 0\n"))
        self.assertIn("ZeroDivisionError: division by zero", printed.getvalue())

    def test_failure_message_may_hold_characters_outside_plain_english(self) -> None:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.evaluator.execute(Program("x = 1\n"))
        self.assertIn("answer → a number", printed.getvalue())

    def test_program_that_never_ends_is_stopped_at_the_time_limit(self) -> None:
        impatient_evaluator = ProcessEvaluator(self.evaluation_path, timeout_seconds=1.0)
        start = time.monotonic()
        score = self.execute_quietly("while True:\n    pass\n", impatient_evaluator)
        elapsed_seconds = time.monotonic() - start
        self.assertEqual(score, impatient_evaluator.failure_score)
        # It waited for the limit, and did not hang long past it
        self.assertGreaterEqual(elapsed_seconds, 1.0)
        self.assertLess(elapsed_seconds, 20.0)

    def test_evaluator_still_works_after_a_program_was_stopped(self) -> None:
        impatient_evaluator = ProcessEvaluator(self.evaluation_path, timeout_seconds=1.0)
        self.execute_quietly("while True:\n    pass\n", impatient_evaluator)
        self.assertEqual(self.evaluator.execute(Program("answer = 9\n")), 4.0)

    def test_program_cannot_change_how_later_programs_are_scored(self) -> None:
        # This program replaces the square root used by the evaluation file
        cheater = "import math\nmath.sqrt = lambda number: 1000.0\nanswer = 9\n"
        self.execute_quietly(cheater)
        # A later, honest program is scored with the real square root
        self.assertEqual(self.evaluator.execute(Program("answer = 9\n")), 4.0)
        # And the main process, where the tests run, was never touched
        self.assertEqual(math.sqrt(9), 3.0)

    def test_program_cannot_disturb_the_random_numbers_of_the_main_process(self) -> None:
        random.seed(123)
        expected = [random.random() for _ in range(3)]
        random.seed(123)
        self.evaluator.execute(Program("import random\nrandom.seed(0)\nanswer = 9\n"))
        self.assertEqual([random.random() for _ in range(3)], expected)

    def test_evaluation_file_without_evaluate_fails_every_program(self) -> None:
        empty_evaluation = self.folder / "empty_evaluation.py"
        empty_evaluation.write_text("x = 1\n", encoding="utf-8")
        evaluator = ProcessEvaluator(empty_evaluation, timeout_seconds=60.0)
        self.assertEqual(self.execute_quietly("answer = 9\n", evaluator), evaluator.failure_score)

    def test_time_limit_must_be_above_zero(self) -> None:
        with self.assertRaises(ValueError):
            ProcessEvaluator(self.evaluation_path, timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
