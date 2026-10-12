import random


class Database:
    def __init__(self):
        self.programs = [] # The programs currently stored in the database

    def add(self, program): # Add a program to the database
        self.programs.append(program)

    def sample(self): # Sample a program from the database
        '''
        For now, we just return a random program. Later, we should implement
        the evolutionary algorithms AlphaEvolve talks about.
        '''
        return random.choice(self.programs) # For now, just return a random program