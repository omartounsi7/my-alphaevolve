"""Problem: find the global minimum of f(x, y) = sin(x) * cos(y) + sin(x * y) + (x^2 + y^2) / 20.

The function has many local minima. Improve search_algorithm so that it reliably
finds the global minimum, escaping the local minima that trap simple algorithms.
Keep evaluate_function and run_search unchanged: the evaluation calls run_search(),
which returns (x, y, value), where value = f(x, y).

The score, higher is better, grows as value gets closer to the global minimum's
value and as (x, y) gets closer to its position. A program that does well on one
call of run_search is scored again on 10 calls, and must then succeed every time.
Each call must finish within 5 seconds.

This is OpenEvolve's function minimization example: the code below is theirs,
with type hints added.
"""

import numpy as np


def search_algorithm(
    iterations: int = 1000, bounds: tuple[float, float] = (-5, 5)
) -> tuple[float, float, float]:
    """
    A simple random search algorithm that often gets stuck in local minima.

    Args:
        iterations: Number of iterations to run
        bounds: Bounds for the search space (min, max)

    Returns:
        Tuple of (best_x, best_y, best_value)
    """
    # Initialize with a random point
    best_x = np.random.uniform(bounds[0], bounds[1])
    best_y = np.random.uniform(bounds[0], bounds[1])
    best_value = evaluate_function(best_x, best_y)

    for _ in range(iterations):
        # Simple random search
        x = np.random.uniform(bounds[0], bounds[1])
        y = np.random.uniform(bounds[0], bounds[1])
        value = evaluate_function(x, y)

        if value < best_value:
            best_value = value
            best_x, best_y = x, y

    return best_x, best_y, best_value


def evaluate_function(x: float, y: float) -> float:
    """The complex function we're trying to minimize"""
    return float(np.sin(x) * np.cos(y) + np.sin(x * y) + (x**2 + y**2) / 20)


def run_search() -> tuple[float, float, float]:
    x, y, value = search_algorithm()
    return x, y, value
