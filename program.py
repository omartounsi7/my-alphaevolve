import uuid


class Program:
    def __init__(self, code, score=None, parent_id=None, generation=0):
        self.id = str(uuid.uuid4())
        self.code = code
        self.score = score
        self.parent_id = parent_id
        self.generation = generation