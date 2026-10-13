"""The evaluation criteria for the function-minimization example.

The problem: find the x, within given bounds, where a function is lowest.
The function and the bounds are defined in target.py, next to this file.

Every candidate program must define a function called search that takes the
function and the two bounds, and returns one number: its best guess for that x.
"""

import math
from typing import Any

from target import LOWER_BOUND, UPPER_BOUND, target_function

# The name of the function every program must define
FUNCTION_NAME = "search"


def evaluate(namespace: dict[str, Any]) -> float:
    """Turn one finished run of a program into a score (higher is better).

    namespace holds every name the program defined when its code was run.
    Raises ValueError with an explanation if the program breaks the rules.
    """

    # If the program did not implement the required function, we raise an error.
    if FUNCTION_NAME not in namespace:
        raise ValueError(f"the program does not define a function called {FUNCTION_NAME}")

    # Call the program's function to get its answer
    answer = namespace[FUNCTION_NAME](target_function, LOWER_BOUND, UPPER_BOUND)

    # If the returned answer is not of the correct type (for this particular problem
    # we expect a number), we raise an error.
    # bool counts as a number in Python, so it has to be ruled out separately
    if isinstance(answer, bool) or not isinstance(answer, int | float):
        raise ValueError(f"expected a number, got {type(answer).__name__}")

    # Reject infinity and "not a number" (nan), which would break score comparisons
    if not math.isfinite(answer):
        raise ValueError(f"expected a finite number, got {answer}")

    # The answer must lie inside the interval the program was told to search
    if not LOWER_BOUND <= answer <= UPPER_BOUND:
        raise ValueError(f"expected a number from {LOWER_BOUND} to {UPPER_BOUND}, got {answer}")

    # A lower point on the curve is a better answer, so flip the sign to get the score.
    # Higher score means better.
    return -target_function(answer)
