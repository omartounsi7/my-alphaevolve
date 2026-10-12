from program import Program
import random


class Database:
    def __init__(self):
        # All stored programs, as a dictionary: program id -> Program object
        self.programs: dict[str, Program] = {}

    def add(self, program):
        # Store a program under using its id
        self.programs[program.id] = program

    def sample(self):
        # Pick the parent for the next mutation. For now: random. Later: Evolutionary algorithms
        return random.choice(list(self.programs.values()))

    def best(self):
        # Return the highest-scoring program, skipping ones not evaluated yet
        best_program = None
        for program in self.programs.values():
            if program.score is None:
                continue
            if best_program is None or program.score > best_program.score:
                best_program = program
        return best_program