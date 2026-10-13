"""Checks that programs survive being saved to disk and loaded back."""

import tempfile
import unittest
from pathlib import Path

from my_alphaevolve.program import Program
from my_alphaevolve.storage import RunStorage


def describe(program: Program) -> dict[str, object]:
    """Return everything about a program, so that two programs can be compared."""
    return program.to_dict()


class TestProgramDictionary(unittest.TestCase):
    """Checks on Program.to_dict and Program.from_dict."""

    def test_program_rebuilt_from_its_dictionary_is_identical(self) -> None:
        program = Program("x = 1\n", score=2.5, parent_id="some-parent", generation=3, iteration=7)
        rebuilt = Program.from_dict(program.to_dict())
        self.assertEqual(describe(rebuilt), describe(program))
        # In particular the id is kept, not replaced by a new one
        self.assertEqual(rebuilt.id, program.id)

    def test_new_programs_still_get_their_own_id(self) -> None:
        self.assertNotEqual(Program("x = 1").id, Program("x = 1").id)


class TestRunStorage(unittest.TestCase):
    """Checks on RunStorage, using a temporary folder."""

    def setUp(self) -> None:
        # Runs before every test: an empty folder that is deleted after the test
        temporary_folder = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_folder.cleanup)
        self.folder = Path(temporary_folder.name) / "run"
        self.storage = RunStorage(self.folder)

    def test_output_folder_is_created_with_the_folders_above_it(self) -> None:
        deep_folder = self.folder / "a" / "b"
        RunStorage(deep_folder)
        self.assertTrue(deep_folder.is_dir())

    def test_nothing_saved_yet_loads_as_an_empty_list(self) -> None:
        self.assertEqual(self.storage.load_programs(), [])

    def test_saved_programs_are_loaded_back_in_order(self) -> None:
        parent = Program("x = 1\n", score=1.0)
        child = Program("x = 2\n", score=2.0, parent_id=parent.id, generation=1, iteration=1)
        self.storage.append_program(parent)
        self.storage.append_program(child)
        loaded = self.storage.load_programs()
        self.assertEqual([describe(p) for p in loaded], [describe(parent), describe(child)])

    def test_each_program_is_one_line_of_the_file(self) -> None:
        # Code spanning several lines must still be stored on a single line
        self.storage.append_program(Program("x = 1\ny = 2\n", score=1.0))
        self.storage.append_program(Program("z = 3\n", score=2.0))
        lines = self.storage.programs_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)

    def test_special_values_survive_saving(self) -> None:
        # A failed program's score, characters outside plain English, and tricky code
        code = "# déjà vu → naïve\ntext = '{\"a\": 1}\\n'\n"
        program = Program(code, score=float("-inf"))
        self.storage.append_program(program)
        loaded = self.storage.load_programs()[0]
        self.assertEqual(loaded.code, code)
        self.assertEqual(loaded.score, float("-inf"))

    def test_another_storage_on_the_same_folder_sees_the_saved_programs(self) -> None:
        # This is what happens when a run is continued by a later launch
        self.storage.append_program(Program("x = 1\n", score=1.0))
        self.assertEqual(len(RunStorage(self.folder).load_programs()), 1)

    def test_last_line_cut_off_while_writing_is_dropped(self) -> None:
        self.storage.append_program(Program("x = 1\n", score=1.0))
        # Simulate a run that was killed in the middle of writing its second program
        with self.storage.programs_path.open("a", encoding="utf-8") as programs_file:
            programs_file.write('{"id": "abc", "code": "x = ')
        self.assertEqual(len(self.storage.load_programs()), 1)
        # A program saved afterwards must not be glued to the remains of the damaged line
        self.storage.append_program(Program("x = 3\n", score=3.0))
        self.assertEqual([p.score for p in self.storage.load_programs()], [1.0, 3.0])

    def test_damaged_line_in_the_middle_is_reported(self) -> None:
        self.storage.programs_path.write_text("this is not a program\n", encoding="utf-8")
        self.storage.append_program(Program("x = 1\n", score=1.0))
        with self.assertRaises(ValueError):
            self.storage.load_programs()

    def test_best_program_file_holds_the_latest_best_code(self) -> None:
        self.storage.save_best_program(Program("x = 1\n", score=1.0))
        self.storage.save_best_program(Program("x = 2\n", score=2.0, iteration=4))
        content = self.storage.best_program_path.read_text(encoding="utf-8")
        self.assertIn("x = 2\n", content)
        self.assertNotIn("x = 1\n", content)
        self.assertIn("score 2.0", content)
        self.assertIn("iteration 4", content)

    def test_best_program_file_is_still_a_valid_program(self) -> None:
        self.storage.save_best_program(Program("answer = 2\n", score=2.0))
        namespace: dict[str, object] = {}
        exec(self.storage.best_program_path.read_text(encoding="utf-8"), namespace)
        self.assertEqual(namespace["answer"], 2)


if __name__ == "__main__":
    unittest.main()
