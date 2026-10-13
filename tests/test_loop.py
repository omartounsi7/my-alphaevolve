"""Checks that the main loop and the command-line script run from start to finish."""

import contextlib
import io
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

from my_alphaevolve.llm import FakeLLM
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

    def setUp(self) -> None:
        # Runs before every test: a fake LLM whose prompts the tests can inspect
        self.llm = FakeLLM(["a prepared reply"])

    def run_and_capture_output(self, problem: Problem) -> str:
        """Run the loop on a problem and return everything it printed."""
        printed = io.StringIO()
        # Send print() output into the printed variable instead of the screen
        with contextlib.redirect_stdout(printed):
            run_my_alphaevolve(problem, self.llm)
        return printed.getvalue()

    def test_reports_the_score_of_a_valid_initial_program(self) -> None:
        code = '"""Make answer as large as possible."""\n\nanswer = 3.5\n'
        output = self.run_and_capture_output(Problem(code, read_answer))
        self.assertIn("score=3.5", output)

    def test_llm_receives_a_prompt_with_the_description_and_the_parent_code(self) -> None:
        code = '"""Make answer as large as possible."""\n\nanswer = 3.5\n'
        self.run_and_capture_output(Problem(code, read_answer))
        self.assertEqual(len(self.llm.prompts), 1)
        prompt = self.llm.prompts[0]
        self.assertIn("Problem description:\nMake answer as large as possible.", prompt)
        self.assertIn("answer = 3.5", prompt)

    def test_reply_from_the_llm_is_reported(self) -> None:
        code = '"""Make answer as large as possible."""\n\nanswer = 3.5\n'
        output = self.run_and_capture_output(Problem(code, read_answer))
        self.assertIn("a prepared reply", output)

    def test_failing_initial_program_stops_the_run(self) -> None:
        # Valid Python with a description, but it crashes as soon as it runs
        code = '"""Make answer as large as possible."""\n\nanswer = 1 / 0\n'
        with self.assertRaises(ValueError):
            self.run_and_capture_output(Problem(code, read_answer))


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
