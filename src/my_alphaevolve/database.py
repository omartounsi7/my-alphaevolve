"""The Database class: the memory of the evolutionary search.

Parents are chosen with MAP-Elites. Working programs are placed in a grid of
cells according to two features of their code, complexity and diversity; each
cell keeps its best program, its elite; and a parent is an elite picked at random.
"""

import math
import random

from my_alphaevolve.program import Program

# Bins per feature: the grid has at most this number squared of cells.
DEFAULT_BINS_PER_FEATURE = 10
# How many programs the diversity of a program is measured against, as in OpenEvolve.
DIVERSITY_REFERENCE_SIZE = 20

# A cell of the grid: the bin of each feature.
Cell = tuple[int, int]


def score_of(program: Program) -> float:
    """Return a program's score as a number."""
    return program.score if program.score is not None else float("-inf")


def code_complexity(code: str) -> float:
    """Return the complexity of a program: the length of its code, as in OpenEvolve."""
    return float(len(code))


def code_difference(first: str, second: str) -> float:
    """Return a quick estimate of how different two programs are; 0 for identical code.

    OpenEvolve's formula: it combines the differences in length, in number of
    lines, and in the set of characters used.
    """
    if first == second:
        return 0.0
    length_difference = abs(len(first) - len(second))
    line_difference = abs(first.count("\n") - second.count("\n"))
    character_difference = len(set(first) ^ set(second))
    return length_difference * 0.1 + line_difference * 10 + character_difference * 0.5


def feature_bin(value: float, lowest: float, highest: float, bins: int) -> int:
    """Return which of bins equal slices of [lowest, highest] the value falls in."""
    if highest == lowest:
        return bins // 2
    position = (value - lowest) / (highest - lowest)
    return min(bins - 1, int(position * bins))


class Database:
    """Stores every program produced so far and picks which one to mutate next."""

    def __init__(
        self,
        bins_per_feature: int = DEFAULT_BINS_PER_FEATURE,
        seed: int | None = None,
    ) -> None:
        """Create an empty database.

        bins_per_feature sets the size of the grid; seed fixes the random picks,
        so that they can be repeated.
        """
        if bins_per_feature < 1:
            raise ValueError(f"bins_per_feature must be 1 or more, got {bins_per_feature}")
        self.programs: dict[str, Program] = {}
        self.bins_per_feature: int = bins_per_feature
        self.random_generator: random.Random = random.Random(seed)
        # The code of the first working programs: diversity is measured against them.
        self.reference_codes: list[str] = []
        # The diversity of each code against the current reference programs.
        self._diversity_cache: dict[str, float] = {}

    def add(self, program: Program, results: float) -> None:
        """Store a program and its score under its id."""
        program.score = results
        self.programs[program.id] = program
        if (
            math.isfinite(results)
            and len(self.reference_codes) < DIVERSITY_REFERENCE_SIZE
            and program.code not in self.reference_codes
        ):
            self.reference_codes.append(program.code)
            self._diversity_cache.clear()

    def get(self, program_id: str) -> Program | None:
        """Look up one program by its id (returns None if no program has that id)."""
        return self.programs.get(program_id)

    def get_working_programs(self) -> list[Program]:
        """Return the programs whose evaluation succeeded, in the order they were added.

        A failed program has the score minus infinity, which is not a finite number.
        """
        return [
            program
            for program in self.programs.values()
            if program.score is not None and math.isfinite(program.score)
        ]

    def diversity(self, code: str) -> float:
        """Return how different a program is, on average, from the reference programs."""
        if code not in self._diversity_cache:
            differences = [
                code_difference(code, reference)
                for reference in self.reference_codes
                if reference != code
            ]
            self._diversity_cache[code] = (
                sum(differences) / len(differences) if differences else 0.0
            )
        return self._diversity_cache[code]

    def get_elites(self) -> dict[Cell, Program]:
        """Return the map of elites: the best program of each occupied cell.

        The map is rebuilt from all working programs each time, so the bins
        always span the range of values seen so far. A program takes a cell
        from its elite only with a strictly higher score.
        """
        working_programs = self.get_working_programs()
        features = [
            (code_complexity(program.code), self.diversity(program.code))
            for program in working_programs
        ]
        if not features:
            return {}
        lowest = [min(values[index] for values in features) for index in range(2)]
        highest = [max(values[index] for values in features) for index in range(2)]

        elites: dict[Cell, Program] = {}
        for program, values in zip(working_programs, features, strict=True):
            cell = (
                feature_bin(values[0], lowest[0], highest[0], self.bins_per_feature),
                feature_bin(values[1], lowest[1], highest[1], self.bins_per_feature),
            )
            elite = elites.get(cell)
            if elite is None or score_of(program) > score_of(elite):
                elites[cell] = program
        return elites

    def sample(self) -> Program:
        """Pick the parent for the next mutation: an elite of the map, at random.

        Failed programs are never in the map, so they are only picked if the
        database holds nothing else.

        Raises ValueError if the database is empty.
        """
        if not self.programs:
            raise ValueError("Cannot sample from an empty database; add a program first.")
        elites = list(self.get_elites().values())
        if not elites:
            return self.random_generator.choice(list(self.programs.values()))
        return self.random_generator.choice(elites)

    def get_best_program(self) -> Program | None:
        """Return the highest-scoring program (None if the database is empty)."""
        best_program: Program | None = None
        best_score = float("-inf")
        for program in self.programs.values():
            if program.score is None:
                continue
            if best_program is None or program.score > best_score:
                best_program = program
                best_score = program.score
        return best_program
