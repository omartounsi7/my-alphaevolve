"""The evaluation criteria for the function-minimization example.

The problem: find the point, within given bounds, where a function is lowest.
A point is a list of numbers, one per coordinate. The function and the bounds
are defined in target.py, next to this file.

Every candidate program must define a function called search that takes the
function and the two lists of bounds, and returns its best guess for that point.
"""

import math
from typing import Any

from target import LOWER_BOUNDS, UPPER_BOUNDS, target_function

# The name of the function every program must define
FUNCTION_NAME = "search"


def validate_point(answer: Any) -> list[float]:
    """Check that a program's answer follows the rules and return it as a list of numbers.

    Raises ValueError with an explanation if any rule is broken.
    """
    # If the returned answer is not of the correct type (for this particular problem
    # we expect a list of numbers), we raise an error.
    if not isinstance(answer, list | tuple):
        raise ValueError(f"expected a list of numbers, got {type(answer).__name__}")

    # The point must have exactly one number per coordinate
    if len(answer) != len(LOWER_BOUNDS):
        raise ValueError(f"expected {len(LOWER_BOUNDS)} coordinates, got {len(answer)}")

    # zip walks through the three lists together, one coordinate at a time
    for coordinate, lower_bound, upper_bound in zip(
        answer, LOWER_BOUNDS, UPPER_BOUNDS, strict=True
    ):
        # bool counts as a number in Python, so it has to be ruled out separately
        if isinstance(coordinate, bool) or not isinstance(coordinate, int | float):
            raise ValueError(f"expected only numbers, got {type(coordinate).__name__}")

        # Reject infinity and "not a number" (nan), which would break score comparisons
        if not math.isfinite(coordinate):
            raise ValueError(f"expected finite numbers, got {coordinate}")

        # Each coordinate must lie inside the interval the program was told to search
        if not lower_bound <= coordinate <= upper_bound:
            raise ValueError(
                f"expected a coordinate from {lower_bound} to {upper_bound}, got {coordinate}"
            )

    # A fresh list of plain decimal numbers, whatever kind of sequence the program returned
    return [float(coordinate) for coordinate in answer]


def evaluate(namespace: dict[str, Any]) -> float:
    """Turn one finished run of a program into a score (higher is better).

    namespace holds every name the program defined when its code was run.
    Raises ValueError with an explanation if the program breaks the rules.
    """

    # If the program did not implement the required function, we raise an error.
    if FUNCTION_NAME not in namespace:
        raise ValueError(f"the program does not define a function called {FUNCTION_NAME}")

    # Call the program's function to get its answer. It is given copies of the
    # bounds, so a program that changes its arguments cannot change the rules.
    answer = namespace[FUNCTION_NAME](target_function, list(LOWER_BOUNDS), list(UPPER_BOUNDS))

    point = validate_point(answer)

    # A lower point on the surface is a better answer, so flip the sign to get the score.
    # Higher score means better.
    return -target_function(point)
