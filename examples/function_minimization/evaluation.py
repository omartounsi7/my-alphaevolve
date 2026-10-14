"""The evaluation criteria for the function-minimization example.

The function to minimize and the bounds are defined in target.py. Every candidate
program must define search(target_function, lower_bounds, upper_bounds), which
returns its best guess for the point where the function is lowest.
"""

import math
from typing import Any

from target import LOWER_BOUNDS, UPPER_BOUNDS, target_function

# The function every program must define.
FUNCTION_NAME = "search"


def validate_point(answer: Any) -> list[float]:
    """Check that a program's answer follows the rules and return it as a list of numbers.

    Raises ValueError with an explanation if any rule is broken.
    """
    if not isinstance(answer, list | tuple):
        raise ValueError(f"expected a list of numbers, got {type(answer).__name__}")

    if len(answer) != len(LOWER_BOUNDS):
        raise ValueError(f"expected {len(LOWER_BOUNDS)} coordinates, got {len(answer)}")

    for coordinate, lower_bound, upper_bound in zip(
        answer, LOWER_BOUNDS, UPPER_BOUNDS, strict=True
    ):
        if isinstance(coordinate, bool) or not isinstance(coordinate, int | float):
            raise ValueError(f"expected only numbers, got {type(coordinate).__name__}")

        if not math.isfinite(coordinate):
            raise ValueError(f"expected finite numbers, got {coordinate}")

        if not lower_bound <= coordinate <= upper_bound:
            raise ValueError(
                f"expected a coordinate from {lower_bound} to {upper_bound}, got {coordinate}"
            )

    return [float(coordinate) for coordinate in answer]


def evaluate(namespace: dict[str, Any]) -> float:
    """Turn one finished run of a program into a score (higher is better).

    namespace holds every name the program defined when its code was run.
    Raises ValueError if the program breaks the rules.
    """
    if FUNCTION_NAME not in namespace:
        raise ValueError(f"the program does not define a function called {FUNCTION_NAME}")

    # Pass copies of the bounds, so the program cannot change the rules.
    answer = namespace[FUNCTION_NAME](target_function, list(LOWER_BOUNDS), list(UPPER_BOUNDS))

    point = validate_point(answer)

    # Lower is better for the function, so flip the sign.
    return -target_function(point)
