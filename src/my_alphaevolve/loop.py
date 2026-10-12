"""The main evolution loop that ties all the building blocks together."""

from my_alphaevolve.database import Database
from my_alphaevolve.evaluator import Evaluator
from my_alphaevolve.problem import Problem
from my_alphaevolve.program import Program


def run_my_alphaevolve(problem: Problem) -> None:
    """Run the evolutionary search on the user's problem from start to finish.

    Raises ValueError if the user's initial program fails its evaluation.
    """
    print("hello from my alphaevolve!")

    # The memory of the search; created once and reused for the whole run
    database = Database()
    # The judge that scores programs with the user's criteria; created once and reused
    evaluator = Evaluator(problem.score_function)

    # Score the user's initial solution, then store it as the first possible parent
    initial_program = Program(problem.initial_code)
    results = evaluator.execute(initial_program)
    if results == evaluator.failure_score:
        # Evolution needs a working starting point, so stop now with a clear message
        raise ValueError("The initial program failed its evaluation; fix it and run again.")
    database.add(initial_program, results)

    print(f"Best program so far: {database.get_best_program()}")

    # parent_program = database.sample()
    # prompt = prompt_sampler.build(parent_program)
    # diff = llm.generate(prompt)
    # child_program = apply_diff(parent_program, diff)
    # results = evaluator.execute(child_program)
    # database.add(child_program, results)
