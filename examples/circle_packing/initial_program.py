"""Problem: pack 26 circles into a unit square, making the sum of their radii as large as possible.

Improve construct_packing, a constructor that directly produces a specific
arrangement of the 26 circles. Keep run_packing unchanged: the evaluation calls
run_packing(), which returns (centers, radii, sum_of_radii):

- centers: a numpy array of shape (26, 2), the (x, y) coordinates of the centers;
- radii: a numpy array of shape (26,), the radius of each circle.

A valid packing keeps every circle inside the square [0, 1] x [0, 1], with no two
circles overlapping and no negative or nan radius; errors up to 1e-6 are tolerated.
The score is the sum of the radii divided by 2.635, the sum the AlphaEvolve paper
reached, or 0 if the packing is not valid. A higher score is better.

Key geometric insights:
- Circle packings often follow hexagonal patterns in the densest regions
- Maximum density for infinite circle packing is pi/(2*sqrt(3)) ≈ 0.9069
- Edge effects make square container packing harder than infinite packing
- Circles can be placed in layers or shells when confined to a square
- Similar radius circles often form regular patterns, while varied radii allow better space
  utilization
- Perfect symmetry may not yield the optimal packing due to edge effects

Focus on designing an explicit constructor that places each circle in a specific
position, rather than an iterative search algorithm.

This is OpenEvolve's circle packing example: the code below is theirs, with type
hints added.
"""

import numpy as np
from numpy.typing import NDArray


def construct_packing() -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
    """
    Construct a specific arrangement of 26 circles in a unit square
    that attempts to maximize the sum of their radii.

    Returns:
        Tuple of (centers, radii, sum_of_radii)
        centers: np.array of shape (26, 2) with (x, y) coordinates
        radii: np.array of shape (26) with radius of each circle
        sum_of_radii: Sum of all radii
    """
    # Initialize arrays for 26 circles
    n = 26
    centers = np.zeros((n, 2))

    # Place circles in a structured pattern
    # This is a simple pattern - evolution will improve this

    # First, place a large circle in the center
    centers[0] = [0.5, 0.5]

    # Place 8 circles around it in a ring
    for i in range(8):
        angle = 2 * np.pi * i / 8
        centers[i + 1] = [0.5 + 0.3 * np.cos(angle), 0.5 + 0.3 * np.sin(angle)]

    # Place 16 more circles in an outer ring
    for i in range(16):
        angle = 2 * np.pi * i / 16
        centers[i + 9] = [0.5 + 0.7 * np.cos(angle), 0.5 + 0.7 * np.sin(angle)]

    # Additional positioning adjustment to make sure all circles
    # are inside the square and don't overlap
    # Clip to ensure everything is inside the unit square
    centers = np.clip(centers, 0.01, 0.99)

    # Compute maximum valid radii for this configuration
    radii = compute_max_radii(centers)

    # Calculate the sum of radii
    sum_radii = float(np.sum(radii))

    return centers, radii, sum_radii


def compute_max_radii(centers: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    Compute the maximum possible radii for each circle position
    such that they don't overlap and stay within the unit square.

    Args:
        centers: np.array of shape (n, 2) with (x, y) coordinates

    Returns:
        np.array of shape (n) with radius of each circle
    """
    n = centers.shape[0]
    radii = np.ones(n)

    # First, limit by distance to square borders
    for i in range(n):
        x, y = centers[i]
        # Distance to borders
        radii[i] = min(x, y, 1 - x, 1 - y)

    # Then, limit by distance to other circles
    # Each pair of circles with centers at distance d can have
    # sum of radii at most d to avoid overlap
    for i in range(n):
        for j in range(i + 1, n):
            dist = np.sqrt(np.sum((centers[i] - centers[j]) ** 2))

            # If current radii would cause overlap
            if radii[i] + radii[j] > dist:
                # Scale both radii proportionally
                scale = dist / (radii[i] + radii[j])
                radii[i] *= scale
                radii[j] *= scale

    return radii


def run_packing() -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
    """Run the circle packing constructor for n=26"""
    centers, radii, sum_radii = construct_packing()
    return centers, radii, sum_radii
