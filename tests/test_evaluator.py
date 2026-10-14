"""Checks on scoring programs, and on the Docker evaluator, using tiny made-up problems."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from docker_check import docker_is_available

from my_alphaevolve.evaluator import DockerEvaluator, docker_image_tag, score_program
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


class TestScoreProgram(unittest.TestCase):
    """Checks on score_program, which every evaluation ends up calling."""

    def test_score_comes_from_the_score_function(self) -> None:
        self.assertEqual(score_program("answer = 3.5\n", read_answer), 3.5)

    def test_whole_number_scores_are_returned_as_decimals(self) -> None:
        score = score_program("x = 1\n", always_returns(3))
        self.assertEqual(score, 3.0)
        self.assertIsInstance(score, float)

    def test_each_program_starts_from_an_empty_namespace(self) -> None:
        score_program("answer = 3.5\n", read_answer)
        with self.assertRaises(KeyError):
            score_program("x = 1\n", read_answer)

    def test_failing_programs_raise_an_error(self) -> None:
        bad_programs = {
            "syntax error": "answer = (\n",
            "crash while running": "answer = 1 / 0\n",
            "expected name missing": "x = 1\n",
            "score function rejects the answer": "answer = 'text'\n",
        }
        for reason, code in bad_programs.items():
            with (
                self.subTest(reason=reason),
                self.assertRaises((SyntaxError, ZeroDivisionError, KeyError, ValueError)),
            ):
                score_program(code, read_answer)

    def test_invalid_scores_raise_an_error(self) -> None:
        invalid_scores: list[Any] = [float("nan"), float("inf"), None, "great", True, [1.0]]
        for invalid_score in invalid_scores:
            with self.subTest(invalid_score=invalid_score), self.assertRaises(ValueError):
                score_program("x = 1\n", always_returns(invalid_score))


class TestContainerWorker(unittest.TestCase):
    """Checks on the script that runs inside the container, run here without Docker."""

    def setUp(self) -> None:
        temporary_folder = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_folder.cleanup)
        self.evaluation_path = Path(temporary_folder.name) / "evaluation.py"
        self.evaluation_path.write_text(
            "def evaluate(namespace):\n    return float(namespace['answer'])\n", encoding="utf-8"
        )

    def run_worker(self, code: str) -> subprocess.CompletedProcess[str]:
        """Run the worker on a program, as the container does."""
        return subprocess.run(
            [sys.executable, "-m", "my_alphaevolve.container_worker", str(self.evaluation_path)],
            input=code,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_score_is_the_last_line_of_the_output(self) -> None:
        result = self.run_worker("answer = 2.5\n")
        self.assertEqual(json.loads(result.stdout.splitlines()[-1]), {"status": "ok", "score": 2.5})

    def test_failure_is_reported_with_its_reason(self) -> None:
        result = self.run_worker("answer = 1 / 0\n")
        reply = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(reply["status"], "error")
        self.assertIn("ZeroDivisionError", reply["message"])

    def test_what_the_program_prints_does_not_mix_with_the_result(self) -> None:
        result = self.run_worker("print('hello')\nanswer = 2.5\n")
        self.assertEqual(result.stdout.strip().splitlines(), ['{"status": "ok", "score": 2.5}'])
        self.assertIn("hello", result.stderr)


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class TestDockerEvaluator(unittest.TestCase):
    """Checks on DockerEvaluator. Each evaluation starts a real container."""

    def setUp(self) -> None:
        temporary_folder = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_folder.cleanup)
        self.folder = Path(temporary_folder.name)
        (self.folder / "my_alphaevolve_evaluator_test_helper.py").write_text(
            "BONUS = 1.0\n", encoding="utf-8"
        )
        self.evaluation_path = self.folder / "evaluation.py"
        self.evaluation_path.write_text(EVALUATION_CODE, encoding="utf-8")
        self.evaluator = DockerEvaluator(self.evaluation_path, timeout_seconds=60.0)

    def execute_quietly(self, code: str, evaluator: DockerEvaluator | None = None) -> float:
        """Evaluate a piece of code without showing the failure messages the parent prints."""
        with contextlib.redirect_stdout(io.StringIO()):
            return (evaluator or self.evaluator).execute(Program(code))

    def failure_message(self, code: str) -> str:
        """Evaluate a piece of code and return what the evaluator printed."""
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.evaluator.execute(Program(code))
        return printed.getvalue()

    def test_score_comes_from_the_evaluation_file_and_its_helper(self) -> None:
        self.assertEqual(self.evaluator.execute(Program("answer = 9\n")), 4.0)

    def test_failing_programs_get_the_failure_score(self) -> None:
        bad_programs = {
            "crash while running": "answer = 1 / 0\n",
            "program ends its process": "import sys\nsys.exit(0)\n",
        }
        for reason, code in bad_programs.items():
            with self.subTest(reason=reason):
                self.assertEqual(self.execute_quietly(code), self.evaluator.failure_score)

    def test_program_has_no_network(self) -> None:
        code = "import socket\nsocket.create_connection(('1.1.1.1', 53), timeout=3)\nanswer = 9\n"
        self.assertEqual(self.execute_quietly(code), self.evaluator.failure_score)

    def test_program_cannot_write_outside_its_temporary_folder(self) -> None:
        message = self.failure_message("open('/problem/evaluation.py', 'w').write('x')\n")
        self.assertIn("Read-only file system", message)
        self.assertEqual(self.evaluation_path.read_text(encoding="utf-8"), EVALUATION_CODE)

    def test_program_may_write_in_its_temporary_folder(self) -> None:
        code = "open('/tmp/notes.txt', 'w').write('x')\nanswer = 9\n"
        self.assertEqual(self.evaluator.execute(Program(code)), 4.0)

    def test_program_that_never_ends_is_stopped_with_everything_it_started(self) -> None:
        impatient_evaluator = DockerEvaluator(self.evaluation_path, timeout_seconds=5.0)
        code = (
            "import subprocess, sys\n"
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])\n"
            "while True:\n    pass\n"
        )
        self.assertEqual(
            self.execute_quietly(code, impatient_evaluator), impatient_evaluator.failure_score
        )
        running = subprocess.run(
            ["docker", "ps", "--quiet", "--filter", f"ancestor={impatient_evaluator.image}"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        self.assertEqual(running.strip(), "")

    def test_program_using_too_much_memory_is_stopped(self) -> None:
        message = self.failure_message("data = bytearray(3 * 1024 ** 3)\n")
        self.assertIn("too much memory", message)

    def test_characters_outside_plain_english_survive(self) -> None:
        message = self.failure_message("x = 1\n")
        self.assertIn("answer → a number", message)

    def test_time_limit_must_be_above_zero(self) -> None:
        with self.assertRaises(ValueError):
            DockerEvaluator(self.evaluation_path, timeout_seconds=0)


class TestDockerImageTag(unittest.TestCase):
    """Checks that the image is rebuilt exactly when the packages change."""

    def test_same_requirements_give_the_same_image(self) -> None:
        self.assertEqual(docker_image_tag(["numpy==2.5.4"]), docker_image_tag(["numpy==2.5.4"]))

    def test_different_requirements_give_a_different_image(self) -> None:
        tags = {
            docker_image_tag([]),
            docker_image_tag(["numpy==2.5.4"]),
            docker_image_tag(["numpy==2.5.3"]),
        }
        self.assertEqual(len(tags), 3)


if __name__ == "__main__":
    unittest.main()
