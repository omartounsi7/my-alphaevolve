"""Checks that the main loop and the command-line script run from start to finish."""

import contextlib
import io
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from my_alphaevolve.database import Database
from my_alphaevolve.evaluator import InProcessEvaluator
from my_alphaevolve.llm import FakeLLM
from my_alphaevolve.loop import run_my_alphaevolve
from my_alphaevolve.problem import Problem
from my_alphaevolve.program import Program

# The top folder of the repository, found relative to this test file
REPOSITORY_FOLDER = Path(__file__).parent.parent
# The script a user launches, and the example problem it is tested with
RUN_SCRIPT = REPOSITORY_FOLDER / "scripts" / "run.py"
EXAMPLE_FOLDER = REPOSITORY_FOLDER / "examples" / "function_minimization"


# A minimal valid initial program: a description, then an answer that scores 3.5
INITIAL_CODE = '"""Make answer as large as possible."""\n\nanswer = 3.5\n'


def read_answer(namespace: dict[str, Any]) -> float:
    """Score a program by the value of the variable called answer that it defines."""
    return float(namespace["answer"])


class TestRunMyAlphaevolve(unittest.TestCase):
    """Checks on run_my_alphaevolve, using a tiny made-up problem."""

    def setUp(self) -> None:
        # Runs before every test: a problem whose initial program scores 3.5
        self.problem = Problem(INITIAL_CODE)

    def run_quietly(self, problem: Problem, llm: FakeLLM, iterations: int = 1) -> Database:
        """Run the loop without showing what it prints, and return its database."""
        # Send print() output into a throwaway variable instead of the screen
        with contextlib.redirect_stdout(io.StringIO()):
            # Programs are scored inside this process: fast, and fine for trusted test code
            return run_my_alphaevolve(problem, llm, InProcessEvaluator(read_answer), iterations)

    def child_of(self, database: Database) -> Program:
        """Return the one program in the database that has a parent."""
        children = [p for p in database.programs.values() if p.parent_id is not None]
        self.assertEqual(len(children), 1)
        return children[0]

    def test_llm_receives_a_prompt_with_the_description_and_the_parent_code(self) -> None:
        llm = FakeLLM(["answer = 4.5\n"])
        self.run_quietly(self.problem, llm)
        self.assertEqual(len(llm.prompts), 1)
        prompt = llm.prompts[0]
        self.assertIn("Problem description:\nMake answer as large as possible.", prompt)
        self.assertIn("answer = 3.5", prompt)

    def test_database_holds_the_initial_program_and_its_child(self) -> None:
        database = self.run_quietly(self.problem, FakeLLM(["answer = 4.5\n"]))
        self.assertEqual(len(database.programs), 2)
        child = self.child_of(database)
        # The child's parent is the initial program, which has no parent itself
        parent = database.get(child.parent_id or "")
        assert parent is not None
        self.assertEqual(parent.code, INITIAL_CODE)
        self.assertEqual(parent.score, 3.5)
        self.assertEqual(child.generation, 1)

    def test_child_is_evaluated_and_holds_only_the_code_of_the_reply(self) -> None:
        llm = FakeLLM(["A better one:\n```python\nanswer = 4.5\n```\n"])
        child = self.child_of(self.run_quietly(self.problem, llm))
        self.assertEqual(child.code, "answer = 4.5\n")
        self.assertEqual(child.score, 4.5)

    def test_better_child_becomes_the_best_program(self) -> None:
        database = self.run_quietly(self.problem, FakeLLM(["answer = 4.5\n"]))
        self.assertIs(database.get_best_program(), self.child_of(database))

    def test_worse_child_does_not_become_the_best_program(self) -> None:
        database = self.run_quietly(self.problem, FakeLLM(["answer = 1.0\n"]))
        best_program = database.get_best_program()
        assert best_program is not None
        self.assertEqual(best_program.code, INITIAL_CODE)

    def test_failing_child_is_stored_with_the_failure_score(self) -> None:
        # The reply is not a program at all, so its evaluation fails
        database = self.run_quietly(self.problem, FakeLLM(["I cannot help with that."]))
        self.assertEqual(self.child_of(database).score, float("-inf"))
        best_program = database.get_best_program()
        assert best_program is not None
        self.assertEqual(best_program.code, INITIAL_CODE)

    def test_each_iteration_asks_the_llm_once_and_stores_one_child(self) -> None:
        llm = FakeLLM(["answer = 4.5\n"])
        database = self.run_quietly(self.problem, llm, iterations=5)
        self.assertEqual(len(llm.prompts), 5)
        # Five children plus the initial program
        self.assertEqual(len(database.programs), 6)

    def test_zero_iterations_only_evaluates_the_initial_program(self) -> None:
        llm = FakeLLM(["answer = 4.5\n"])
        database = self.run_quietly(self.problem, llm, iterations=0)
        self.assertEqual(llm.prompts, [])
        self.assertEqual(len(database.programs), 1)

    def test_negative_iterations_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.run_quietly(self.problem, FakeLLM(["answer = 4.5\n"]), iterations=-1)

    def test_best_program_is_the_best_of_all_iterations(self) -> None:
        # The best reply is neither the first nor the last one
        llm = FakeLLM(["answer = 4.0\n", "answer = 9.0\n", "answer = 5.0\n"])
        best_program = self.run_quietly(self.problem, llm, iterations=3).get_best_program()
        assert best_program is not None
        self.assertEqual(best_program.score, 9.0)

    def test_children_can_become_parents(self) -> None:
        # Parents are picked at random; fixing the seed makes the picks repeatable
        random.seed(0)
        database = self.run_quietly(self.problem, FakeLLM(["answer = 4.5\n"]), iterations=30)
        deepest_generation = max(program.generation for program in database.programs.values())
        # A generation above 1 means some child was itself made from a child
        self.assertGreater(deepest_generation, 1)

    def test_later_prompts_show_the_code_of_earlier_children(self) -> None:
        random.seed(0)
        llm = FakeLLM(["answer = 4.5\n"])
        self.run_quietly(self.problem, llm, iterations=30)
        # The first prompt can only show the initial program; a later one shows a child
        self.assertIn("answer = 3.5", llm.prompts[0])
        self.assertTrue(any("answer = 4.5" in prompt for prompt in llm.prompts[1:]))

    def test_failing_initial_program_stops_the_run(self) -> None:
        # Valid Python with a description, but it crashes as soon as it runs
        code = '"""Make answer as large as possible."""\n\nanswer = 1 / 0\n'
        with self.assertRaises(ValueError):
            self.run_quietly(Problem(code), FakeLLM(["answer = 4.5\n"]))


