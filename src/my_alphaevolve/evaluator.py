"""The Evaluator classes: run a program and measure how good it is.

Runs always use DockerEvaluator, which runs each program in its own Docker
container: no network, a read-only file system, limited memory and a time limit.
"""

import hashlib
import json
import math
import shutil
import subprocess
import tempfile
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from my_alphaevolve.problem import ScoreFunction
from my_alphaevolve.program import Program

# How long one program may run, in seconds.
DEFAULT_TIMEOUT_SECONDS = 30.0

# The longest failure message kept, in characters.
MAX_MESSAGE_LENGTH = 2000

# The image in which DockerEvaluator runs programs.
DOCKERFILE_PATH = Path(__file__).parent / "evaluation.Dockerfile"
DOCKER_IMAGE_NAME = "my-alphaevolve-evaluation"

# Limits of one evaluation container.
DEFAULT_MEMORY_LIMIT = "1g"
DEFAULT_CPU_LIMIT = 1.0
DEFAULT_PROCESS_LIMIT = 64


def score_program(code: str, score_function: ScoreFunction) -> float:
    """Run a program's code in this process and return its score (higher is better)."""
    namespace: dict[str, Any] = {}
    exec(code, namespace)
    score: Any = score_function(namespace)
    if isinstance(score, bool) or not isinstance(score, int | float):
        raise ValueError(f"the score must be a number, got {type(score).__name__}")
    if not math.isfinite(score):
        raise ValueError(f"the score must be a finite number, got {score}")
    return float(score)


def describe_error(error: Exception) -> str:
    """Return a short text saying what went wrong, such as "ZeroDivisionError: division by zero"."""
    message = f"{type(error).__name__}: {error}"
    return message[:MAX_MESSAGE_LENGTH]


class Evaluator(ABC):
    """What every evaluator must be able to do: turn a program into a score."""

    def __init__(self) -> None:
        # The score of programs that fail: worse than any real score.
        self.failure_score: float = float("-inf")

    @abstractmethod
    def execute(self, program: Program) -> float:
        """Run the program's code and return its score (higher is better)."""


class DockerUnavailableError(RuntimeError):
    """Raised when Docker is not installed or not running."""


def docker_image_tag() -> str:
    """Return the image's name, tagged with a fingerprint of the Dockerfile.

    Editing the Dockerfile changes the tag, so the image is rebuilt automatically.
    """
    fingerprint = hashlib.sha256(DOCKERFILE_PATH.read_bytes()).hexdigest()[:12]
    return f"{DOCKER_IMAGE_NAME}:{fingerprint}"


class DockerEvaluator(Evaluator):
    """Runs each program in its own Docker container, removed afterwards.

    Inside the container the program has no network, cannot write anywhere but
    a temporary folder, and is limited in memory, CPU and number of processes.
    It sees only the my_alphaevolve package and the problem's folder, both read-only.
    Stopping the container stops every process the program started.

    The image is built on first use, which downloads Python's official image once.
    """

    def __init__(
        self,
        evaluation_path: Path,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: float = DEFAULT_CPU_LIMIT,
        process_limit: int = DEFAULT_PROCESS_LIMIT,
    ) -> None:
        """Check that Docker works and that the image exists, building it if needed.

        Raises DockerUnavailableError if Docker is not installed or not running.
        """
        super().__init__()
        if timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be above 0, got {timeout_seconds}")
        self.evaluation_path: Path = evaluation_path.resolve()
        # The time limit includes starting the container, about a second.
        self.timeout_seconds: float = timeout_seconds
        self.memory_limit: str = memory_limit
        self.cpu_limit: float = cpu_limit
        self.process_limit: int = process_limit
        self.image: str = docker_image_tag()
        self._check_docker()
        self._ensure_image()

    def _check_docker(self) -> None:
        if shutil.which("docker") is None:
            raise DockerUnavailableError("Docker is not installed.")
        result = subprocess.run(["docker", "info"], capture_output=True, check=False)
        if result.returncode != 0:
            raise DockerUnavailableError(
                "Docker is not running: start it (Docker Desktop on Windows and macOS)."
            )

    def _ensure_image(self) -> None:
        inspect = subprocess.run(
            ["docker", "image", "inspect", self.image], capture_output=True, check=False
        )
        if inspect.returncode == 0:
            return
        print(f"Building the Docker image {self.image} (only once)...")
        build_command = [
            "docker", "build",
            "--tag", self.image,
            "--file", str(DOCKERFILE_PATH),
            str(DOCKERFILE_PATH.parent),
        ]  # fmt: skip
        subprocess.run(build_command, check=True)

    def _run_command(self, container_name: str) -> list[str]:
        package_folder = Path(__file__).resolve().parent
        return [
            "docker", "run", "--rm", "--interactive",
            "--name", container_name,
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp",
            "--memory", self.memory_limit,
            "--memory-swap", self.memory_limit,
            "--cpus", str(self.cpu_limit),
            "--pids-limit", str(self.process_limit),
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--mount", f"type=bind,source={package_folder},target=/app/my_alphaevolve,readonly",
            "--mount", f"type=bind,source={self.evaluation_path.parent},target=/problem,readonly",
            self.image,
            "python", "-m", "my_alphaevolve.container_worker",
            f"/problem/{self.evaluation_path.name}",
        ]  # fmt: skip

    def execute(self, program: Program) -> float:
        """Run the program in a new container and return its score.

        A program that crashes, breaks the problem's rules, is given an invalid
        score, runs too long or exceeds the container's limits gets failure_score.
        """
        container_name = f"my-alphaevolve-{uuid.uuid4().hex[:12]}"
        # Output goes to files, not memory: a program may print without end.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(
                self._run_command(container_name),
                stdin=subprocess.PIPE,
                stdout=output,
                stderr=errors,
            )
            try:
                assert process.stdin is not None
                process.stdin.write(program.code.encode("utf-8"))
                process.stdin.close()
                process.wait(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                print(f"Evaluation failed: no answer after {self.timeout_seconds} seconds")
                return self.failure_score
            finally:
                # Always remove the container, even after Ctrl+C.
                if process.poll() is None:
                    subprocess.run(["docker", "kill", container_name], capture_output=True)
                    process.kill()
                    process.wait()
            output.seek(0)
            result = _read_result(output.read().decode("utf-8", errors="replace"))
            if result is None:
                errors.seek(0)
                error_text = errors.read().decode("utf-8", errors="replace")
                print(f"Evaluation failed: {_describe_silent_end(process.returncode, error_text)}")
                return self.failure_score

        if result["status"] == "ok":
            return float(result["score"])
        print(f"Evaluation failed: {result.get('message')}")
        return self.failure_score


def _read_result(output: str) -> dict[str, Any] | None:
    """Return the result printed by the container worker, or None if there is none."""
    lines = output.strip().splitlines()
    if not lines:
        return None
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) and "status" in result else None


def _describe_silent_end(return_code: int, error_text: str) -> str:
    """Explain why a container ended without giving a result."""
    # 137: killed, which Docker does when the memory limit is reached.
    if return_code == 137:
        return "the program was stopped, most likely for using too much memory"
    last_lines = " | ".join(error_text.strip().splitlines()[-3:])
    message = "the program stopped without giving an answer"
    return f"{message} ({last_lines})"[:MAX_MESSAGE_LENGTH] if last_lines else message
