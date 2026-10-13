"""The LLM classes: send a prompt to a language model and return its reply."""

from abc import ABC, abstractmethod

# Note: the openai package is not imported here, at the top, as is usual.
# It takes close to a second to import. Every program is scored in a new process
# that starts by importing the files the run script imports, so importing openai
# here would add that second to every single evaluation.
# It is therefore imported only where it is used, inside OpenAICompatibleLLM.

# Where a local Ollama server listens by default. The "/v1" part is the
# OpenAI-compatible interface that Ollama, like most cloud providers, offers.
DEFAULT_LLM_URL = "http://localhost:11434/v1"

# The longest reply asked of the model, in tokens (a token is roughly 3/4 of a word).
# It bounds the cost and duration of one request.
DEFAULT_MAX_REPLY_TOKENS = 4096

# How long to wait for one reply, in seconds, before giving up on the request
DEFAULT_REQUEST_TIMEOUT_SECONDS = 300.0

# How many times a request that failed for a passing reason (network trouble,
# a busy server) is tried again before giving up
DEFAULT_MAX_RETRIES = 2

# Sent as the API key when none is given. A local server such as Ollama ignores
# the key, but the openai package refuses to work without one.
PLACEHOLDER_API_KEY = "no-key-needed"


class LLMError(Exception):
    """Raised when an LLM could not give a reply, for example because of a network problem.

    Having one error type of our own lets the evolution loop catch every such
    failure in one place, whichever LLM class is in use.
    """


class LLM(ABC):
    """What every LLM must be able to do: turn a prompt into a reply.

    This class is only a description. The real work is done by the classes
    built on it, which all offer the same generate method.
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return the model's reply to the prompt, as text.

        Raises LLMError if no reply could be obtained.
        """


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


class OpenAICompatibleLLM(LLM):
    """A real LLM, reached through the OpenAI-compatible interface.

    That interface is offered by Ollama for models running on your own machine
    and by most cloud providers, so this one class serves both: only the
    address, the model name and the API key differ.
    """

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_LLM_URL,
        api_key: str | None = None,
        max_reply_tokens: int | None = DEFAULT_MAX_REPLY_TOKENS,
        timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """Prepare to talk to one model on one server. Nothing is sent yet.

        api_key is the secret that identifies you to a cloud provider; None is
        fine for a local server. max_reply_tokens may be None for no limit.

        Raises ValueError if a setting is out of range.
        """
        if not model:
            raise ValueError("The name of the model must not be empty.")
        if max_reply_tokens is not None and max_reply_tokens < 1:
            raise ValueError(f"max_reply_tokens must be 1 or more, got {max_reply_tokens}")
        if timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be above 0, got {timeout_seconds}")
        if max_retries < 0:
            raise ValueError(f"max_retries must be 0 or more, got {max_retries}")
        # Imported here and not at the top of the file: see the note there
        import openai

        # The name of the model to use, as the server knows it
        self.model: str = model
        # The address of the server
        self.base_url: str = base_url
        # The longest reply to ask for, in tokens; None for no limit
        self.max_reply_tokens: int | None = max_reply_tokens
        # The object from the openai package that sends the requests. It also
        # waits at most timeout_seconds per request and retries passing failures.
        # The API key is handed to it and deliberately not kept anywhere else.
        self.client: openai.OpenAI = openai.OpenAI(
            base_url=base_url,
            api_key=api_key or PLACEHOLDER_API_KEY,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    def generate(self, prompt: str) -> str:
        """Send the prompt to the model and return its reply, as text.

        Raises LLMError if the request fails after its retries, or if the
        model's reply is empty.
        """
        # Already loaded when the object was created, so this costs nothing
        import openai

        try:
            if self.max_reply_tokens is None:
                response = self.client.chat.completions.create(
                    model=self.model,
                    # A conversation holding a single message, from the user: our prompt
                    messages=[{"role": "user", "content": prompt}],
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.max_reply_tokens,
                )
        except openai.OpenAIError as error:
            # Every failure of the openai package (no connection, refused key,
            # server error, timeout...) becomes our own error type
            raise LLMError(f"{type(error).__name__}: {error}") from error

        # A response can hold several alternative replies; we asked for one
        reply = response.choices[0].message.content if response.choices else None
        if not reply:
            raise LLMError("the model returned an empty reply")
        return reply
