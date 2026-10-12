"""Checks that the main loop and the command-line script run from start to finish."""

import contextlib
import io
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

from my_alphaevolve.loop import run_my_alphaevolve
from my_alphaevolve.problem import Problem

# The top folder of the repository, found relative to this test file
REPOSITORY_FOLDER = Path(__file__).parent.parent
# The script a user launches, and the example problem it is tested with
RUN_SCRIPT = REPOSITORY_FOLDER / "scripts" / "run.py"
EXAMPLE_FOLDER = REPOSITORY_FOLDER / "examples" / "function_minimization"


def read_answer(namespace: dict[str, Any]) -> float:
    """Score a program by the value of the variable called answer that it defines."""
    return float(namespace["answer"])


class TestRunMyAlphaevolve(unittest.TestCase):
    """Checks on run_my_alphaevolve, using a tiny made-up problem."""

    def run_and_capture_output(self, problem: Problem) -> str:
        """Run the loop on a problem and return everything it printed."""
        printed = io.StringIO()
        # Send print() output into the printed variable instead of the screen
        with contextlib.redirect_stdout(printed):
            run_my_alphaevolve(problem)
        return printed.getvalue()

    def test_reports_the_score_of_a_valid_initial_program(self) -> None:
        output = self.run_and_capture_output(Problem("answer = 3.5\n", read_answer))
        self.assertIn("score=3.5", output)

    def test_broken_initial_program_stops_the_run(self) -> None:
        with self.assertRaises(ValueError):
            self.run_and_capture_output(Problem("answer = (\n", read_answer))


class TestRunScript(unittest.TestCase):
    """Checks on scripts/run.py, launched the way a user would launch it."""

    def launch(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """Run the script in a separate Python process and return its result."""
        return subprocess.run(
            [sys.executable, str(RUN_SCRIPT), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_runs_the_example_problem(self) -> None:
        result = self.launch(
            str(EXAMPLE_FOLDER / "initial_program.py"),
            str(EXAMPLE_FOLDER / "evaluation.py"),
        )
        # Return code 0 is how a program tells the system it finished without error
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Best program so far", result.stdout)

    def test_missing_arguments_are_reported(self) -> None:
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage", result.stderr)


if __name__ == "__main__":
    unittest.main()
