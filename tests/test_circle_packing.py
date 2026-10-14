"""Checks on the circle packing example, OpenEvolve's adapted to this project."""

import math
import unittest
from pathlib import Path
from typing import Any

from docker_check import docker_is_available
from doubles import InProcessEvaluator, execute_quietly

from my_alphaevolve.evaluator import DockerEvaluator
from my_alphaevolve.problem import load_problem, load_score_function
from my_alphaevolve.program import Program

EXAMPLE_FOLDER = Path(__file__).parent.parent / "examples" / "circle_packing"
# The sum of radii the AlphaEvolve paper reached, which scores are divided by.
TARGET_VALUE = 2.635


def grid_packing() -> tuple[list[tuple[float, float]], list[float]]:
    """Return a valid packing: 26 circles of radius 1/12 on a grid of 6 columns."""
    centers = [
        ((2 * column + 1) / 12, (2 * row + 1) / 10) for row in range(5) for column in range(6)
    ]
    return centers[:26], [1 / 12] * 26


def packing_code(centers: Any, radii: Any) -> str:
    """Build the code of a program whose run_packing returns the given values."""
    return f"def run_packing():\n    return {centers!r}, {radii!r}, 0.0\n"


class TestCirclePacking(unittest.TestCase):
    """Checks on evaluation.py, with programs scored in the test process."""

    def setUp(self) -> None:
        self.problem = load_problem(
            EXAMPLE_FOLDER / "initial_program.py", EXAMPLE_FOLDER / "evaluation.py"
        )
        self.score_function = load_score_function(EXAMPLE_FOLDER / "evaluation.py")
        self.evaluator = InProcessEvaluator(self.score_function)

    def calls_made(self, centers: Any, radii: Any) -> int:
        """Return how many times the evaluation calls run_packing."""
        namespace: dict[str, Any] = {"calls": []}
        exec(
            f"def run_packing():\n    calls.append(1)\n    return {centers!r}, {radii!r}, 0.0\n",
            namespace,
        )
        self.score_function(namespace)
        return len(namespace["calls"])

    def test_initial_program_scores_as_in_openevolve(self) -> None:
        # A sum of radii of 0.9598, divided by 2.635.
        score = self.evaluator.execute(Program(self.problem.initial_code))
        self.assertAlmostEqual(score, 0.9597642 / TARGET_VALUE, places=6)

    def test_description_states_the_problem(self) -> None:
        self.assertIn("26 circles", self.problem.description)
        self.assertIn("run_packing()", self.problem.description)

    def test_example_allows_openevolve_packages(self) -> None:
        self.assertEqual(self.problem.packages, ["matplotlib", "numpy", "scipy"])

    def test_score_is_the_sum_of_the_radii_divided_by_the_target(self) -> None:
        centers, radii = grid_packing()
        score = self.evaluator.execute(Program(packing_code(centers, radii)))
        self.assertAlmostEqual(score, 26 / 12 / TARGET_VALUE)

    def test_tiny_numerical_errors_are_tolerated(self) -> None:
        centers, radii = grid_packing()
        radii[0] += 1e-7
        score = self.evaluator.execute(Program(packing_code(centers, radii)))
        self.assertAlmostEqual(score, (26 / 12 + 1e-7) / TARGET_VALUE)

    def test_weak_packings_are_run_once(self) -> None:
        centers, radii = grid_packing()
        self.assertEqual(self.calls_made(centers, [r / 2 for r in radii]), 1)

    def test_packings_scoring_half_the_target_are_run_again(self) -> None:
        # A stage 1 score of 0.5 or more leads to stage 2, as in OpenEvolve.
        self.assertEqual(self.calls_made(*grid_packing()), 2)

    def test_packings_that_break_the_rules_score_zero(self) -> None:
        # As in OpenEvolve, these score 0 rather than failing.
        centers, radii = grid_packing()
        bad_programs = {
            "function missing": "x = 1\n",
            "two values returned": f"def run_packing():\n    return {centers!r}, {radii!r}\n",
            "25 circles": packing_code(centers[:25], radii[:25]),
            "radii of the wrong length": packing_code(centers, radii[:25]),
            "a center with three numbers": packing_code([(0.5, 0.5, 0.5)] + centers[1:], radii),
            "overlapping circles": packing_code([centers[1]] + centers[1:], radii),
            "a circle leaving the square": packing_code([(0.05, 0.5)] + centers[1:], radii),
            "a negative radius": packing_code(centers, [-0.01] + radii[1:]),
            "a radius that is nan": packing_code(centers, [math.nan] + radii[1:]),
            "a radius that is text": packing_code(centers, ["0.1"] + radii[1:]),
        }
        for reason, code in bad_programs.items():
            with self.subTest(reason=reason):
                self.assertEqual(execute_quietly(self.evaluator, code), 0.0)


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class TestCirclePackingInDocker(unittest.TestCase):
    """Checks that the example's packages are installed in its container."""

    def setUp(self) -> None:
        self.evaluator = DockerEvaluator(EXAMPLE_FOLDER / "evaluation.py")

    def test_initial_program_scores_as_in_openevolve(self) -> None:
        problem = load_problem(
            EXAMPLE_FOLDER / "initial_program.py", EXAMPLE_FOLDER / "evaluation.py"
        )
        score = self.evaluator.execute(Program(problem.initial_code))
        self.assertAlmostEqual(score, 0.9597642 / TARGET_VALUE, places=6)

    def test_program_may_use_the_listed_packages(self) -> None:
        code = (
            "import matplotlib\n"
            "import numpy as np\n"
            "import scipy\n\n"
            "def run_packing():\n"
            "    columns, rows = np.meshgrid(np.arange(6), np.arange(5))\n"
            "    centers = np.stack([(2 * columns + 1) / 12, (2 * rows + 1) / 10], axis=-1)\n"
            "    radii = np.full(26, 1 / 12)\n"
            "    return centers.reshape(-1, 2)[:26], radii, np.sum(radii)\n"
        )
        self.assertAlmostEqual(self.evaluator.execute(Program(code)), 26 / 12 / TARGET_VALUE)


if __name__ == "__main__":
    unittest.main()
