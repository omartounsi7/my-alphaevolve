"""The main evolution loop that ties all the building blocks together."""

from my_alphaevolve.database import Database
from my_alphaevolve.evaluator import Evaluator
from my_alphaevolve.problem import INITIAL_CODE, score_function
from my_alphaevolve.program import Program


def run_my_alphaevolve() -> None:
    """Run the evolutionary search from start to finish."""
    print("hello from my alphaevolve!")

    # The memory of the search; created once and reused for the whole run
    database = Database()
    # The judge that scores programs; created once and reused for the whole run
    evaluator = Evaluator(score_function)

    # Score the starting program, then store it as the first possible parent
    initial_program = Program(INITIAL_CODE)
    results = evaluator.execute(initial_program)
    database.add(initial_program, results)

    print(f"Best program so far: {database.get_best_program()}")

    # parent_program = database.sample()
    # prompt = prompt_sampler.build(parent_program)
    # diff = llm.generate(prompt)
    # child_program = apply_diff(parent_program, diff)
    # results = evaluator.execute(child_program)
    # database.add(child_program, results)
