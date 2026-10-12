"""Checks that load_problem turns the user's two files into a Problem."""

import sys
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

    def test_invisible_marker_at_the_start_of_the_initial_program_is_dropped(self) -> None:
        # "utf-8-sig" writes the invisible marker (BOM) that some Windows editors add
        initial = self.folder / "initial.py"
        initial.write_text("answer = 42\n", encoding="utf-8-sig")
        evaluation = self.write_file("evaluation.py", "def evaluate(namespace):\n    return 0.0\n")
        self.assertEqual(load_problem(initial, evaluation).initial_code, "answer = 42\n")

    def test_evaluation_file_can_import_a_file_next_to_it(self) -> None:
        self.write_file("my_alphaevolve_test_helper.py", "VALUE = 7.0\n")
        initial = self.write_file("initial.py", "answer = 42\n")
        evaluation = self.write_file(
            "evaluation.py",
            "import my_alphaevolve_test_helper\n\n"
            "def evaluate(namespace):\n    return my_alphaevolve_test_helper.VALUE\n",
        )
        # Python remembers imported modules; forget this one once the test is over
        self.addCleanup(sys.modules.pop, "my_alphaevolve_test_helper", None)
        search_folders_before = list(sys.path)
        problem = load_problem(initial, evaluation)
        self.assertEqual(problem.score_function({}), 7.0)
        # Loading must leave Python's list of import folders as it found it
        self.assertEqual(sys.path, search_folders_before)


if __name__ == "__main__":
    unittest.main()
