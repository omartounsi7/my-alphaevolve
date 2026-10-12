"""Checks that Program and Database behave as intended."""

import unittest

from my_alphaevolve.database import Database
from my_alphaevolve.program import Program


class TestProgram(unittest.TestCase):
    def test_each_program_gets_its_own_id(self):
        # Two programs must never share an id, even with identical code
        self.assertNotEqual(Program("x = 1").id, Program("x = 1").id)

    def test_defaults_describe_an_initial_program(self):
        # A program created from code alone has no score, no parent, generation 0
        program = Program("x = 1")
        self.assertIsNone(program.score)
        self.assertIsNone(program.parent_id)
        self.assertEqual(program.generation, 0)


class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Runs before every test: a database holding a parent and its better child
        self.database = Database()
        self.parent = Program("x = 1")
        self.child = Program("x = 2", parent_id=self.parent.id, generation=1)
        self.database.add(self.parent, 0.0)
        self.database.add(self.child, 1.0)

    def test_add_stores_the_results_on_the_program(self):
        self.assertEqual(self.parent.score, 0.0)
        self.assertEqual(self.child.score, 1.0)

    def test_get_finds_a_program_by_id(self):
        # Following a child's parent_id leads back to the parent object
        self.assertIs(self.database.get(self.child.parent_id), self.parent)

    def test_get_returns_none_for_an_unknown_id(self):
        self.assertIsNone(self.database.get("no-such-id"))

    def test_sample_returns_a_stored_program(self):
        for _ in range(20):
            self.assertIn(self.database.sample(), [self.parent, self.child])

    def test_best_returns_the_highest_score(self):
        self.assertIs(self.database.best(), self.child)

    def test_best_of_an_empty_database_is_none(self):
        self.assertIsNone(Database().best())


if __name__ == "__main__":
    unittest.main()
