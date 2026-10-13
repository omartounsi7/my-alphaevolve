"""A tiny stand-in for an LLM server, for the tests.

It runs inside the test process, listens on this machine only, and answers the
one request the openai package makes: a "chat completion". This lets the tests
exercise the real OpenAICompatibleLLM class, and the real run script, without
any network or any LLM.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# A reply the fake server can be told to give: text for a normal answer, or a
# number for a failure with that HTTP status code (500 means "server error")
PreparedReply = str | int


class FakeLLMServer:
    """A local web server that answers chat requests with replies prepared in advance."""

    def __init__(self, replies: list[PreparedReply]) -> None:
        """Start the server. Call stop() when done, or use it in a "with" block."""
        # The prepared replies, given in order and then repeated from the first one
        self.replies: list[PreparedReply] = list(replies)
        # Every request received so far: the "authorization" header and the decoded "body"
        self.requests: list[dict[str, Any]] = []
        fake_server = self

        class Handler(BaseHTTPRequestHandler):
            """Answers one request; the http.server module creates one per request."""

            def do_POST(self) -> None:  # noqa: N802 - the name is imposed by http.server
                """Record the request and send back the next prepared reply."""
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                call_number = len(fake_server.requests)
                fake_server.requests.append(
                    {"authorization": self.headers.get("Authorization"), "body": body}
                )
                reply = fake_server.replies[call_number % len(fake_server.replies)]

                if isinstance(reply, int):
                    # A failure: only the status code matters
                    self.send_response(reply)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": {"message": "prepared failure"}}')
                    return

                # A success, in the shape the OpenAI-compatible interface prescribes
                answer = {
                    "id": "fake-completion",
                    "object": "chat.completion",
                    "created": 0,
                    "model": body.get("model", ""),
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": reply},
                            "finish_reason": "stop",
                        }
                    ],
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(answer).encode("utf-8"))

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                """Stay silent: by default every request would print a line during the tests."""

        # Port 0 asks the system for any free port; 127.0.0.1 is "this machine only"
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        # The address to give to OpenAICompatibleLLM or to --llm-url
        self.url: str = f"http://127.0.0.1:{self._server.server_port}/v1"
        # The server waits for requests in the background while the test carries on
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the server and free its port."""
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()

    def __enter__(self) -> "FakeLLMServer":
        """Allow "with FakeLLMServer(...) as server:", which stops the server at the end."""
        return self

    def __exit__(self, *exception_details: object) -> None:
        """Stop the server when the "with" block ends, even after an error."""
        self.stop()
