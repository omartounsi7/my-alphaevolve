"""The Database class: the memory of the evolutionary search."""

import math
import random

from my_alphaevolve.program import Program

# How many of the best programs form the archive that exploitation picks from.
DEFAULT_ARCHIVE_SIZE = 10
# How often the parent is picked from the archive (0.7 = 70% of the time).
DEFAULT_EXPLOITATION_RATIO = 0.7


def score_of(program: Program) -> float:
    """Return a program's score as a number."""
    return program.score if program.score is not None else float("-inf")


class Database:
    """Stores every program produced so far and picks which one to mutate next."""

    def __init__(
        self,
        archive_size: int = DEFAULT_ARCHIVE_SIZE,
        exploitation_ratio: float = DEFAULT_EXPLOITATION_RATIO,
        seed: int | None = None,
    ) -> None:
        """Create an empty database.

        archive_size and exploitation_ratio tune how sample picks parents.
        seed fixes the random picks, so that they can be repeated.
        """
        if archive_size < 1:
            raise ValueError(f"archive_size must be 1 or more, got {archive_size}")
        if not 0.0 <= exploitation_ratio <= 1.0:
            raise ValueError(f"exploitation_ratio must be from 0 to 1, got {exploitation_ratio}")
        self.programs: dict[str, Program] = {}
        self.archive_size: int = archive_size
        self.exploitation_ratio: float = exploitation_ratio
        self.random_generator: random.Random = random.Random(seed)

    def add(self, program: Program, results: float) -> None:
        """Store a program and its score under its id."""
        program.score = results
        self.programs[program.id] = program

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

    def get_top_programs(self, count: int) -> list[Program]:
        """Return the count best working programs, best first.

        Returns fewer if the database holds fewer working programs. Among
        programs with the same score, the one added first comes first.
        """
        ranked_programs = sorted(self.get_working_programs(), key=score_of, reverse=True)
        return ranked_programs[:count]

    def sample(self) -> Program:
        """Pick the parent for the next mutation.

        One of two strategies is chosen at random each time:

        - exploitation (exploitation_ratio of the time): a random program from
          the archive, the archive_size best programs. This refines what
          already works.
        - exploration (the rest of the time): a random working program, good
          or bad. This gives less successful ideas a chance to lead somewhere.

        Failed programs are never picked, unless the database holds nothing else.

        Raises ValueError if the database is empty.
        """
        if not self.programs:
            raise ValueError("Cannot sample from an empty database; add a program first.")

        working_programs = self.get_working_programs()
        if not working_programs:
            return self.random_generator.choice(list(self.programs.values()))

        if self.random_generator.random() < self.exploitation_ratio:
            return self.random_generator.choice(self.get_top_programs(self.archive_size))
        return self.random_generator.choice(working_programs)

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
