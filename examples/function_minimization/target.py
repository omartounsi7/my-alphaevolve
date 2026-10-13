"""The function to minimize in this example, and the interval to search.

To minimize a different function, edit this file only: nothing else in the
example mentions a particular function.
"""

import math

# The smallest and largest x a program is allowed to answer with
LOWER_BOUND = -10.0
UPPER_BOUND = 10.0


def target_function(x: float) -> float:
    """Return the height of the curve at x; this is what we want to make small."""
    # sin(3 * x) makes waves; x**2 / 10 is a wide bowl, so one valley is the deepest
    return math.sin(3 * x) + x**2 / 10
