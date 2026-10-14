"""Checks that the main loop and the command-line script run from start to finish."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from docker_check import docker_is_available
from doubles import InProcessEvaluator
from fake_llm_server import FakeLLMServer, prepared_llm, serve

from my_alphaevolve.database import Database
from my_alphaevolve.llm import LLM, LLMError
from my_alphaevolve.loop import MAX_LLM_FAILURES_IN_A_ROW, run_my_alphaevolve
from my_alphaevolve.problem import Problem
from my_alphaevolve.program import Program

# The top folder of the repository, found relative to this test file
REPOSITORY_FOLDER = Path(__file__).parent.parent
# The script a user launches, and the example problem it is tested with
RUN_SCRIPT = REPOSITORY_FOLDER / "scripts" / "run.py"
EXAMPLE_FOLDER = REPOSITORY_FOLDER / "examples" / "function_minimization"

# What the stand-in LLM server answers in the script tests: a program for the
# function-minimization example that tries many random points and keeps the lowest
RANDOM_SEARCH_REPLY = """\
import random


def search(target_function, lower_bounds, upper_bounds):
    generator = random.Random(0)
    points = [
        [generator.uniform(low, high) for low, high in zip(lower_bounds, upper_bounds)]
        for _ in range(2000)
    ]
    return min(points, key=target_function)
