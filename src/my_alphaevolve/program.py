"""The Program class: one candidate solution in the evolutionary search."""

import uuid
from typing import Any


class Program:
    """One candidate solution: a piece of code plus what we know about it."""

    def __init__(
        self,
        code: str,
        score: float | None = None,
        parent_id: str | None = None,
        generation: int = 0,
        iteration: int = 0,
        program_id: str | None = None,
    ) -> None:
        # Unique id for this program.
        self.id: str = program_id if program_id is not None else str(uuid.uuid4())
        # The source code of the program
        self.code: str = code
        # How good the program is (higher is better); None = not evaluated yet
        self.score: float | None = score
        # The id of the parent program this one was made from; None for the initial program
        self.parent_id: str | None = parent_id
        # How many mutation steps separate this program from the initial one
        self.generation: int = generation
        # The iteration of the run in which this program was made; 0 for the initial program
        self.iteration: int = iteration

    def __repr__(self) -> str:
        """Return the text shown by print(program).

        Example: Program(id=3f2a9c1e, score=1.0, generation=0)
        """
        return f"Program(id={self.id[:8]}, score={self.score}, generation={self.generation})"

    def to_dict(self) -> dict[str, Any]:
        """Return everything known about this program as a dictionary of plain values."""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "generation": self.generation,
            "iteration": self.iteration,
            "score": self.score,
            "code": self.code,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Program":
        """Rebuild a program from a dictionary made by to_dict, keeping its id."""
        return cls(
            code=data["code"],
            score=data["score"],
            parent_id=data["parent_id"],
            generation=data["generation"],
            iteration=data["iteration"],
            program_id=data["id"],
        )
