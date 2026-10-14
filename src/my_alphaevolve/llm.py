"""The LLM classes: send a prompt to a language model and return its reply."""

from abc import ABC, abstractmethod

# The openai package is imported inside OpenAICompatibleLLM, not here: it takes about
# a second to import, and every evaluation subprocess would pay that cost.

# Where a local Ollama server listens by default ("/v1" is its OpenAI-compatible interface).
DEFAULT_LLM_URL = "http://localhost:11434/v1"

# The longest reply asked of the model, in tokens (about 3/4 of a word each).
DEFAULT_MAX_REPLY_TOKENS = 4096

# How long to wait for one reply, in seconds.
DEFAULT_REQUEST_TIMEOUT_SECONDS = 300.0

# How many times a request that failed for a passing reason (network, busy server) is retried.
DEFAULT_MAX_RETRIES = 2

# Sent when no API key is given: local servers ignore it, but openai requires one.
PLACEHOLDER_API_KEY = "no-key-needed"


class LLMError(Exception):
    """Raised when an LLM could not give a reply, so the loop can catch any LLM failure."""


class LLM(ABC):
    """What every LLM must be able to do: turn a prompt into a reply."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return the model's reply to the prompt, as text.

        Raises LLMError if no reply could be obtained.
        """


class OpenAICompatibleLLM(LLM):
    """A real LLM, reached through the OpenAI-compatible interface."""

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_LLM_URL,
        api_key: str | None = None,
        max_reply_tokens: int | None = DEFAULT_MAX_REPLY_TOKENS,
        timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """Prepare to talk to one model on one server. Nothing is sent yet."""
        if not model:
            raise ValueError("The name of the model must not be empty.")
        if max_reply_tokens is not None and max_reply_tokens < 1:
            raise ValueError(f"max_reply_tokens must be 1 or more, got {max_reply_tokens}")
        if timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be above 0, got {timeout_seconds}")
        if max_retries < 0:
            raise ValueError(f"max_retries must be 0 or more, got {max_retries}")
        # Imported here, not at the top of the file: see the note there.
        import openai

        # The name of the model to use
        self.model: str = model
        # The address of the server
        self.base_url: str = base_url
        # The longest reply to ask for in tokens; None for no limit
        self.max_reply_tokens: int | None = max_reply_tokens
        # Sends the requests (with timeout and retries) and is the only holder of the API key.
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
        # Already loaded in __init__, so this costs nothing.
        import openai

        try:
            if self.max_reply_tokens is None:
                response = self.client.chat.completions.create(
                    model=self.model,
                    # A conversation holding a single user message: the prompt.
                    messages=[{"role": "user", "content": prompt}],
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.max_reply_tokens,
                )
        except openai.OpenAIError as error:
            raise LLMError(f"{type(error).__name__}: {error}") from error

        reply = response.choices[0].message.content if response.choices else None
        if not reply:
            raise LLMError("the model returned an empty reply")
        return reply
