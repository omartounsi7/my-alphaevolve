"""The evaluation criteria for the circle packing example.

They compute the score of OpenEvolve's examples/circle_packing/evaluator.py, run
with its config_phase_1.yaml (cascade evaluation, thresholds 0.5 and 0.75): the
sum of the radii of a valid packing divided by 2.635, or 0. Both of OpenEvolve's
stages compute this score, so a program scoring at least 0.5 is run a second
time, and the second score replaces the first.
"""

from collections.abc import Callable
from typing import Any

import numpy as np

# The function every program must define.
FUNCTION_NAME = "run_packing"
NUMBER_OF_CIRCLES = 26
# The sum the AlphaEvolve paper reached, which scores are divided by.
TARGET_VALUE = 2.635
# Allowed numerical error.
TOLERANCE = 1e-6
# The score stage 1 must reach for stage 2 to run.
STAGE_2_THRESHOLD = 0.5


def validate_packing(centers: Any, radii: Any) -> bool:
    """Tell whether every circle is inside the unit square and no two circles overlap."""
    if np.isnan(centers).any() or np.isnan(radii).any():
        return False
    for (x, y), r in zip(centers, radii, strict=True):
        if r < 0:
            return False
        if (
            x - r < -TOLERANCE
            or x + r > 1 + TOLERANCE
            or y - r < -TOLERANCE
            or y + r > 1 + TOLERANCE
        ):
            return False
    for i in range(NUMBER_OF_CIRCLES):
        for j in range(i + 1, NUMBER_OF_CIRCLES):
            dist = np.sqrt(np.sum((centers[i] - centers[j]) ** 2))
            if dist < radii[i] + radii[j] - TOLERANCE:
                return False
    return True


def packing_score(run_packing: Callable[[], Any]) -> float:
    """Call run_packing and score its packing; any failure scores 0, as in OpenEvolve."""
    try:
        centers, radii, _ = run_packing()
        centers = np.asarray(centers)
        radii = np.asarray(radii)
        if centers.shape != (NUMBER_OF_CIRCLES, 2) or radii.shape != (NUMBER_OF_CIRCLES,):
            return 0.0
        if not validate_packing(centers, radii):
            return 0.0
        return float(np.sum(radii) / TARGET_VALUE)
    except Exception:
        return 0.0


def evaluate(namespace: dict[str, Any]) -> float:
    """Return the program's score, as OpenEvolve computes it (higher is better)."""
    if FUNCTION_NAME not in namespace:
        return 0.0
    run_packing = namespace[FUNCTION_NAME]
    score = packing_score(run_packing)
    if score < STAGE_2_THRESHOLD:
        return score
    return packing_score(run_packing)
