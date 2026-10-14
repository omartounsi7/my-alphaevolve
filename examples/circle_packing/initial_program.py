"""Problem: pack 26 circles into a unit square, making the sum of their radii as large as possible.

Write a function construct_packing() that takes no arguments and returns two values:

- centers: the 26 circle centers, as a list of (x, y) pairs or a numpy array of shape (26, 2);
- radii: the 26 radii, in the same order, as a list or a numpy array of shape (26,).

Every packing must follow these rules, checked with a tolerance of 1e-6:

- each circle lies entirely inside the square [0, 1] x [0, 1];
- no two circles overlap;
- no radius is negative, and no value is nan or infinite.

The score is the sum of the radii, and a packing that breaks a rule fails, so a
higher sum is better. construct_packing must finish within the run's time limit
(30 seconds by default). AlphaEvolve reported a sum of about 2.635 for 26 circles.
"""

import math


def construct_packing() -> tuple[list[tuple[float, float]], list[float]]:
    """Return the centers and radii of 26 circles: one in the middle, two rings, one in a corner."""
    centers = [(0.5, 0.5)]
    for i in range(8):
        angle = 2 * math.pi * i / 8
        centers.append((0.5 + 0.3 * math.cos(angle), 0.5 + 0.3 * math.sin(angle)))
    # The outer ring is too wide for the square: its circles are pushed back inside below.
    for i in range(16):
        angle = 2 * math.pi * i / 16
        centers.append((0.5 + 0.7 * math.cos(angle), 0.5 + 0.7 * math.sin(angle)))
    centers.append((0.0, 0.0))
    centers = [(min(max(x, 0.01), 0.99), min(max(y, 0.01), 0.99)) for x, y in centers]
    return centers, compute_max_radii(centers)


def compute_max_radii(centers: list[tuple[float, float]]) -> list[float]:
    """Return the largest radii for these centers that keep circles apart and inside the square."""
    # Start from the distance to the nearest side of the square.
    radii = [min(x, y, 1 - x, 1 - y) for x, y in centers]
    # Shrink each overlapping pair in proportion until they just touch.
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            distance = math.dist(centers[i], centers[j])
            if radii[i] + radii[j] > distance:
                scale = distance / (radii[i] + radii[j])
                radii[i] *= scale
                radii[j] *= scale
    return radii
