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