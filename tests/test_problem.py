"""Checks that Problem and load_problem turn the user's inputs into a usable problem."""

import sys
import tempfile
import unittest
from pathlib import Path

from my_alphaevolve.problem import (
    Problem,
    load_problem,
    load_score_function,
    package_name,
    read_requirements,
)

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
        search_folders_before = list(sys.path)
        load_problem(initial, evaluation)
        # The evaluation function reaches its helper...
        self.assertEqual(load_score_function(evaluation)({}), 7.0)
        # ...and loading leaves Python's import folders and import memory as it found them
        self.assertEqual(sys.path, search_folders_before)
        self.assertNotIn("my_alphaevolve_test_helper", sys.modules)

    def test_two_problems_can_each_have_a_helper_with_the_same_name(self) -> None:
        score_functions = []
        for value in (1.0, 2.0):
            # One sub-folder per problem, each with its own my_alphaevolve_test_helper.py
            folder = self.folder / f"problem_{value}"
            folder.mkdir()
            (folder / "my_alphaevolve_test_helper.py").write_text(
                f"VALUE = {value}\n", encoding="utf-8"
            )
            (folder / "evaluation.py").write_text(
                "from my_alphaevolve_test_helper import VALUE\n\n"
                "def evaluate(namespace):\n    return VALUE\n",
                encoding="utf-8",
            )
            score_functions.append(load_score_function(folder / "evaluation.py"))
        # Each problem must be scored with its own helper, not the first one loaded
        self.assertEqual(score_functions[0]({}), 1.0)
        self.assertEqual(score_functions[1]({}), 2.0)

    def test_helper_used_while_evaluating_still_works_after_being_forgotten(self) -> None:
        # Here evaluate reaches into the helper at the moment it is called, long after loading
        self.write_file("my_alphaevolve_test_helper.py", "def double(x):\n    return 2 * x\n")
        evaluation = self.write_file(
            "evaluation.py",
            "import my_alphaevolve_test_helper\n\n"
            "def evaluate(namespace):\n"
            "    return my_alphaevolve_test_helper.double(namespace['answer'])\n",
        )
        score_function = load_score_function(evaluation)
        self.assertNotIn("my_alphaevolve_test_helper", sys.modules)
        self.assertEqual(score_function({"answer": 21}), 42)

    def test_modules_imported_before_loading_are_not_forgotten(self) -> None:
        # The evaluation file imports json, which Python already knows; it must stay known
        import json

        evaluation = self.write_file(
            "evaluation.py", "import json\n\ndef evaluate(namespace):\n    return 0.0\n"
        )
        load_score_function(evaluation)
        self.assertIs(sys.modules["json"], json)

    def test_helpers_are_forgotten_even_when_the_evaluation_file_crashes(self) -> None:
        self.write_file("my_alphaevolve_test_helper.py", "VALUE = 7.0\n")
        evaluation = self.write_file(
            "evaluation.py", "import my_alphaevolve_test_helper\n\nresult = 1 / 0\n"
        )
        with self.assertRaises(ZeroDivisionError):
            load_score_function(evaluation)
        self.assertNotIn("my_alphaevolve_test_helper", sys.modules)


class TestRequirements(unittest.TestCase):
    """Checks on reading the packages programs may import."""

    def setUp(self) -> None:
        temporary_folder = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_folder.cleanup)
        self.folder = Path(temporary_folder.name)

    def write_requirements(self, content: str) -> None:
        (self.folder / "requirements.txt").write_text(content, encoding="utf-8")

    def test_no_file_means_no_requirements(self) -> None:
        self.assertEqual(read_requirements(self.folder), [])

    def test_comments_and_blank_lines_are_left_out(self) -> None:
        self.write_requirements("# Packages\nnumpy==2.5.4\n\nscipy>=1.18  # science\n")
        self.assertEqual(read_requirements(self.folder), ["numpy==2.5.4", "scipy>=1.18"])

    def test_pip_options_are_rejected(self) -> None:
        for option in ("--index-url https://example.com", "-r other.txt", "-e ."):
            with self.subTest(option=option), self.assertRaises(ValueError):
                self.write_requirements(f"numpy\n{option}\n")
                read_requirements(self.folder)

    def test_package_name_is_the_requirement_without_its_version(self) -> None:
        cases = {
            "numpy": "numpy",
            "numpy==2.5.4": "numpy",
            "scipy >= 1.18": "scipy",
            "requests[socks]~=2.32": "requests",
            "pywin32; sys_platform == 'win32'": "pywin32",
        }
        for requirement, name in cases.items():
            with self.subTest(requirement=requirement):
                self.assertEqual(package_name(requirement), name)

    def test_loaded_problem_knows_its_packages(self) -> None:
        self.write_requirements("numpy==2.5.4\nscipy==1.18.1\n")
        initial = self.folder / "initial.py"
        initial.write_text(INITIAL_CODE, encoding="utf-8")
        evaluation = self.folder / "evaluation.py"
        evaluation.write_text(EVALUATION_CODE, encoding="utf-8")
        self.assertEqual(load_problem(initial, evaluation).packages, ["numpy", "scipy"])

    def test_problem_without_requirements_has_no_packages(self) -> None:
        self.assertEqual(Problem(INITIAL_CODE).packages, [])


if __name__ == "__main__":
    unittest.main()
