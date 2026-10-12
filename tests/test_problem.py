"""Checks that load_problem turns the user's two files into a Problem."""

import tempfile
import unittest
from pathlib import Path

from my_alphaevolve.problem import load_problem


class TestLoadProblem(unittest.TestCase):
    """Checks on load_problem, using small files written to a temporary folder."""

    def setUp(self) -> None:
        # Runs before every test: an empty folder that is deleted after the test
        temporary_folder = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_folder.cleanup)
        self.folder = Path(temporary_folder.name)

    def write_file(self, name: str, content: str) -> Path:
        """Create a file in the temporary folder and return its path."""
        path = self.folder / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_the_initial_code_and_the_evaluate_function(self) -> None:
        initial = self.write_file("initial.py", "answer = 42\n")
        evaluation = self.write_file(
            "evaluation.py",
            "def evaluate(namespace):\n    return float(namespace['answer'])\n",
        )
        problem = load_problem(initial, evaluation)
        # The initial program is kept as text, exactly as written
        self.assertEqual(problem.initial_code, "answer = 42\n")
        # The score function is the user's evaluate, ready to be called
        self.assertEqual(problem.score_function({"answer": 42}), 42.0)

    def test_missing_file_raises_a_clear_error(self) -> None:
        evaluation = self.write_file("evaluation.py", "def evaluate(namespace):\n    return 0.0\n")
        with self.assertRaises(FileNotFoundError):
            load_problem(self.folder / "does_not_exist.py", evaluation)

    def test_evaluation_file_without_evaluate_raises_a_clear_error(self) -> None:
        initial = self.write_file("initial.py", "answer = 42\n")
        evaluation = self.write_file("evaluation.py", "x = 1\n")
        with self.assertRaises(ValueError):
            load_problem(initial, evaluation)


if __name__ == "__main__":
    unittest.main()
