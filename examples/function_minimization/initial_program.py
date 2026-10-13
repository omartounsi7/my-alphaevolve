"""Problem: find the lowest point of a function of one variable.

Write a function search(target_function, lower_bound, upper_bound) that returns
a number x, with lower_bound <= x <= upper_bound, where target_function(x) is as
small as possible.

target_function takes one number and returns one number. It is not known in
advance, so search must discover its shape by calling it. It may have several
valleys, and the goal is the lowest one.

The score is minus target_function(x) at the returned x, so a higher score is
better.
"""

from collections.abc import Callable


def search(
    target_function: Callable[[float], float],
    lower_bound: float,
    upper_bound: float,
) -> float:
    """Return the x between the bounds where we think target_function is lowest."""
    # A deliberately poor first attempt: always answer with the left edge
    return lower_bound
