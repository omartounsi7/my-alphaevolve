from my_alphaevolve.database import Database


def run_my_alphaevolve():
    print("hello from my alphaevolve!")

    database = Database()

    # parent_program = database.sample()
    # prompt = prompt_sampler.build(parent_program)
    # diff = llm.generate(prompt)
    # child_program = apply_diff(parent_program, diff)
    # results = evaluator.execute(child_program)
    # database.add(child_program, results)