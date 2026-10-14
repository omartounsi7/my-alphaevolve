"""Checks that Program and Database behave as intended."""

import random
import unittest

from my_alphaevolve.database import (
    DIVERSITY_REFERENCE_SIZE,
    Database,
    code_complexity,
    code_difference,
    feature_bin,
)
from my_alphaevolve.program import Program


class TestProgram(unittest.TestCase):
    """Checks on the Program class."""

    def test_each_program_gets_its_own_id(self) -> None:
        # Two programs must never share an id, even with identical code
        self.assertNotEqual(Program("x = 1").id, Program("x = 1").id)

    def test_defaults_describe_an_initial_program(self) -> None:
        # A program created from code alone has no score, no parent, generation 0
        program = Program("x = 1")
        self.assertIsNone(program.score)
        self.assertIsNone(program.parent_id)
        self.assertEqual(program.generation, 0)


class TestDatabase(unittest.TestCase):
    """Checks on the Database class."""

    def setUp(self) -> None:
        # Runs before every test: a database holding a parent and its better child
        self.database = Database()
        self.parent = Program("x = 1")
        self.child = Program("x = 2", parent_id=self.parent.id, generation=1)
        self.database.add(self.parent, 0.0)
        self.database.add(self.child, 1.0)

    def test_add_stores_the_results_on_the_program(self) -> None:
        self.assertEqual(self.parent.score, 0.0)
        self.assertEqual(self.child.score, 1.0)

    def test_get_finds_a_program_by_id(self) -> None:
        # Following a child's parent_id leads back to the parent object
        self.assertEqual(self.child.parent_id, self.parent.id)
        self.assertIs(self.database.get(self.parent.id), self.parent)

    def test_get_returns_none_for_an_unknown_id(self) -> None:
        self.assertIsNone(self.database.get("no-such-id"))

    def test_sample_returns_a_stored_program(self) -> None:
        for _ in range(20):
            self.assertIn(self.database.sample(), [self.parent, self.child])

    def test_sample_from_an_empty_database_raises_a_clear_error(self) -> None:
        with self.assertRaises(ValueError):
            Database().sample()

    def test_best_returns_the_highest_score(self) -> None:
        self.assertIs(self.database.get_best_program(), self.child)

    def test_best_of_an_empty_database_is_none(self) -> None:
        self.assertIsNone(Database().get_best_program())


def varied_database(seed: int = 0) -> tuple[Database, list[Program]]:
    """Return a database of 100 working programs of growing length, scoring 0 to 99."""
    database = Database(seed=seed)
    programs = [Program("x = 1\n" * (number + 1)) for number in range(100)]
    for number, program in enumerate(programs):
        database.add(program, float(number))
    return database, programs


class TestFeatures(unittest.TestCase):
    """Checks on the two features that place a program in the map."""

    def test_complexity_is_the_length_of_the_code(self) -> None:
        self.assertEqual(code_complexity("x = 1\n"), 6.0)

    def test_identical_code_has_no_difference(self) -> None:
        self.assertEqual(code_difference("x = 1\n", "x = 1\n"), 0.0)

    def test_difference_follows_openevolve_formula(self) -> None:
        # 3 more characters, 1 more line, and the characters "y" and "z" used by one side only
        difference = code_difference("x = 1\n", "x = 1\nyz\n")
        self.assertAlmostEqual(difference, 3 * 0.1 + 1 * 10 + 2 * 0.5)

    def test_bins_cut_the_range_in_equal_slices(self) -> None:
        bins = [feature_bin(value, 0.0, 10.0, 5) for value in (0.0, 1.9, 2.0, 9.9, 10.0)]
        self.assertEqual(bins, [0, 0, 1, 4, 4])

    def test_a_single_value_falls_in_the_middle_bin(self) -> None:
        self.assertEqual(feature_bin(3.0, 3.0, 3.0, 10), 5)

    def test_diversity_is_measured_against_the_first_working_programs(self) -> None:
        database = Database()
        for number in range(DIVERSITY_REFERENCE_SIZE + 5):
            database.add(Program(f"x = {number}\n"), 1.0)
        database.add(Program("failed\n"), float("-inf"))
        self.assertEqual(len(database.reference_codes), DIVERSITY_REFERENCE_SIZE)
        self.assertEqual(database.reference_codes[0], "x = 0\n")
        self.assertNotIn("failed\n", database.reference_codes)


class TestMapOfElites(unittest.TestCase):
    """Checks on the map of elites and on sample."""

    def test_better_program_takes_the_cell(self) -> None:
        # Two programs with the same features land in the same cell
        database = Database()
        worse, better = Program("x = 1\n"), Program("x = 2\n")
        database.add(worse, 1.0)
        database.add(better, 2.0)
        self.assertEqual(list(database.get_elites().values()), [better])

    def test_equal_score_does_not_take_the_cell(self) -> None:
        database = Database()
        first, second = Program("x = 1\n"), Program("x = 2\n")
        database.add(first, 1.0)
        database.add(second, 1.0)
        self.assertEqual(list(database.get_elites().values()), [first])

    def test_different_programs_occupy_different_cells(self) -> None:
        database, programs = varied_database()
        elites = database.get_elites()
        self.assertGreater(len(elites), 1)
        self.assertLessEqual(len(elites), database.bins_per_feature**2)
        self.assertIs(elites[max(elites)], programs[-1])

    def test_failed_programs_are_never_in_the_map(self) -> None:
        database = Database()
        database.add(Program("x = 1\n"), 1.0)
        failed = Program("x = (\n" * 50)
        database.add(failed, float("-inf"))
        self.assertNotIn(failed, database.get_elites().values())

    def test_sample_only_picks_elites(self) -> None:
        database, _ = varied_database()
        elites = set(program.id for program in database.get_elites().values())
        picks = {database.sample().id for _ in range(500)}
        self.assertEqual(picks, elites)

    def test_failed_program_is_picked_when_nothing_else_exists(self) -> None:
        database = Database()
        failed = Program("x = (")
        database.add(failed, float("-inf"))
        self.assertIs(database.sample(), failed)

    def test_same_seed_gives_the_same_picks(self) -> None:
        first_database, first_programs = varied_database(seed=7)
        second_database, second_programs = varied_database(seed=7)
        first_picks = [first_programs.index(first_database.sample()) for _ in range(50)]
        second_picks = [second_programs.index(second_database.sample()) for _ in range(50)]
        self.assertEqual(first_picks, second_picks)

    def test_seeding_the_shared_random_generator_does_not_change_the_picks(self) -> None:
        undisturbed, undisturbed_programs = varied_database()
        disturbed, disturbed_programs = varied_database()
        expected_picks = [undisturbed_programs.index(undisturbed.sample()) for _ in range(50)]
        picks = []
        for _ in range(50):
            # What an evaluated program might do between two picks of a parent
            random.seed(0)
            picks.append(disturbed_programs.index(disturbed.sample()))
        self.assertEqual(picks, expected_picks)

    def test_invalid_number_of_bins_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Database(bins_per_feature=0)


if __name__ == "__main__":
    unittest.main()
