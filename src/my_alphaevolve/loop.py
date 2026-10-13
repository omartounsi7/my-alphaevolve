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

# After this many iterations in a row without a reply from the LLM, the run stops:
# the LLM is probably unreachable, and what was found so far is worth keeping
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

    llm is the language model that proposes improved programs; the caller
    chooses it, so the loop works the same with a fake or a real one.

    evaluator is the judge that scores programs; the caller chooses it too:
    a ProcessEvaluator for real runs, an InProcessEvaluator for trusted code.

    iterations is how many times the evolution step is repeated; each
    repetition asks the LLM for one new program.

    output_folder is where the run is saved: every program as it is made, and
    the best one so far. If the folder already holds a saved run, that run is
    continued for iterations more iterations instead of starting again.
    None means nothing is saved.

    seed fixes the random choice of parents, so that it can be repeated
    exactly; None gives different choices every time. The run as a whole is
    only repeatable if the LLM also gives the same replies.

    The run can be stopped early with Ctrl+C; what was done until then is kept.

    An iteration in which the LLM gives no reply is skipped. After
    MAX_LLM_FAILURES_IN_A_ROW such iterations in a row, the run stops early.

    Returns the database holding every program of the run, the initial one
    included; its get_best_program method gives the best solution found.

    Raises ValueError if iterations is negative, if the user's initial program
    fails its evaluation, or if the saved run in output_folder cannot be read.
    """
    if iterations < 0:
        raise ValueError(f"iterations must be 0 or more, got {iterations}")

    # The memory of the search; created once and reused for the whole run
    database = Database(seed=seed)
    # The writer of prompts for the LLM; created once and reused for the whole run
    prompt_sampler = PromptSampler(problem.description)
    # The keeper of the run's files; None when the run is not saved
    storage = RunStorage(output_folder) if output_folder is not None else None

    # The programs of an earlier run in the same folder; empty for a new run
    saved_programs = storage.load_programs() if storage is not None else []
    if saved_programs:
        # Continue the saved run: put its programs back, with the scores they already have
        for saved_program in saved_programs:
            if saved_program.score is None:
                raise ValueError(f"The saved program {saved_program.id} has no score.")
            database.add(saved_program, saved_program.score)
        # Carry on counting iterations where the saved run stopped
        first_iteration = max(program.iteration for program in saved_programs) + 1
        print(f"Continuing the run saved in {output_folder}: {len(saved_programs)} programs")
    else:
        # Start a new run: score the user's initial solution, then store it as the
        # first possible parent
        initial_program = Program(problem.initial_code)
        results = evaluator.execute(initial_program)
        if results == evaluator.failure_score:
            # Evolution needs a working starting point, so stop now with a clear message
            raise ValueError("The initial program failed its evaluation; fix it and run again.")
        database.add(initial_program, results)
        if storage is not None:
            storage.append_program(initial_program)
            storage.save_best_program(initial_program)
        first_iteration = 1
        print(f"Initial program: score={results}")

    # The number of the last iteration of this session
    last_iteration = first_iteration + iterations - 1
    # How many iterations in a row just ended without a reply from the LLM
    llm_failures_in_a_row = 0

    try:
        # The evolution loop. range(a, b + 1) counts a, a + 1, ..., b
        for iteration in range(first_iteration, last_iteration + 1):
            # One complete step of evolution: pick a parent, write its prompt, ask the
            # LLM for an improved program, turn its reply into a child, score the child
            # and store it so that it can become a parent in a later iteration.
            parent_program = database.sample()
            prompt = prompt_sampler.build(parent_program)
            try:
                reply = llm.generate(prompt)
            except LLMError as error:
                # No reply this time (network trouble, a busy server...): this
                # iteration produces no child, and the run carries on
                llm_failures_in_a_row += 1
                print(f"Iteration {iteration}/{last_iteration}: skipped, no reply ({error})")
                if llm_failures_in_a_row >= MAX_LLM_FAILURES_IN_A_ROW:
                    # The LLM seems to be unreachable: going on would only repeat the failure
                    print(f"The LLM failed {llm_failures_in_a_row} times in a row; stopping.")
                    # break leaves the for loop at once
                    break
                # continue skips the rest of this iteration and moves on to the next one
                continue
            llm_failures_in_a_row = 0
            child_program = make_child_program(parent_program, reply, iteration)
            results = evaluator.execute(child_program)
            # A child that failed is stored too, with the failure score
            database.add(child_program, results)

            best_program = database.get_best_program()
            if storage is not None:
                # Save the child right away, so that stopping the run loses nothing
                storage.append_program(child_program)
                if best_program is child_program:
                    # The child beat every earlier program: it is the new best
                    storage.save_best_program(child_program)

            # One line of progress, so a long run can be followed as it goes
            best_score = best_program.score if best_program is not None else None
            print(
                f"Iteration {iteration}/{last_iteration}: "
                f"child score={results} (generation {child_program.generation}), "
                f"best score={best_score}"
            )
    except KeyboardInterrupt:
        # Raised by Python when the user presses Ctrl+C: end the run calmly
        # instead of crashing. Every finished iteration is already stored.
        print("\nStopped by the user.")
        if output_folder is not None:
            print(f"Run again with the same output folder to continue: {output_folder}")

    return database
