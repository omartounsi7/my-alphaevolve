"""Checks on the function-minimization example, OpenEvolve's adapted to this project.

The programs are scored in the test process, since these tests check the example's
rules; the Docker evaluator has its own tests.
"""

import contextlib
import io
import unittest
from pathlib import Path
from typing import Any

from docker_check import docker_is_available
from doubles import InProcessEvaluator, execute_quietly

from my_alphaevolve.evaluator import DockerEvaluator
from my_alphaevolve.problem import load_problem, load_score_function
from my_alphaevolve.program import Program

# The folder holding the function-minimization example, found relative to this test file
EXAMPLE_FOLDER = Path(__file__).parent.parent / "examples" / "function_minimization"

# OpenEvolve's approximation of the global minimum: x, y and the function's value there.
GLOBAL_MINIMUM = (-1.704, 0.678, -1.519)


def answer_code(answer: str) -> str:
    """Build the code of a program whose run_search returns the given expression."""
    return f"def run_search():\n    return {answer}\n"


def counting_code(answer: str) -> str:
    """Build the code of a program that records each call of run_search in a list."""
    return f"calls = []\n\ndef run_search():\n    calls.append(1)\n    return {answer}\n"


class TestFunctionMinimization(unittest.TestCase):
    """Checks on the function-minimization example's evaluation criteria."""

    def setUp(self) -> None:
        # Runs before every test: the example problem and a fresh evaluator for it
        self.problem = load_problem(
            EXAMPLE_FOLDER / "initial_program.py",
            EXAMPLE_FOLDER / "evaluation.py",
        )
        self.score_function = load_score_function(EXAMPLE_FOLDER / "evaluation.py")
        self.evaluator = InProcessEvaluator(self.score_function)

    def score_of(self, code: str) -> float:
        """Evaluate a piece of code and return its score."""
        return execute_quietly(self.evaluator, code)

    def calls_made(self, code: str) -> int:
        """Return how many times the evaluation calls a counting program's run_search."""
        namespace: dict[str, Any] = {}
        exec(code, namespace)
        self.score_function(namespace)
        return len(namespace["calls"])

    def test_description_states_the_problem(self) -> None:
        self.assertIn("sin(x) * cos(y) + sin(x * y) + (x^2 + y^2) / 20", self.problem.description)
        self.assertIn("run_search()", self.problem.description)

    def test_initial_program_gets_a_real_score(self) -> None:
        # Its random search gives a different score on each evaluation.
        score = self.score_of(self.problem.initial_code)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.5)

    def test_global_minimum_gets_the_highest_score(self) -> None:
        self.assertEqual(self.score_of(answer_code(repr(GLOBAL_MINIMUM))), 1.5)

    def test_value_is_computed_when_only_x_and_y_are_returned(self) -> None:
        score = self.score_of(answer_code(repr(GLOBAL_MINIMUM[:2])))
        self.assertAlmostEqual(score, 1.5, places=3)

    def test_point_far_from_the_minimum_scores_less(self) -> None:
        far = self.score_of(answer_code("4.0, 4.0"))
        near = self.score_of(answer_code("-1.6, 0.7"))
        self.assertLess(far, near)

    def test_weak_programs_are_scored_on_one_call(self) -> None:
        self.assertEqual(self.calls_made(counting_code("4.0, 4.0")), 1)

    def test_strong_programs_are_scored_again_on_ten_calls(self) -> None:
        # A stage 1 score of 1.3 or more leads to stage 2, as in OpenEvolve.
        self.assertEqual(self.calls_made(counting_code(repr(GLOBAL_MINIMUM))), 11)

    def test_failed_calls_lower_the_score(self) -> None:
        # Every other call fails: stage 2 counts 5 successes out of 10.
        code = (
            "calls = []\n\n"
            "def run_search():\n"
            "    calls.append(1)\n"
            "    if len(calls) % 2 == 0:\n"
            "        raise ValueError('failed')\n"
            f"    return {GLOBAL_MINIMUM!r}\n"
        )
        self.assertAlmostEqual(self.score_of(code), 1.5 * (0.5 + 0.3 + 0.2 * 0.5))

    def test_programs_that_break_the_rules_score_zero(self) -> None:
        # As in OpenEvolve, these score 0 rather than failing.
        bad_programs = {
            "function missing": "x = 1\n",
            "crash inside the function": answer_code("1 / 0"),
            "a single number": answer_code("0.0"),
            "a list instead of a tuple": answer_code("[0.0, 0.0]"),
            "four values": answer_code("0.0, 0.0, 0.0, 0.0"),
            "text": answer_code("'a', 'b'"),
            "nan": answer_code("float('nan'), 0.0, 0.0"),
            "infinite": answer_code("float('inf'), 0.0, 0.0"),
        }
        for reason, code in bad_programs.items():
            with self.subTest(reason=reason):
                self.assertEqual(self.score_of(code), 0.0)

    def test_program_that_does_not_run_fails(self) -> None:
        self.assertEqual(self.score_of("def run_search(:\n"), self.evaluator.failure_score)


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class TestFunctionMinimizationInDocker(unittest.TestCase):
    """Checks that the example's packages are installed in its container, and nothing else.

    The first run builds the example's image, which downloads its packages.
    """

    def setUp(self) -> None:
        self.evaluator = DockerEvaluator(EXAMPLE_FOLDER / "evaluation.py")
        self.problem = load_problem(
            EXAMPLE_FOLDER / "initial_program.py", EXAMPLE_FOLDER / "evaluation.py"
        )

    def test_example_lists_openevolve_packages(self) -> None:
        self.assertEqual(self.problem.packages, ["numpy", "scipy"])

    def test_initial_program_gets_a_real_score(self) -> None:
        self.assertGreater(self.evaluator.execute(Program(self.problem.initial_code)), 0.0)

    def test_program_may_use_the_listed_packages(self) -> None:
        code = (
            "import numpy as np\n"
            "from scipy.optimize import minimize\n\n"
            "def run_search():\n"
            "    def f(point):\n"
            "        x, y = point\n"
            "        return np.sin(x) * np.cos(y) + np.sin(x * y) + (x**2 + y**2) / 20\n"
            "    x, y = minimize(f, [-1.5, 0.5]).x\n"
            "    return x, y\n"
        )
        self.assertAlmostEqual(self.evaluator.execute(Program(code)), 1.5, places=3)

    def test_program_cannot_use_other_packages(self) -> None:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            score = self.evaluator.execute(Program("import pandas\n"))
        self.assertEqual(score, self.evaluator.failure_score)
        self.assertIn("No module named 'pandas'", printed.getvalue())


if __name__ == "__main__":
    unittest.main()