class TestRunScript(unittest.TestCase):
    """Checks on scripts/run.py, launched the way a user would launch it."""

    def launch(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """Run the script in a separate Python process and return its result."""
        return subprocess.run(
            [sys.executable, str(RUN_SCRIPT), *arguments],
            capture_output=True,
            text=True,
            # The script prints in UTF-8, so its output must be read back the same way
            encoding="utf-8",
            check=False,
        )

    def test_runs_the_example_problem(self) -> None:
        result = self.launch(
            str(EXAMPLE_FOLDER / "initial_program.py"),
            str(EXAMPLE_FOLDER / "evaluation.py"),
        )
        # Return code 0 is how a program tells the system it finished without error
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # The fake LLM's random search must beat the initial program and be reported
        self.assertIn("Best program: Program(", result.stdout)
        self.assertIn("generation=1", result.stdout)

    def test_iterations_option_sets_the_length_of_the_run(self) -> None:
        result = self.launch(
            str(EXAMPLE_FOLDER / "initial_program.py"),
            str(EXAMPLE_FOLDER / "evaluation.py"),
            "--iterations",
            "3",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Iteration 3/3", result.stdout)
        self.assertNotIn("Iteration 4", result.stdout)

    def test_characters_outside_the_system_encoding_are_printed(self) -> None:
        # A problem whose initial program has an arrow in it. The fake LLM's reply
        # fails here, so the initial program stays the best and its code is printed.
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            initial = folder / "initial.py"
            initial.write_text(
                '"""Make answer as large as possible."""\n\n# small → large\nanswer = 1\n',
                encoding="utf-8",
            )
            evaluation = folder / "evaluation.py"
            evaluation.write_text(
                "def evaluate(namespace):\n"
                "    if 'answer' not in namespace:\n"
                "        raise ValueError('answer must be ≥ 0, but is missing')\n"
                "    return float(namespace['answer'])\n",
                encoding="utf-8",
            )
            result = self.launch(str(initial), str(evaluation), "--iterations", "1")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # Both the failure message and the best program's code hold such a character
        self.assertIn("answer must be ≥ 0", result.stdout)
        self.assertIn("# small → large", result.stdout)

    def test_negative_iterations_are_reported(self) -> None:
        result = self.launch(
            str(EXAMPLE_FOLDER / "initial_program.py"),
            str(EXAMPLE_FOLDER / "evaluation.py"),
            "--iterations",
            "-1",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--iterations must be 0 or more", result.stderr)

    def test_missing_arguments_are_reported(self) -> None:
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage", result.stderr)


if __name__ == "__main__":
    unittest.main()
