from program import Program
import random


class Database:
    """Stores every program produced so far and picks which one to mutate next."""

    def __init__(self):
        # All stored programs, as a dictionary: program id -> Program object
        self.programs: dict[str, Program] = {}

    def add(self, program, results):
        # Store a program and its score under its id
        program.score = results
        self.programs[program.id] = program

    def get(self, program_id):
        # Look up one program by its id (returns None if no program has that id)
        return self.programs.get(program_id)

    def sample(self):
        # Pick the parent for the next mutation. For now: random. Later: Evolutionary algorithms
        return random.choice(list(self.programs.values()))

    def best(self):
        # Return the highest-scoring program
        best_program = None
        for program in self.programs.values():
            if program.score is None:
                continue
            if best_program is None or program.score > best_program.score:
                best_program = program
        return best_program