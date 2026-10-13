"""Checks that Problem and load_problem turn the user's inputs into a usable problem."""

import sys
import tempfile
import unittest
from pathlib import Path

from my_alphaevolve.problem import Problem, load_problem, load_score_function

# A minimal valid initial program: a docstring describing the problem, then the code
INITIAL_CODE = '"""Make answer as large as possible."""\n\nanswer = 42\n'
# A minimal valid evaluation file: the score is the program's answer variable
EVALUATION_CODE = "def evaluate(namespace):\n    return float(namespace['answer'])\n"


class TestProblem(unittest.TestCase):
    """Checks on the Problem class and the description it reads from the initial program."""

    def test_description_is_the_docstring_at_the_top_of_the_initial_program(self) -> None:
        problem = Problem(INITIAL_CODE)
        self.assertEqual(problem.description, "Make answer as large as possible.")

    def test_description_keeps_every_line_of_a_long_docstring(self) -> None:
        code = '"""First line.\n\nSecond paragraph.\n"""\n\nanswer = 42\n'
        problem = Problem(code)
        self.assertEqual(problem.description, "First line.\n\nSecond paragraph.")

    def test_initial_programs_without_a_description_are_rejected(self) -> None:
        # Each entry: why the initial program is rejected -> its code
        bad_programs = {
            "no docstring": "answer = 42\n",
            "empty docstring": '""""""\n\nanswer = 42\n',
            "docstring only on a function": 'def f():\n    """Do it."""\n',
            "comment instead of docstring": "# Make answer large.\nanswer = 42\n",
            "not valid Python": '"""Make answer large."""\n\nanswer = (\n',
        }
        for reason, code in bad_programs.items():
            # subTest reports each bad program separately if several fail
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                Problem(code)


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

    def test_loads_the_initial_code_description_and_evaluation_path(self) -> None:
        initial = self.write_file("initial.py", INITIAL_CODE)
        evaluation = self.write_file("evaluation.py", EVALUATION_CODE)
        problem = load_problem(initial, evaluation)
        # The initial program is kept as text, exactly as written
        self.assertEqual(problem.initial_code, INITIAL_CODE)
        self.assertEqual(problem.description, "Make answer as large as possible.")
        # The evaluation file is kept as an absolute path, for the processes that will load it
        assert problem.evaluation_path is not None
        self.assertTrue(problem.evaluation_path.is_absolute())
        self.assertEqual(problem.evaluation_path, evaluation.resolve())

    def test_problem_made_without_an_evaluation_file_has_no_path(self) -> None:
        self.assertIsNone(Problem(INITIAL_CODE).evaluation_path)

    def test_score_function_is_the_evaluate_of_the_evaluation_file(self) -> None:
        evaluation = self.write_file("evaluation.py", EVALUATION_CODE)
        score_function = load_score_function(evaluation)
        self.assertEqual(score_function({"answer": 42}), 42.0)

    def test_missing_evaluation_file_raises_a_clear_error(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_score_function(self.folder / "does_not_exist.py")

    def test_missing_file_raises_a_clear_error(self) -> None:
        evaluation = self.write_file("evaluation.py", EVALUATION_CODE)
        with self.assertRaises(FileNotFoundError):
            load_problem(self.folder / "does_not_exist.py", evaluation)

    def test_evaluation_file_without_evaluate_raises_a_clear_error(self) -> None:
        initial = self.write_file("initial.py", INITIAL_CODE)
        evaluation = self.write_file("evaluation.py", "x = 1\n")
        with self.assertRaises(ValueError):
            load_problem(initial, evaluation)

    def test_initial_program_without_a_description_raises_a_clear_error(self) -> None:
        initial = self.write_file("initial.py", "answer = 42\n")
        evaluation = self.write_file("evaluation.py", EVALUATION_CODE)
        with self.assertRaises(ValueError):
            load_problem(initial, evaluation)

    def test_invisible_marker_at_the_start_of_the_initial_program_is_dropped(self) -> None:
        # "utf-8-sig" writes the invisible marker (BOM) that some Windows editors add
        initial = self.folder / "initial.py"
        initial.write_text(INITIAL_CODE, encoding="utf-8-sig")
        evaluation = self.write_file("evaluation.py", EVALUATION_CODE)
        self.assertEqual(load_problem(initial, evaluation).initial_code, INITIAL_CODE)

    def test_evaluation_file_can_import_a_file_next_to_it(self) -> None:
        self.write_file("my_alphaevolve_test_helper.py", "VALUE = 7.0\n")
        initial = self.write_file("initial.py", INITIAL_CODE)
        evaluation = self.write_file(
            "evaluation.py",
            "import my_alphaevolve_test_helper\n\n"
            "def evaluate(namespace):\n    return my_alphaevolve_test_helper.VALUE\n",
        )
        # Python remembers imported modules; forget this one once the test is over
        self.addCleanup(sys.modules.pop, "my_alphaevolve_test_helper", None)
        search_folders_before = list(sys.path)
        load_problem(initial, evaluation)
        self.assertEqual(load_score_function(evaluation)({}), 7.0)
        # Loading must leave Python's list of import folders as it found it
        self.assertEqual(sys.path, search_folders_before)


if __name__ == "__main__":
    unittest.main()
