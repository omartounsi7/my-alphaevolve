"""The main evolution loop that ties all the building blocks together."""

from my_alphaevolve.database import Database


def run_my_alphaevolve() -> None:
    """Run the evolutionary search from start to finish."""
    print("hello from my alphaevolve!")

    # The memory of the search; not used yet because the loop below is still a plan
    database = Database()  # noqa: F841

    # parent_program = database.sample()
    # prompt = prompt_sampler.build(parent_program)
    # diff = llm.generate(prompt)
    # child_program = apply_diff(parent_program, diff)
    # results = evaluator.execute(child_program)
    # database.add(child_program, results)
