"""Checks on the circle packing example's evaluation criteria."""

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


def grid_packing() -> tuple[list[tuple[float, float]], list[float]]:
    """Return a valid packing: 26 circles of radius 1/12 on a grid of 6 columns."""
    centers = [
        ((2 * column + 1) / 12, (2 * row + 1) / 10) for row in range(5) for column in range(6)
    ]
    return centers[:26], [1 / 12] * 26


def packing_code(centers: Any, radii: Any) -> str:
    """Build the code of a program whose construct_packing returns the given values."""
    return f"def construct_packing():\n    return {centers!r}, {radii!r}\n"


class ArrayLike:
    """Behaves like a numpy array for the evaluation: it has a tolist method."""

    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def tolist(self) -> list[Any]:
        return self.values


class TestCirclePacking(unittest.TestCase):
    """Checks on evaluation.py, with programs scored in the test process."""

    def setUp(self) -> None:
        self.problem = load_problem(
            EXAMPLE_FOLDER / "initial_program.py", EXAMPLE_FOLDER / "evaluation.py"
        )
        self.score_function = load_score_function(EXAMPLE_FOLDER / "evaluation.py")
        self.evaluator = InProcessEvaluator(self.score_function)

    def test_initial_program_is_valid_and_matches_openevolve(self) -> None:
        # OpenEvolve's initial packing scores about 0.96.
        score = self.evaluator.execute(Program(self.problem.initial_code))
        self.assertAlmostEqual(score, 0.9597642, places=6)

    def test_description_states_the_problem(self) -> None:
        self.assertIn("26 circles", self.problem.description)
        self.assertIn("construct_packing()", self.problem.description)

    def test_example_allows_numpy_and_scipy(self) -> None:
        self.assertEqual(self.problem.packages, ["numpy", "scipy"])

    def test_score_is_the_sum_of_the_radii(self) -> None:
        centers, radii = grid_packing()
        score = self.evaluator.execute(Program(packing_code(centers, radii)))
        self.assertAlmostEqual(score, 26 / 12)

    def test_array_like_values_are_accepted(self) -> None:
        centers, radii = grid_packing()
        namespace = {
            "construct_packing": lambda: (
                ArrayLike([ArrayLike(list(center)) for center in centers]),
                ArrayLike(radii),
            )
        }
        self.assertAlmostEqual(self.score_function(namespace), 26 / 12)

    def test_tiny_numerical_errors_are_tolerated(self) -> None:
        centers, radii = grid_packing()
        radii[0] += 1e-7
        score = self.evaluator.execute(Program(packing_code(centers, radii)))
        self.assertAlmostEqual(score, 26 / 12 + 1e-7)

    def test_rule_breaking_packings_get_the_failure_score(self) -> None:
        centers, radii = grid_packing()
        bad_programs = {
            "function missing": "x = 1\n",
            "one value returned": f"def construct_packing():\n    return {centers!r}\n",
            "25 circles": packing_code(centers[:25], radii[:25]),
            "radii of the wrong length": packing_code(centers, radii[:25]),
            "a center with three numbers": packing_code([(0.5, 0.5, 0.5)] + centers[1:], radii),
            "overlapping circles": packing_code([centers[1]] + centers[1:], radii),
            "a circle leaving the square": packing_code([(0.05, 0.5)] + centers[1:], radii),
            "a negative radius": packing_code(centers, [-0.01] + radii[1:]),
            "a radius that is nan": packing_code(centers, [math.nan] + radii[1:]),
            "a coordinate that is a bool": packing_code([(True, 0.5)] + centers[1:], radii),
            "a radius that is text": packing_code(centers, ["0.1"] + radii[1:]),
        }
        for reason, code in bad_programs.items():
            with self.subTest(reason=reason):
                score = execute_quietly(self.evaluator, code)
                self.assertEqual(score, self.evaluator.failure_score)


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class TestCirclePackingInDocker(unittest.TestCase):
    """Checks that programs using numpy are scored in the example's container."""

    def test_numpy_arrays_are_accepted(self) -> None:
        evaluator = DockerEvaluator(EXAMPLE_FOLDER / "evaluation.py")
        code = (
            "import numpy as np\n\n"
            "def construct_packing():\n"
            "    columns, rows = np.meshgrid(np.arange(6), np.arange(5))\n"
            "    centers = np.stack([(2 * columns + 1) / 12, (2 * rows + 1) / 10], axis=-1)\n"
            "    return centers.reshape(-1, 2)[:26], np.full(26, 1 / 12)\n"
        )
        self.assertAlmostEqual(evaluator.execute(Program(code)), 26 / 12)


if __name__ == "__main__":
    unittest.main()
