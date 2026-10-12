import uuid


class Program:
    """One candidate solution: a piece of code plus what we know about it."""

    def __init__(self, code, score=None, parent_id=None, generation=0):
        # Unique id for this program
        self.id = str(uuid.uuid4())
        # The source code of the program
        self.code = code
        # How good the program is (higher is better); None = not evaluated yet
        self.score = score
        # The id of the parent program this one was made from; None for the initial program
        self.parent_id = parent_id
        # How many mutation steps separate this program from the initial one
        self.generation = generation

    def __repr__(self):
        # This replaces what print(program) shows. Example: Program(id=3f2a9c1e, score=1.0, generation=0)
        return f"Program(id={self.id[:8]}, score={self.score}, generation={self.generation})"