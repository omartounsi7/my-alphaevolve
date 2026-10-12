"""The problem being solved: minimize a function.

Every candidate program must define a function called search that takes no
arguments and returns one number: its best guess for the x where
target_function(x) is lowest.

Later on this file will be made to handle any user-inputted problem.
"""

import math
from typing import Any

# The name of the function every program must define
FUNCTION_NAME = "search"

# The starting program, as text: a deliberately poor guess
INITIAL_CODE = '''
def search():
    """Return the x where we think the target function is lowest."""
    return 0.0
'''


def target_function(x: float) -> float:
    """Return the height of the bumpy curve at x; this is what we want to make small."""
    return math.sin(3 * x) + x**2 / 10


def score_function(namespace: dict[str, Any]) -> float:
    """Turn one finished run of a program into a score (higher is better).

    namespace holds every name the program defined when its code was run.
    Raises ValueError with an explanation if the program breaks the rules.
    """

    # If the program did not implement the required function, we return an error.
    if FUNCTION_NAME not in namespace:
        raise ValueError(f"the program does not define a function called {FUNCTION_NAME}")
    
    # Call the program's function to get its answer
    answer = namespace[FUNCTION_NAME]()

    # If the returned answer is not of the correct type (for this particular problem we expect a number), we return an error.
    # bool counts as a number in Python, so it has to be ruled out separately
    if isinstance(answer, bool) or not isinstance(answer, int | float):
        raise ValueError(f"expected a number, got {type(answer).__name__}")

    # Reject infinity and "not a number" (nan), which would break score comparisons
    if not math.isfinite(answer):
        raise ValueError(f"expected a finite number, got {answer}")

    # A lower point on the curve is a better answer, so flip the sign to get the score. Higher score means better.
    return -target_function(answer)