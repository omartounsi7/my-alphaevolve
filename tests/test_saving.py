"""Checks that a run is saved as it goes, and can be stopped and continued."""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fake_llm_server import FakeLLMServer

from my_alphaevolve.database import Database
from my_alphaevolve.evaluator import InProcessEvaluator
from my_alphaevolve.llm import LLM, FakeLLM
from my_alphaevolve.loop import run_my_alphaevolve
from my_alphaevolve.problem import Problem
from my_alphaevolve.storage import RunStorage

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


class InterruptingLLM(LLM):
    """A fake LLM that behaves as if the user pressed Ctrl+C during one of its calls."""

    def __init__(self, reply: str, interrupt_on_call: int) -> None:
        # The reply given to every call that is not interrupted
        self.reply: str = reply
        # Which call is interrupted: 1 for the first, 2 for the second, ...
        self.interrupt_on_call: int = interrupt_on_call
        # How many calls have been made so far
        self.calls: int = 0

    def generate(self, prompt: str) -> str:
        """Return the reply, or raise KeyboardInterrupt on the chosen call."""
        self.calls += 1
        if self.calls == self.interrupt_on_call:
            raise KeyboardInterrupt
        return self.reply


class TestSavingARun(unittest.TestCase):
    """Checks on run_my_alphaevolve with an output folder."""

    def setUp(self) -> None:
        # Runs before every test: a problem, and an output folder deleted after the test
        self.problem = Problem(INITIAL_CODE)
        temporary_folder = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_folder.cleanup)
        self.output_folder = Path(temporary_folder.name) / "run"

    def run_quietly(self, llm: LLM, iterations: int, problem: Problem | None = None) -> Database:
        """Run the loop with the output folder, without showing what it prints."""
        # Send print() output into a throwaway variable instead of the screen
        with contextlib.redirect_stdout(io.StringIO()):
            return run_my_alphaevolve(
                problem or self.problem,
                llm,
                # Programs are scored inside this process: fine for trusted test code
                InProcessEvaluator(read_answer),
                iterations,
                self.output_folder,
            )

    def saved_iterations(self) -> list[int]:
        """Return the iteration number of every saved program, in file order."""
        return [p.iteration for p in RunStorage(self.output_folder).load_programs()]

    def best_program_file(self) -> str:
        """Return the content of the saved best program file."""
        return (self.output_folder / "best_program.py").read_text(encoding="utf-8")

    def test_every_program_is_saved_with_its_iteration(self) -> None:
        database = self.run_quietly(FakeLLM(["answer = 4.5\n"]), iterations=3)
        # The initial program is iteration 0; the children are 1, 2, 3
        self.assertEqual(self.saved_iterations(), [0, 1, 2, 3])
        saved_ids = [p.id for p in RunStorage(self.output_folder).load_programs()]
        self.assertEqual(saved_ids, list(database.programs))

    def test_best_program_file_follows_the_best_program(self) -> None:
        # The best reply is the second one; the third must not replace it
        llm = FakeLLM(["answer = 4.0\n", "answer = 9.0\n", "answer = 5.0\n"])
        self.run_quietly(llm, iterations=3)
        self.assertIn("answer = 9.0", self.best_program_file())
        self.assertIn("found at iteration 2", self.best_program_file())

    def test_best_program_file_holds_the_initial_program_when_nothing_beats_it(self) -> None:
        self.run_quietly(FakeLLM(["answer = 1.0\n"]), iterations=2)
        self.assertIn("answer = 3.5", self.best_program_file())

    def test_running_again_continues_the_saved_run(self) -> None:
        self.run_quietly(FakeLLM(["answer = 4.5\n"]), iterations=2)
        second_llm = FakeLLM(["answer = 6.0\n"])
        database = self.run_quietly(second_llm, iterations=3)
        # Three more iterations, numbered after the first two
        self.assertEqual(self.saved_iterations(), [0, 1, 2, 3, 4, 5])
        self.assertEqual(len(second_llm.prompts), 3)
        # The database of the second session holds the programs of both sessions
        self.assertEqual(len(database.programs), 6)
        best_program = database.get_best_program()
        assert best_program is not None
        self.assertEqual(best_program.score, 6.0)
        self.assertIn("answer = 6.0", self.best_program_file())

    def test_continuing_does_not_evaluate_the_initial_program_again(self) -> None:
        self.run_quietly(FakeLLM(["answer = 4.5\n"]), iterations=1)
        # The second session is given a broken initial program. A new run would
        # stop on it; a continued run never looks at it.
        broken_problem = Problem('"""Describe."""\n\nanswer = 1 / 0\n')
        database = self.run_quietly(FakeLLM(["answer = 4.5\n"]), 1, problem=broken_problem)
        self.assertEqual(len(database.programs), 3)

    def test_children_of_a_continued_run_descend_from_saved_programs(self) -> None:
        self.run_quietly(FakeLLM(["answer = 4.5\n"]), iterations=2)
        database = self.run_quietly(FakeLLM(["answer = 6.0\n"]), iterations=5)
        for program in database.programs.values():
            if program.parent_id is not None:
                # Every parent must be found, including those loaded from the file
                self.assertIsNotNone(database.get(program.parent_id))

    def test_stopping_with_ctrl_c_keeps_the_finished_iterations(self) -> None:
        # Ctrl+C arrives during the third iteration, of ten asked for
        llm = InterruptingLLM("answer = 4.5\n", interrupt_on_call=3)
        database = self.run_quietly(llm, iterations=10)
        # The run ended without an error, with two children in memory and on disk
        self.assertEqual(len(database.programs), 3)
        self.assertEqual(self.saved_iterations(), [0, 1, 2])

    def test_stopped_run_can_be_continued(self) -> None:
        self.run_quietly(InterruptingLLM("answer = 4.5\n", interrupt_on_call=3), iterations=10)
        self.run_quietly(FakeLLM(["answer = 4.5\n"]), iterations=2)
        self.assertEqual(self.saved_iterations(), [0, 1, 2, 3, 4])

    def test_nothing_is_written_without_an_output_folder(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            evaluator = InProcessEvaluator(read_answer)
            run_my_alphaevolve(self.problem, FakeLLM(["answer = 4.5\n"]), evaluator, 2)
        self.assertFalse(self.output_folder.exists())


class TestRunScriptOutput(unittest.TestCase):
    """Checks on the --output option of scripts/run.py."""

    def setUp(self) -> None:
        # Runs before every test: a stand-in LLM server, stopped after the test.
        # Any reply will do here: these tests are about files, not about scores.
        self.server = FakeLLMServer(["def search(f, low, high):\n    return list(high)\n"])
        self.addCleanup(self.server.stop)

    def launch(self, output_folder: Path, iterations: int) -> subprocess.CompletedProcess[str]:
        """Run the script on the example problem in a separate Python process."""
        return subprocess.run(
            [
                sys.executable,
                str(RUN_SCRIPT),
                str(EXAMPLE_FOLDER / "initial_program.py"),
                str(EXAMPLE_FOLDER / "evaluation.py"),
                "--model",
                "test-model",
                "--llm-url",
                self.server.url,
                "--iterations",
                str(iterations),
                "--output",
                str(output_folder),
            ],
            capture_output=True,
            text=True,
            # The script prints in UTF-8, so its output must be read back the same way
            encoding="utf-8",
            check=False,
        )

    def test_output_option_saves_the_run_and_a_second_launch_continues_it(self) -> None:
        with tempfile.TemporaryDirectory() as folder_name:
            output_folder = Path(folder_name) / "run"
            first = self.launch(output_folder, iterations=2)
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            self.assertIn("Iteration 2/2", first.stdout)
            self.assertTrue((output_folder / "best_program.py").is_file())

            second = self.launch(output_folder, iterations=3)
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            self.assertIn("Continuing the run", second.stdout)
            self.assertIn("Iteration 5/5", second.stdout)
            self.assertEqual(len(RunStorage(output_folder).load_programs()), 6)


if __name__ == "__main__":
    unittest.main()
