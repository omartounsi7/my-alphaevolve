"""Checks that the PromptSampler builds the prompt as intended."""

import unittest

from my_alphaevolve.program import Program
from my_alphaevolve.prompt_sampler import PromptSampler


class TestPromptSampler(unittest.TestCase):
    """Checks on PromptSampler.build."""

    def setUp(self) -> None:
        # Runs before every test: a sampler using the default template
        self.prompt_sampler = PromptSampler("Find the lowest point of a curve.")

    def test_prompt_contains_the_description_code_and_score(self) -> None:
        parent = Program("def search():\n    return 0.1\n", score=-0.25)
        prompt = self.prompt_sampler.build(parent)
        self.assertIn("Find the lowest point of a curve.", prompt)
        self.assertIn("def search():\n    return 0.1", prompt)
        self.assertIn("Score: -0.25", prompt)

    def test_prompt_asks_for_only_code_with_explanations_in_comments(self) -> None:
        prompt = self.prompt_sampler.build(Program("x = 1\n", score=1.0))
        self.assertIn("Reply with only the complete new program, as Python code.", prompt)
        self.assertIn("put every explanation in comments inside the code", prompt)

    def test_instructions_come_after_the_program(self) -> None:
        # The last thing the LLM reads is what it is asked to produce
        prompt = self.prompt_sampler.build(Program("x = 1\n", score=1.0))
        self.assertLess(prompt.index("x = 1"), prompt.index("Reply with only"))

    def test_curly_braces_in_the_code_and_description_are_kept_as_written(self) -> None:
        # Curly braces are special in templates, but must survive in the filled-in text
        prompt_sampler = PromptSampler("Return a set such as {1, 2}.")
        prompt = prompt_sampler.build(Program("values = {'a': 1}\n", score=1.0))
        self.assertIn("Return a set such as {1, 2}.", prompt)
        self.assertIn("values = {'a': 1}", prompt)

    def test_custom_template_is_used(self) -> None:
        prompt_sampler = PromptSampler("minimize", "{description} / {score} / {code}")
        prompt = prompt_sampler.build(Program("x = 1\n", score=2.0))
        self.assertEqual(prompt, "minimize / 2.0 / x = 1")

    def test_program_without_a_score_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.prompt_sampler.build(Program("x = 1\n"))


if __name__ == "__main__":
    unittest.main()
