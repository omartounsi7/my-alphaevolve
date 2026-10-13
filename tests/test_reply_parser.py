"""Checks that an LLM's reply is turned into the right child Program."""

import unittest

from my_alphaevolve.program import Program
from my_alphaevolve.reply_parser import extract_code, make_child_program

# The marker that opens and closes a code block, named so the tests stay readable
FENCE = "```"


class TestExtractCode(unittest.TestCase):
    """Checks on extract_code, one shape of reply per test."""

    def test_code_block_with_a_language_name(self) -> None:
        reply = f"{FENCE}python\nx = 1\n{FENCE}"
        self.assertEqual(extract_code(reply), "x = 1\n")

    def test_code_block_without_a_language_name(self) -> None:
        reply = f"{FENCE}\nx = 1\n{FENCE}"
        self.assertEqual(extract_code(reply), "x = 1\n")

    def test_sentences_around_the_code_block_are_dropped(self) -> None:
        reply = f"Here is a better version.\n\n{FENCE}python\nx = 1\n{FENCE}\n\nIt is faster."
        self.assertEqual(extract_code(reply), "x = 1\n")

    def test_longest_of_several_code_blocks_is_kept(self) -> None:
        reply = (
            f"First change this line:\n{FENCE}python\nx = 1\n{FENCE}\n"
            f"The full program is:\n{FENCE}python\nx = 1\ny = 2\n{FENCE}\n"
        )
        self.assertEqual(extract_code(reply), "x = 1\ny = 2\n")

    def test_code_block_that_is_never_closed(self) -> None:
        reply = f"Here it is.\n{FENCE}python\nx = 1\ny = 2"
        self.assertEqual(extract_code(reply), "x = 1\ny = 2\n")

    def test_reply_without_a_code_block_is_taken_whole(self) -> None:
        self.assertEqual(extract_code("x = 1\ny = 2\n"), "x = 1\ny = 2\n")

    def test_indentation_and_blank_lines_inside_the_code_are_kept(self) -> None:
        code = "def f():\n    a = 1\n\n    return a\n"
        self.assertEqual(extract_code(f"{FENCE}python\n{code}{FENCE}"), code)

    def test_reasoning_of_a_thinking_model_is_dropped(self) -> None:
        # Some models write their reasoning first, between <think> and </think>
        reply = "<think>\nMaybe x = 5? No, too big.\n</think>\n\nx = 1\ny = 2\n"
        self.assertEqual(extract_code(reply), "x = 1\ny = 2\n")

    def test_code_block_inside_the_reasoning_is_not_taken_for_the_program(self) -> None:
        # The discarded attempt is longer than the answer, and must still lose
        reply = (
            f"<think>\nFirst idea:\n{FENCE}python\nx = 100\ny = 200\nz = 300\n{FENCE}\n</think>\n"
            f"{FENCE}python\nx = 1\n{FENCE}\n"
        )
        self.assertEqual(extract_code(reply), "x = 1\n")

    def test_empty_reply_gives_an_empty_program(self) -> None:
        self.assertEqual(extract_code(""), "\n")


class TestMakeChildProgram(unittest.TestCase):
    """Checks on make_child_program."""

    def setUp(self) -> None:
        # Runs before every test: an evaluated parent three steps from the initial program
        self.parent = Program("x = 1\n", score=2.0, generation=3)
        self.child = make_child_program(self.parent, f"Better:\n{FENCE}python\nx = 2\n{FENCE}")

    def test_child_code_comes_from_the_reply(self) -> None:
        self.assertEqual(self.child.code, "x = 2\n")

    def test_child_remembers_its_parent(self) -> None:
        self.assertEqual(self.child.parent_id, self.parent.id)

    def test_child_is_one_generation_after_its_parent(self) -> None:
        self.assertEqual(self.child.generation, 4)

    def test_child_is_a_new_unevaluated_program(self) -> None:
        self.assertNotEqual(self.child.id, self.parent.id)
        self.assertIsNone(self.child.score)

    def test_parent_is_left_unchanged(self) -> None:
        self.assertEqual(self.parent.code, "x = 1\n")
        self.assertEqual(self.parent.score, 2.0)


if __name__ == "__main__":
    unittest.main()