"""


# A minimal valid initial program: a description, then an answer that scores 3.5
INITIAL_CODE = '"""Make answer as large as possible."""\n\nanswer = 3.5\n'


def read_answer(namespace: dict[str, Any]) -> float:
    """Score a program by the value of the variable called answer that it defines."""
    return float(namespace["answer"])


class UnreliableLLM(LLM):
    """A fake LLM that fails on chosen calls, as a real one does when the network drops."""

    def __init__(self, reply: str, failing_calls: set[int]) -> None:
        # The reply given to every call that does not fail
        self.reply: str = reply
        # Which calls fail: 1 for the first, 2 for the second, ...
        self.failing_calls: set[int] = failing_calls
        # How many calls have been made so far
        self.calls: int = 0

    def generate(self, prompt: str) -> str:
        """Return the reply, or raise LLMError on the chosen calls."""
        self.calls += 1
        if self.calls in self.failing_calls:
            raise LLMError("prepared failure")
        return self.reply


class TestRunMyAlphaevolve(unittest.TestCase):
    """Checks on run_my_alphaevolve, using a tiny made-up problem."""

    def setUp(self) -> None:
        # Runs before every test: a problem whose initial program scores 3.5
        self.problem = Problem(INITIAL_CODE)

    def run_quietly(self, problem: Problem, llm: LLM, iterations: int = 1) -> Database:
        """Run the loop without showing what it prints, and return its database."""
        # Send print() output into a throwaway variable instead of the screen
        with contextlib.redirect_stdout(io.StringIO()):
            # Programs are scored inside this process: fast, and fine for trusted test code
            # seed=0 makes the random choice of parents the same on every test run
            return run_my_alphaevolve(
                problem, llm, InProcessEvaluator(read_answer), iterations, seed=0
            )

    def parent_positions(self, database: Database) -> list[int]:
        """Return, for each child in order, the position of its parent in the database."""
        program_ids = list(database.programs)
        return [
            program_ids.index(program.parent_id)
            for program in database.programs.values()
            if program.parent_id is not None
        ]

    def child_of(self, database: Database) -> Program:
        """Return the one program in the database that has a parent."""
        children = [p for p in database.programs.values() if p.parent_id is not None]
        self.assertEqual(len(children), 1)
        return children[0]

    def test_llm_receives_a_prompt_with_the_description_and_the_parent_code(self) -> None:
        server = serve(self, ["answer = 4.5\n"])
        llm = server.llm()
        self.run_quietly(self.problem, llm)
        self.assertEqual(len(server.prompts), 1)
        prompt = server.prompts[0]
        self.assertIn("Problem description:\nMake answer as large as possible.", prompt)
        self.assertIn("answer = 3.5", prompt)

    def test_prompt_names_the_packages_programs_may_import(self) -> None:
        server = serve(self, ["answer = 4.5\n"])
        self.run_quietly(Problem(INITIAL_CODE, packages=["numpy"]), server.llm())
        self.assertIn("standard library and these packages: numpy.", server.prompts[0])

    def test_database_holds_the_initial_program_and_its_child(self) -> None:
        database = self.run_quietly(self.problem, prepared_llm(self, ["answer = 4.5\n"]))
        self.assertEqual(len(database.programs), 2)
        child = self.child_of(database)
        # The child's parent is the initial program, which has no parent itself
        parent = database.get(child.parent_id or "")
        assert parent is not None
        self.assertEqual(parent.code, INITIAL_CODE)
        self.assertEqual(parent.score, 3.5)
        self.assertEqual(child.generation, 1)

    def test_child_is_evaluated_and_holds_only_the_code_of_the_reply(self) -> None:
        server = serve(self, ["A better one:\n```python\nanswer = 4.5\n```\n"])
        llm = server.llm()
        child = self.child_of(self.run_quietly(self.problem, llm))
        self.assertEqual(child.code, "answer = 4.5\n")
        self.assertEqual(child.score, 4.5)

    def test_better_child_becomes_the_best_program(self) -> None:
        database = self.run_quietly(self.problem, prepared_llm(self, ["answer = 4.5\n"]))
        self.assertIs(database.get_best_program(), self.child_of(database))

    def test_worse_child_does_not_become_the_best_program(self) -> None:
        database = self.run_quietly(self.problem, prepared_llm(self, ["answer = 1.0\n"]))
        best_program = database.get_best_program()
        assert best_program is not None
        self.assertEqual(best_program.code, INITIAL_CODE)

    def test_failing_child_is_stored_with_the_failure_score(self) -> None:
        # The reply is not a program at all, so its evaluation fails
        database = self.run_quietly(self.problem, prepared_llm(self, ["I cannot help with that."]))
        self.assertEqual(self.child_of(database).score, float("-inf"))
        best_program = database.get_best_program()
        assert best_program is not None
        self.assertEqual(best_program.code, INITIAL_CODE)

    def test_each_iteration_asks_the_llm_once_and_stores_one_child(self) -> None:
        server = serve(self, ["answer = 4.5\n"])
        llm = server.llm()
        database = self.run_quietly(self.problem, llm, iterations=5)
        self.assertEqual(len(server.prompts), 5)
        # Five children plus the initial program
        self.assertEqual(len(database.programs), 6)

    def test_zero_iterations_only_evaluates_the_initial_program(self) -> None:
        server = serve(self, ["answer = 4.5\n"])
        llm = server.llm()
        database = self.run_quietly(self.problem, llm, iterations=0)
        self.assertEqual(server.prompts, [])
        self.assertEqual(len(database.programs), 1)

    def test_negative_iterations_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.run_quietly(self.problem, prepared_llm(self, ["answer = 4.5\n"]), iterations=-1)

    def test_best_program_is_the_best_of_all_iterations(self) -> None:
        # The best reply is neither the first nor the last one
        server = serve(self, ["answer = 4.0\n", "answer = 9.0\n", "answer = 5.0\n"])
        llm = server.llm()
        best_program = self.run_quietly(self.problem, llm, iterations=3).get_best_program()
        assert best_program is not None
        self.assertEqual(best_program.score, 9.0)

    def test_children_can_become_parents(self) -> None:
        database = self.run_quietly(
            self.problem, prepared_llm(self, ["answer = 4.5\n"]), iterations=30
        )
        deepest_generation = max(program.generation for program in database.programs.values())
        # A generation above 1 means some child was itself made from a child
        self.assertGreater(deepest_generation, 1)

    def test_same_seed_gives_the_same_choice_of_parents(self) -> None:
        first = self.run_quietly(
            self.problem, prepared_llm(self, ["answer = 4.5\n"]), iterations=30
        )
        second = self.run_quietly(
            self.problem, prepared_llm(self, ["answer = 4.5\n"]), iterations=30
        )
        self.assertEqual(self.parent_positions(first), self.parent_positions(second))

    def test_program_calling_random_seed_does_not_change_the_choice_of_parents(self) -> None:
        # Search code written by an LLM often seeds the shared random generator.
        # Here the programs even run inside this process, the worst case.
        seeding_reply = "import random\nrandom.seed(0)\nanswer = 4.5\n"
        normal = self.run_quietly(
            self.problem, prepared_llm(self, ["answer = 4.5\n"]), iterations=30
        )
        seeding = self.run_quietly(self.problem, prepared_llm(self, [seeding_reply]), iterations=30)
        self.assertEqual(self.parent_positions(normal), self.parent_positions(seeding))

    def test_later_prompts_show_the_code_of_earlier_children(self) -> None:
        server = serve(self, ["answer = 4.5\n"])
        llm = server.llm()
        self.run_quietly(self.problem, llm, iterations=30)
        # The first prompt can only show the initial program; a later one shows a child
        self.assertIn("answer = 3.5", server.prompts[0])
        self.assertTrue(any("answer = 4.5" in prompt for prompt in server.prompts[1:]))

    def test_failing_initial_program_stops_the_run(self) -> None:
        # Valid Python with a description, but it crashes as soon as it runs
        code = '"""Make answer as large as possible."""\n\nanswer = 1 / 0\n'
        with self.assertRaises(ValueError):
            self.run_quietly(Problem(code), prepared_llm(self, ["answer = 4.5\n"]))

    def test_iteration_without_a_reply_is_skipped_and_the_run_carries_on(self) -> None:
        # The LLM fails on its second call only
        llm = UnreliableLLM("answer = 4.5\n", failing_calls={2})
        database = self.run_quietly(self.problem, llm, iterations=4)
        self.assertEqual(llm.calls, 4)
        # Three children plus the initial program: iteration 2 produced nothing
        self.assertEqual(len(database.programs), 4)
        iterations_with_a_child = sorted(p.iteration for p in database.programs.values())
        self.assertEqual(iterations_with_a_child, [0, 1, 3, 4])

    def test_run_stops_when_the_llm_keeps_failing(self) -> None:
        # The LLM fails on every call from the second one on
        llm = UnreliableLLM("answer = 4.5\n", failing_calls=set(range(2, 100)))
        database = self.run_quietly(self.problem, llm, iterations=50)
        # One success, then three failures in a row end the run: 4 calls, not 50
        self.assertEqual(llm.calls, 1 + MAX_LLM_FAILURES_IN_A_ROW)
        self.assertEqual(len(database.programs), 2)

    def test_failures_that_are_not_in_a_row_do_not_stop_the_run(self) -> None:
        # Every other call fails: never three in a row
        llm = UnreliableLLM("answer = 4.5\n", failing_calls=set(range(1, 100, 2)))
        self.run_quietly(self.problem, llm, iterations=10)
        self.assertEqual(llm.calls, 10)


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class TestRunScript(unittest.TestCase):
    """Checks on scripts/run.py, launched the way a user would launch it.

    The script talks to a stand-in LLM server started by each test, so the
    whole path is exercised: the real LLM class, the real evaluator, the loop.
    """

    def setUp(self) -> None:
        # Runs before every test: a stand-in LLM server, stopped after the test
        self.server = FakeLLMServer([RANDOM_SEARCH_REPLY])
        self.addCleanup(self.server.stop)

    def launch(
        self,
        *arguments: str,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run the script in a separate Python process and return its result."""
        return subprocess.run(
            [sys.executable, str(RUN_SCRIPT), *arguments],
            capture_output=True,
            text=True,
            # The script prints in UTF-8, so its output must be read back the same way
            encoding="utf-8",
            check=False,
            # None means "the same environment variables as this process"
            env=environment,
        )

    def launch_example(
        self,
        *arguments: str,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run the script on the example problem, using the stand-in LLM server."""
        return self.launch(
            str(EXAMPLE_FOLDER / "initial_program.py"),
            str(EXAMPLE_FOLDER / "evaluation.py"),
            "--model",
            "test-model",
            "--llm-url",
            self.server.url,
            *arguments,
            environment=environment,
        )

    def test_runs_the_example_problem(self) -> None:
        result = self.launch_example("--iterations", "2")
        # Return code 0 is how a program tells the system it finished without error
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # The server's random search must beat the initial program and be reported
        self.assertIn("Best program: Program(", result.stdout)
        self.assertIn("generation=1", result.stdout)

    def test_llm_is_asked_with_the_chosen_model_and_a_prompt_about_the_problem(self) -> None:
        self.launch_example("--iterations", "1")
        self.assertEqual(len(self.server.requests), 1)
        body = self.server.requests[0]["body"]
        self.assertEqual(body["model"], "test-model")
        self.assertIn("lower_bounds", body["messages"][0]["content"])

    def test_api_key_is_read_from_the_chosen_environment_variable(self) -> None:
        # os.environ holds this process's environment variables; add one for the script
        environment = dict(os.environ, MY_TEST_KEY="secret-from-the-environment")
        self.launch_example(
            "--iterations", "1", "--api-key-env", "MY_TEST_KEY", environment=environment
        )
        authorization = self.server.requests[0]["authorization"]
        self.assertEqual(authorization, "Bearer secret-from-the-environment")

    def test_api_key_never_appears_in_the_output(self) -> None:
        environment = dict(os.environ, MY_TEST_KEY="secret-from-the-environment")
        result = self.launch_example(
            "--iterations", "1", "--api-key-env", "MY_TEST_KEY", environment=environment
        )
        self.assertNotIn("secret-from-the-environment", result.stdout + result.stderr)

    def test_reply_limit_option_is_sent_and_zero_removes_it(self) -> None:
        self.launch_example("--iterations", "1", "--max-reply-tokens", "77")
        self.launch_example("--iterations", "1", "--max-reply-tokens", "0")
        self.assertEqual(self.server.requests[0]["body"]["max_tokens"], 77)
        self.assertNotIn("max_tokens", self.server.requests[1]["body"])

    def test_seed_option_is_accepted(self) -> None:
        result = self.launch_example("--iterations", "2", "--seed", "7")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Iteration 2/2", result.stdout)

    def test_programs_run_in_docker(self) -> None:
        result = self.launch(
            str(EXAMPLE_FOLDER / "initial_program.py"),
            str(EXAMPLE_FOLDER / "evaluation.py"),
            "--model",
            "test-model",
            "--llm-url",
            self.server.url,
            "--iterations",
            "1",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Evaluator: a Docker container per program", result.stdout)
        self.assertIn("Iteration 1/1: child score=1.8", result.stdout)

    def test_iterations_option_sets_the_length_of_the_run(self) -> None:
        result = self.launch_example("--iterations", "3")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Iteration 3/3", result.stdout)
        self.assertNotIn("Iteration 4", result.stdout)

    def test_characters_outside_the_system_encoding_are_printed(self) -> None:
        # A problem whose initial program has an arrow in it. The server's reply
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
            result = self.launch(
                str(initial),
                str(evaluation),
                "--model",
                "test-model",
                "--llm-url",
                self.server.url,
                "--iterations",
                "1",
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # Both the failure message and the best program's code hold such a character
        self.assertIn("answer must be ≥ 0", result.stdout)
        self.assertIn("# small → large", result.stdout)

    def test_negative_iterations_are_reported(self) -> None:
        result = self.launch_example("--iterations", "-1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--iterations must be 0 or more", result.stderr)

    def test_missing_model_is_reported(self) -> None:
        result = self.launch(
            str(EXAMPLE_FOLDER / "initial_program.py"),
            str(EXAMPLE_FOLDER / "evaluation.py"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--model", result.stderr)

    def test_missing_arguments_are_reported(self) -> None:
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage", result.stderr)


if __name__ == "__main__":
    unittest.main()
