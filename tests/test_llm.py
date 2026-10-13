"""Checks that the LLM classes behave as intended.

The real class, OpenAICompatibleLLM, is tested against a stand-in server that
runs inside the tests, so no network and no actual LLM are needed.
"""

import socket
import unittest

from fake_llm_server import FakeLLMServer

from my_alphaevolve.llm import (
    LLM,
    PLACEHOLDER_API_KEY,
    FakeLLM,
    LLMError,
    OpenAICompatibleLLM,
)


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


def unused_local_url() -> str:
    """Return the address of a port on this machine where no server is listening."""
    # Ask the system for a free port, then release it at once
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}/v1"


class TestOpenAICompatibleLLM(unittest.TestCase):
    """Checks on OpenAICompatibleLLM, talking to the stand-in server."""

    def start_server(self, replies: list[str | int]) -> FakeLLMServer:
        """Start a stand-in server that is stopped automatically after the test."""
        server = FakeLLMServer(replies)
        self.addCleanup(server.stop)
        return server

    def test_reply_of_the_model_is_returned(self) -> None:
        server = self.start_server(["def search():\n    return 1\n"])
        llm = OpenAICompatibleLLM("some-model", base_url=server.url)
        self.assertEqual(llm.generate("a prompt"), "def search():\n    return 1\n")

    def test_request_holds_the_model_the_prompt_and_the_reply_limit(self) -> None:
        server = self.start_server(["a reply"])
        llm = OpenAICompatibleLLM("some-model", base_url=server.url, max_reply_tokens=123)
        llm.generate("Improve this program → please.")
        body = server.requests[0]["body"]
        self.assertEqual(body["model"], "some-model")
        # The prompt travels as a conversation of one message, from the user
        expected_messages = [{"role": "user", "content": "Improve this program → please."}]
        self.assertEqual(body["messages"], expected_messages)
        self.assertEqual(body["max_tokens"], 123)

    def test_no_reply_limit_is_sent_when_there_is_none(self) -> None:
        server = self.start_server(["a reply"])
        llm = OpenAICompatibleLLM("some-model", base_url=server.url, max_reply_tokens=None)
        llm.generate("a prompt")
        self.assertNotIn("max_tokens", server.requests[0]["body"])

    def test_api_key_is_sent_to_the_server(self) -> None:
        server = self.start_server(["a reply"])
        llm = OpenAICompatibleLLM("some-model", base_url=server.url, api_key="secret-key")
        llm.generate("a prompt")
        self.assertEqual(server.requests[0]["authorization"], "Bearer secret-key")

    def test_placeholder_key_is_sent_when_none_is_given(self) -> None:
        # A local server ignores the key, but the request must still carry one
        server = self.start_server(["a reply"])
        OpenAICompatibleLLM("some-model", base_url=server.url).generate("a prompt")
        self.assertEqual(server.requests[0]["authorization"], f"Bearer {PLACEHOLDER_API_KEY}")

    def test_is_an_llm(self) -> None:
        self.assertIsInstance(OpenAICompatibleLLM("some-model"), LLM)

    def test_server_failure_becomes_an_llm_error(self) -> None:
        # 500 is the status code for "the server had an internal error"
        server = self.start_server([500])
        llm = OpenAICompatibleLLM("some-model", base_url=server.url, max_retries=0)
        with self.assertRaises(LLMError):
            llm.generate("a prompt")

    def test_refused_api_key_becomes_an_llm_error(self) -> None:
        # 401 is the status code for "you did not identify yourself correctly"
        server = self.start_server([401])
        llm = OpenAICompatibleLLM("some-model", base_url=server.url, max_retries=0)
        with self.assertRaises(LLMError) as raised:
            llm.generate("a prompt")
        self.assertIn("AuthenticationError", str(raised.exception))

    def test_failed_request_is_tried_again(self) -> None:
        # The first attempt fails; the retry gets the reply
        server = self.start_server([500, "a reply"])
        llm = OpenAICompatibleLLM("some-model", base_url=server.url, max_retries=1)
        self.assertEqual(llm.generate("a prompt"), "a reply")
        self.assertEqual(len(server.requests), 2)

    def test_unreachable_server_becomes_an_llm_error(self) -> None:
        llm = OpenAICompatibleLLM("some-model", base_url=unused_local_url(), max_retries=0)
        with self.assertRaises(LLMError):
            llm.generate("a prompt")

    def test_empty_reply_becomes_an_llm_error(self) -> None:
        server = self.start_server([""])
        llm = OpenAICompatibleLLM("some-model", base_url=server.url)
        with self.assertRaises(LLMError):
            llm.generate("a prompt")

    def test_invalid_settings_are_rejected(self) -> None:
        # Each entry: the arguments of one invalid way to create the LLM
        invalid_settings: list[dict[str, object]] = [
            {"model": ""},
            {"model": "some-model", "max_reply_tokens": 0},
            {"model": "some-model", "timeout_seconds": 0},
            {"model": "some-model", "max_retries": -1},
        ]
        for settings in invalid_settings:
            # ** passes the entries of a dictionary as named arguments
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                OpenAICompatibleLLM(**settings)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
