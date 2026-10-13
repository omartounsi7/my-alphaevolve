"""Checks that the FakeLLM behaves as intended."""

import unittest

from my_alphaevolve.llm import LLM, FakeLLM


class TestFakeLLM(unittest.TestCase):
    """Checks on FakeLLM.generate."""

    def test_replies_are_returned_in_order(self) -> None:
        llm = FakeLLM(["first", "second"])
        self.assertEqual(llm.generate("a prompt"), "first")
        self.assertEqual(llm.generate("a prompt"), "second")

    def test_replies_start_again_after_the_last_one(self) -> None:
        llm = FakeLLM(["first", "second"])
        replies = [llm.generate("a prompt") for _ in range(5)]
        self.assertEqual(replies, ["first", "second", "first", "second", "first"])

    def test_prompts_are_recorded_in_order(self) -> None:
        llm = FakeLLM(["a reply"])
        llm.generate("prompt one")
        llm.generate("prompt two")
        self.assertEqual(llm.prompts, ["prompt one", "prompt two"])

    def test_changing_the_original_list_does_not_change_the_replies(self) -> None:
        replies = ["first"]
        llm = FakeLLM(replies)
        replies.append("second")
        self.assertEqual(llm.generate("a prompt"), "first")
        self.assertEqual(llm.generate("a prompt"), "first")

    def test_no_replies_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FakeLLM([])

    def test_fake_llm_is_an_llm(self) -> None:
        # Anything written for an LLM must accept a FakeLLM
        self.assertIsInstance(FakeLLM(["a reply"]), LLM)


if __name__ == "__main__":
    unittest.main()
