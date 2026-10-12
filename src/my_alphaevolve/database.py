"""The Database class: the memory of the evolutionary search."""

import random

from my_alphaevolve.program import Program


class Database:
    """Stores every program produced so far and picks which one to mutate next."""

    def __init__(self) -> None:
        # All stored programs, as a dictionary: program id -> Program object
        self.programs: dict[str, Program] = {}

    def add(self, program: Program, results: float) -> None:
        """Store a program and its score under its id."""
        program.score = results
        self.programs[program.id] = program

    def get(self, program_id: str) -> Program | None:
        """Look up one program by its id (returns None if no program has that id)."""
        return self.programs.get(program_id)

    def sample(self) -> Program:
        """Pick the parent for the next mutation.

        For now: random. Later: Evolutionary algorithms.
        """
        if not self.programs:
            # Fail with a clear message instead of random.choice's cryptic one
            raise ValueError("Cannot sample from an empty database; add a program first.")
        return random.choice(list(self.programs.values()))

    def get_best_program(self) -> Program | None:
        """Return the highest-scoring program (None if the database is empty)."""
        best_program: Program | None = None
        # The score of best_program, kept separately so it is always a plain number
        best_score = float("-inf")
        for program in self.programs.values():
            if program.score is None:
                continue
            if best_program is None or program.score > best_score:
                best_program = program
                best_score = program.score
        return best_program
