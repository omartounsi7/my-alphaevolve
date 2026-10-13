"""Checks that Program and Database behave as intended."""

import random
import unittest

from my_alphaevolve.database import Database
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


def ranked_database(archive_size: int, exploitation_ratio: float) -> tuple[Database, list[Program]]:
    """Return a database of 100 working programs scoring 0 to 99, and those programs.

    The program at position n of the list has the score n, so the best ones are at the end.
    """
    # seed=0 makes the random picks the same on every test run
    database = Database(archive_size, exploitation_ratio, seed=0)
    programs = [Program(f"x = {number}") for number in range(100)]
    for number, program in enumerate(programs):
        database.add(program, float(number))
    return database, programs


class TestTopPrograms(unittest.TestCase):
    """Checks on get_working_programs and get_top_programs."""

    def setUp(self) -> None:
        # Runs before every test: three working programs and one failed one
        self.database = Database()
        self.low = Program("x = 1")
        self.high = Program("x = 2")
        self.failed = Program("x = (")
        self.middle = Program("x = 3")
        self.database.add(self.low, 1.0)
        self.database.add(self.high, 3.0)
        self.database.add(self.failed, float("-inf"))
        self.database.add(self.middle, 2.0)

    def test_working_programs_leave_out_the_failed_ones(self) -> None:
        self.assertEqual(self.database.get_working_programs(), [self.low, self.high, self.middle])

    def test_top_programs_are_the_best_ones_best_first(self) -> None:
        self.assertEqual(self.database.get_top_programs(2), [self.high, self.middle])

    def test_asking_for_more_than_there_are_returns_all_working_programs(self) -> None:
        top_programs = self.database.get_top_programs(10)
        self.assertEqual(top_programs, [self.high, self.middle, self.low])

    def test_programs_with_the_same_score_keep_the_order_they_were_added_in(self) -> None:
        database = Database()
        first, second = Program("x = 1"), Program("x = 2")
        database.add(first, 5.0)
        database.add(second, 5.0)
        self.assertEqual(database.get_top_programs(2), [first, second])


class TestSampling(unittest.TestCase):
    """Checks on how sample picks parents."""

    def test_failed_programs_are_never_picked_when_a_working_one_exists(self) -> None:
        database = Database()
        working = Program("x = 1")
        database.add(working, 1.0)
        for _ in range(20):
            database.add(Program("x = ("), float("-inf"))
        for _ in range(200):
            self.assertIs(database.sample(), working)

    def test_failed_program_is_picked_when_nothing_else_exists(self) -> None:
        database = Database()
        failed = Program("x = (")
        database.add(failed, float("-inf"))
        self.assertIs(database.sample(), failed)

    def test_pure_exploitation_only_picks_from_the_archive(self) -> None:
        database, programs = ranked_database(archive_size=10, exploitation_ratio=1.0)
        # The archive is the ten best programs: the last ten of the list
        archive = programs[-10:]
        picked = {database.sample().id for _ in range(500)}
        self.assertTrue(picked <= {program.id for program in archive})
        # With 500 picks among 10 programs, every one of them should have come up
        self.assertEqual(len(picked), 10)

    def test_pure_exploration_picks_programs_outside_the_archive_too(self) -> None:
        database, programs = ranked_database(archive_size=10, exploitation_ratio=0.0)
        archive_ids = {program.id for program in programs[-10:]}
        picks = [database.sample().id for _ in range(2000)]
        share_from_archive = sum(pick in archive_ids for pick in picks) / len(picks)
        # 10 of the 100 programs are in the archive, so about 10% of uniform picks are
        self.assertAlmostEqual(share_from_archive, 0.10, delta=0.04)

    def test_default_mix_favours_the_archive(self) -> None:
        database, programs = ranked_database(archive_size=10, exploitation_ratio=0.7)
        archive_ids = {program.id for program in programs[-10:]}
        picks = [database.sample().id for _ in range(5000)]
        share_from_archive = sum(pick in archive_ids for pick in picks) / len(picks)
        # 70% exploitation, plus the 10% of the remaining 30% that lands in the archive anyway
        self.assertAlmostEqual(share_from_archive, 0.73, delta=0.04)

    def test_same_seed_gives_the_same_picks(self) -> None:
        first_database, first_programs = ranked_database(10, 0.7)
        second_database, second_programs = ranked_database(10, 0.7)
        # Programs get new ids each time, so picks are compared by position in the list
        first_picks = [first_programs.index(first_database.sample()) for _ in range(50)]
        second_picks = [second_programs.index(second_database.sample()) for _ in range(50)]
        self.assertEqual(first_picks, second_picks)

    def test_databases_without_a_seed_do_not_pick_alike(self) -> None:
        programs = [Program(f"x = {number}") for number in range(100)]
        sequences = []
        for _ in range(2):
            database = Database(exploitation_ratio=0.0)
            for program in programs:
                database.add(program, 1.0)
            sequences.append([programs.index(database.sample()) for _ in range(50)])
        # Two sequences of 50 picks among 100 programs agreeing by chance is unthinkable
        self.assertNotEqual(sequences[0], sequences[1])

    def test_seeding_the_shared_random_generator_does_not_change_the_picks(self) -> None:
        undisturbed, undisturbed_programs = ranked_database(10, 0.7)
        disturbed, disturbed_programs = ranked_database(10, 0.7)
        expected_picks = [undisturbed_programs.index(undisturbed.sample()) for _ in range(50)]
        picks = []
        for _ in range(50):
            # What an evaluated program might do between two picks of a parent
            random.seed(0)
            picks.append(disturbed_programs.index(disturbed.sample()))
        self.assertEqual(picks, expected_picks)

    def test_invalid_settings_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Database(archive_size=0)
        with self.assertRaises(ValueError):
            Database(exploitation_ratio=1.5)
        with self.assertRaises(ValueError):
            Database(exploitation_ratio=-0.1)


if __name__ == "__main__":
    unittest.main()
