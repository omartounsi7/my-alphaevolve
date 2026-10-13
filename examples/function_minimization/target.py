"""The function to minimize in this example, and the region to search.

A point is always a list of numbers, one per coordinate, even when there is
only one coordinate. The number of coordinates is the length of the bounds.

To minimize a different function, edit this file only: nothing else in the
example mentions a particular function or number of coordinates.
"""

import math

# The smallest and largest value allowed for each coordinate of a point.
# Both lists must have the same length: one entry per coordinate.
LOWER_BOUNDS = [-10.0, -10.0]
UPPER_BOUNDS = [10.0, 10.0]


def target_function(point: list[float]) -> float:
    """Return the height of the surface at a point; this is what we want to make small."""
    # For each coordinate x: sin(3 * x) makes waves and x**2 / 10 is a wide bowl,
    # so the surface has many valleys and one of them is the deepest
    return sum(math.sin(3 * x) + x**2 / 10 for x in point)
