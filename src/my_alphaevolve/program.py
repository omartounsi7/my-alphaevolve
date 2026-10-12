"""The Program class: one candidate solution in the evolutionary search."""

import uuid


class Program:
    """One candidate solution: a piece of code plus what we know about it."""

    def __init__(
        self,
        code: str,
        score: float | None = None,
        parent_id: str | None = None,
        generation: int = 0,
    ) -> None:
        # Unique id for this program
        self.id: str = str(uuid.uuid4())
        # The source code of the program
        self.code: str = code
        # How good the program is (higher is better); None = not evaluated yet
        self.score: float | None = score
        # The id of the parent program this one was made from; None for the initial program
        self.parent_id: str | None = parent_id
        # How many mutation steps separate this program from the initial one
        self.generation: int = generation

    def __repr__(self) -> str:
        """Return the text shown by print(program).

        Example: Program(id=3f2a9c1e, score=1.0, generation=0)
        """
        return f"Program(id={self.id[:8]}, score={self.score}, generation={self.generation})"
