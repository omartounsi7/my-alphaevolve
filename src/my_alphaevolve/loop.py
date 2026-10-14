"""The main evolution loop that ties all the building blocks together."""

from pathlib import Path

from my_alphaevolve.database import Database
from my_alphaevolve.evaluator import Evaluator
from my_alphaevolve.llm import LLM, LLMError
from my_alphaevolve.problem import Problem
from my_alphaevolve.program import Program
from my_alphaevolve.prompt_sampler import PromptSampler
from my_alphaevolve.reply_parser import make_child_program
from my_alphaevolve.storage import RunStorage

# The run stops after this many iterations in a row without an LLM reply.
MAX_LLM_FAILURES_IN_A_ROW = 3


def run_my_alphaevolve(
    problem: Problem,
    llm: LLM,
    evaluator: Evaluator,
    iterations: int,
    output_folder: Path | None = None,
    seed: int | None = None,
) -> Database:
    """Run the evolutionary search on the user's problem from start to finish.

    llm proposes improved programs; evaluator scores them. iterations is how many
    programs to ask the LLM for.

    output_folder is where every program and the best one are saved. If it already
    holds a saved run, that run is continued for iterations more iterations.
    None means nothing is saved.

    seed fixes the random choice of parents; the run is only fully repeatable if
    the LLM also gives the same replies.

    Ctrl+C stops the run early and keeps what was done. An iteration without an LLM
    reply is skipped; after MAX_LLM_FAILURES_IN_A_ROW in a row, the run stops.

    Returns the database of every program of the run, the initial one included.

    Raises ValueError if iterations is negative, if the user's initial program
    fails its evaluation, or if the saved run in output_folder cannot be read.
    """
    if iterations < 0:
        raise ValueError(f"iterations must be 0 or more, got {iterations}")

    database = Database(seed=seed)
    prompt_sampler = PromptSampler(problem.description, packages=problem.packages)
    storage = RunStorage(output_folder) if output_folder is not None else None

    # The programs of an earlier run in the same folder; empty for a new run.
    saved_programs = storage.load_programs() if storage is not None else []
    if saved_programs:
        # Continue the saved run: put its programs back with their saved scores.
        for saved_program in saved_programs:
            if saved_program.score is None:
                raise ValueError(f"The saved program {saved_program.id} has no score.")
            database.add(saved_program, saved_program.score)
        # Carry on counting where the saved run stopped.
        first_iteration = max(program.iteration for program in saved_programs) + 1
        print(f"Continuing the run saved in {output_folder}: {len(saved_programs)} programs")
    else:
        # Start a new run: score the initial program and store it as the first parent.
        initial_program = Program(problem.initial_code)
        results = evaluator.execute(initial_program)
        if results == evaluator.failure_score:
            # Evolution needs a working starting point.
            raise ValueError("The initial program failed its evaluation; fix it and run again.")
        database.add(initial_program, results)
        if storage is not None:
            storage.append_program(initial_program)
            storage.save_best_program(initial_program)
        first_iteration = 1
        print(f"Initial program: score={results}")

    last_iteration = first_iteration + iterations - 1
    llm_failures_in_a_row = 0

    try:
        for iteration in range(first_iteration, last_iteration + 1):
            # One step: pick a parent, prompt the LLM, parse the reply into a child,
            # score it and store it so that it can become a parent later.
            parent_program = database.sample()
            prompt = prompt_sampler.build(parent_program)
            try:
                reply = llm.generate(prompt)
            except LLMError as error:
                # No reply: this iteration produces no child.
                llm_failures_in_a_row += 1
                print(f"Iteration {iteration}/{last_iteration}: skipped, no reply ({error})")
                if llm_failures_in_a_row >= MAX_LLM_FAILURES_IN_A_ROW:
                    # The LLM is unreachable.
                    print(f"The LLM failed {llm_failures_in_a_row} times in a row; stopping.")
                    break
                continue
            llm_failures_in_a_row = 0
            child_program = make_child_program(parent_program, reply, iteration)
            results = evaluator.execute(child_program)
            database.add(child_program, results)

            best_program = database.get_best_program()
            if storage is not None:
                storage.append_program(child_program)
                if best_program is child_program:
                    storage.save_best_program(child_program)

            best_score = best_program.score if best_program is not None else None
            print(
                f"Iteration {iteration}/{last_iteration}: "
                f"child score={results} (generation {child_program.generation}), "
                f"best score={best_score}"
            )
    except KeyboardInterrupt:
        # Ctrl+C ends the run cleanly.
        print("\nStopped by the user.")
        if output_folder is not None:
            print(f"Run again with the same output folder to continue: {output_folder}")

    return database
