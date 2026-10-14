"""The evaluation criteria for the function minimization example.

They compute the score of OpenEvolve's examples/function_minimization/evaluator.py,
run with its config.yaml (cascade evaluation, threshold 1.3):

- stage 1 calls run_search once and scores its answer;
- a program scoring at least 1.3 goes on to stage 2, which calls run_search 10
  times and replaces the stage 1 score with its own.

As in OpenEvolve, a program without run_search, or whose calls all fail, scores 0.
"""

import concurrent.futures
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

# The function every program must define.
FUNCTION_NAME = "run_search"
# OpenEvolve's approximation of the global minimum.
GLOBAL_MIN_X = -1.704
GLOBAL_MIN_Y = 0.678
GLOBAL_MIN_VALUE = -1.519
# The score stage 1 must reach for stage 2 to run.
STAGE_2_THRESHOLD = 1.3
NUMBER_OF_TRIALS = 10
TRIAL_TIMEOUT_SECONDS = 5
# Score multipliers for a distance to the global minimum below 0.5, 1.5, 3.0, and beyond.
DISTANCE_LIMITS = (0.5, 1.5, 3.0)
STAGE_1_MULTIPLIERS = (1.4, 1.15, 1.0, 0.8)
STAGE_2_MULTIPLIERS = (1.5, 1.2, 1.0, 0.7)

# An answer of run_search: x, y and the function's value there.
Answer = tuple[float, float, float]


def target_function(x: Any, y: Any) -> Any:
    """Return f(x, y), computed as in OpenEvolve's evaluator."""
    return np.sin(x) * np.cos(y) + np.sin(x * y) + (x**2 + y**2) / 20


def run_with_timeout(function: Callable[[], Any], timeout_seconds: float) -> Any:
    """Call function and return its result; raise TimeoutError if it took too long.

    As in OpenEvolve, a slow call is not stopped: the error comes once it has finished.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(function)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as error:
            raise TimeoutError(f"Function timed out after {timeout_seconds} seconds") from error


def safe_float(value: Any) -> float:
    """Return value as a float, or 0.0 if it cannot be converted, as OpenEvolve does."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def run_trial(run_search: Callable[[], Any]) -> Answer | None:
    """Call run_search once and return its answer, or None if the call fails."""
    try:
        result = run_with_timeout(run_search, TRIAL_TIMEOUT_SECONDS)
        if not isinstance(result, tuple) or len(result) not in (2, 3):
            return None
        if len(result) == 3:
            x, y, value = result
        else:
            x, y = result
            value = target_function(x, y)
        answer = (safe_float(x), safe_float(y), safe_float(value))
    except Exception:
        return None
    if not all(np.isfinite(number) for number in answer):
        return None
    return answer


def distance_to_global_minimum(x: float, y: float) -> float:
    return float(np.sqrt((x - GLOBAL_MIN_X) ** 2 + (y - GLOBAL_MIN_Y) ** 2))


def value_score(value: float) -> float:
    return 1.0 / (1.0 + abs(value - GLOBAL_MIN_VALUE))


def quality_multiplier(distance: float, multipliers: Sequence[float]) -> float:
    """Return the bonus or penalty for a distance to the global minimum."""
    for limit, multiplier in zip(DISTANCE_LIMITS, multipliers[:-1], strict=True):
        if distance < limit:
            return multiplier
    return multipliers[-1]


def stage_1_score(run_search: Callable[[], Any]) -> float:
    """Score one call of run_search."""
    answer = run_trial(run_search)
    if answer is None:
        return 0.0
    x, y, value = answer
    distance = distance_to_global_minimum(x, y)
    base_score = 0.6 * value_score(value) + 0.4 * (1.0 / (1.0 + distance))
    return base_score * quality_multiplier(distance, STAGE_1_MULTIPLIERS)


def stage_2_score(run_search: Callable[[], Any]) -> float:
    """Score several calls of run_search: their average answer and how many succeeded."""
    trials = [run_trial(run_search) for _ in range(NUMBER_OF_TRIALS)]
    answers = [answer for answer in trials if answer is not None]
    if not answers:
        return 0.0
    average_value = float(np.mean([value for _, _, value in answers]))
    average_distance = float(np.mean([distance_to_global_minimum(x, y) for x, y, _ in answers]))
    reliability = len(answers) / NUMBER_OF_TRIALS
    base_score = (
        0.5 * value_score(average_value)
        + 0.3 * (1.0 / (1.0 + average_distance))
        + 0.2 * reliability
    )
    return base_score * quality_multiplier(average_distance, STAGE_2_MULTIPLIERS)


def evaluate(namespace: dict[str, Any]) -> float:
    """Return the program's score, as OpenEvolve computes it (higher is better)."""
    if FUNCTION_NAME not in namespace:
        return 0.0
    run_search = namespace[FUNCTION_NAME]
    score = stage_1_score(run_search)
    if score < STAGE_2_THRESHOLD:
        return score
    return stage_2_score(run_search)
