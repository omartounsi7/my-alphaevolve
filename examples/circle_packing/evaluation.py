"""The evaluation criteria for the circle packing example.

Every candidate program must define construct_packing(), returning the centers
and radii of 26 circles. The score is the sum of the radii of a valid packing.
"""

import itertools
import math
from typing import Any

# The function every program must define.
FUNCTION_NAME = "construct_packing"
NUMBER_OF_CIRCLES = 26
# Allowed numerical error, as in OpenEvolve's circle packing evaluator.
TOLERANCE = 1e-6


def to_numbers(values: Any, what: str) -> list[float]:
    """Return a sequence of numbers as a list of floats; numpy arrays are accepted too.

    Raises ValueError if values is not a sequence of finite real numbers.
    """
    # A numpy array or number turns itself into plain Python values.
    if hasattr(values, "tolist"):
        values = values.tolist()
    if not isinstance(values, list | tuple):
        raise ValueError(f"{what}: expected a list of numbers, got {type(values).__name__}")
    numbers = []
    for value in values:
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{what}: expected only numbers, got {type(value).__name__}")
        if not math.isfinite(value):
            raise ValueError(f"{what}: expected finite numbers, got {value}")
        numbers.append(float(value))
    return numbers


def validate_packing(centers: Any, radii: Any) -> tuple[list[tuple[float, float]], list[float]]:
    """Check that a packing follows the rules and return it as plain Python numbers.

    Raises ValueError with an explanation if any rule is broken.
    """
    if hasattr(centers, "tolist"):
        centers = centers.tolist()
    if not isinstance(centers, list | tuple) or len(centers) != NUMBER_OF_CIRCLES:
        raise ValueError(f"expected {NUMBER_OF_CIRCLES} centers")
    points = []
    for index, center in enumerate(centers):
        coordinates = to_numbers(center, f"center {index}")
        if len(coordinates) != 2:
            raise ValueError(f"center {index}: expected (x, y), got {len(coordinates)} numbers")
        points.append((coordinates[0], coordinates[1]))

    sizes = to_numbers(radii, "radii")
    if len(sizes) != NUMBER_OF_CIRCLES:
        raise ValueError(f"expected {NUMBER_OF_CIRCLES} radii, got {len(sizes)}")

    for index, ((x, y), radius) in enumerate(zip(points, sizes, strict=True)):
        if radius < 0:
            raise ValueError(f"circle {index} has a negative radius: {radius}")
        if min(x - radius, y - radius) < -TOLERANCE or max(x + radius, y + radius) > 1 + TOLERANCE:
            raise ValueError(f"circle {index} at ({x}, {y}) with radius {radius} leaves the square")

    for (i, first), (j, second) in itertools.combinations(enumerate(points), 2):
        distance = math.dist(first, second)
        if distance < sizes[i] + sizes[j] - TOLERANCE:
            raise ValueError(
                f"circles {i} and {j} overlap: distance {distance}, radii {sizes[i]} + {sizes[j]}"
            )
    return points, sizes


def evaluate(namespace: dict[str, Any]) -> float:
    """Return the sum of the radii of the program's packing (higher is better).

    Raises ValueError if the program breaks the rules.
    """
    if FUNCTION_NAME not in namespace:
        raise ValueError(f"the program does not define a function called {FUNCTION_NAME}")

    answer = namespace[FUNCTION_NAME]()
    if not isinstance(answer, list | tuple) or len(answer) != 2:
        raise ValueError(f"{FUNCTION_NAME} must return two values: centers and radii")

    _, radii = validate_packing(answer[0], answer[1])
    return sum(radii)
