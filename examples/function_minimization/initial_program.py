"""Problem: find the lowest point of a function of one or several variables.

Write a function search(target_function, lower_bounds, upper_bounds) that returns
a point where target_function(point) is as small as possible.

A point is a list of numbers, one per variable. lower_bounds and upper_bounds
are lists of the same length as a point: coordinate i of the returned point must
satisfy lower_bounds[i] <= point[i] <= upper_bounds[i]. There may be only one
variable; a point is then a list holding a single number.

target_function takes a point and returns one number. It is not known in
advance, so search must discover its shape by calling it. It may have several
valleys, and the goal is the lowest one.

The score is minus target_function(point) at the returned point, so a higher
score is better.
"""

from collections.abc import Callable


def search(
    target_function: Callable[[list[float]], float],
    lower_bounds: list[float],
    upper_bounds: list[float],
) -> list[float]:
    """Return the point within the bounds where we think target_function is lowest."""
    # A deliberately poor first attempt: always answer with the lowest corner
    return list(lower_bounds)
