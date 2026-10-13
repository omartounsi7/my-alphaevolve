"""The LLM classes: send a prompt to a language model and return its reply."""

from abc import ABC, abstractmethod


class LLM(ABC):
    """What every LLM must be able to do: turn a prompt into a reply.

    This class is only a description. The real work is done by the classes
    built on it, such as FakeLLM, which all offer the same generate method.
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return the model's reply to the prompt, as text."""


class FakeLLM(LLM):
    """A stand-in for a real LLM that returns replies prepared in advance.

    It needs no network, costs nothing and always behaves the same way,
    which makes it suitable for building and testing the evolution loop.
    """

    def __init__(self, replies: list[str]) -> None:
        """Prepare the fake with the replies it will give, in order.

        Raises ValueError if replies is empty.
        """
        if not replies:
            raise ValueError("FakeLLM needs at least one reply.")
        # The prepared replies; a copy, so later changes to the caller's list have no effect
        self.replies: list[str] = list(replies)
        # Every prompt received so far, in order; lets tests check what was asked
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        """Record the prompt and return the next prepared reply.

        After the last reply, it starts again from the first one.
        """
        # How many prompts came before this one: 0 for the first call, 1 for the second, ...
        call_number = len(self.prompts)
        self.prompts.append(prompt)
        # % gives the remainder of a division, which wraps the position back to 0
        return self.replies[call_number % len(self.replies)]
