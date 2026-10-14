"""The main evolution loop that ties all the building blocks together."""

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

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

# How many iterations run at once when no other number is given.
DEFAULT_WORKERS = 1

# How often, in seconds, the main thread wakes up while waiting for workers.
# On Windows, Ctrl+C only reaches a thread that is awake.
WAKE_UP_SECONDS = 0.2


def wait_for_finished(running: dict[Future[tuple[Program, float]], int]) -> set[Future[Any]]:
    """Wait until at least one iteration in progress has finished, and return those that have."""
    while True:
        finished, _ = wait(running, timeout=WAKE_UP_SECONDS, return_when=FIRST_COMPLETED)
        if finished:
            return finished


def run_my_alphaevolve(
    problem: Problem,
    llm: LLM,
    evaluator: Evaluator,
    iterations: int,
    output_folder: Path | None = None,
    seed: int | None = None,
    workers: int = DEFAULT_WORKERS,
) -> Database:
    """Run the evolutionary search on the user's problem from start to finish.

    llm proposes improved programs; evaluator scores them. iterations is how many
    programs to ask the LLM for.

    output_folder is where every program and the best one are saved. If it already
    holds a saved run, that run is continued for iterations more iterations.
    None means nothing is saved.

    seed fixes the random choice of parents; the run is only fully repeatable if
    the LLM also gives the same replies, and with a single worker.

    workers is how many iterations run at once. Results are stored as they arrive,
    so with several workers they come in no fixed order.

    Ctrl+C stops the run early: nothing new starts, and the iterations in progress
    are finished and kept unless Ctrl+C is pressed again. An iteration without an
    LLM reply is skipped; after MAX_LLM_FAILURES_IN_A_ROW in a row, the run stops.

    Returns the database of every program of the run, the initial one included.

    Raises ValueError if iterations is negative, if workers is below 1, if the
    user's initial program fails its evaluation, or if the saved run in
    output_folder cannot be read.
    """
    if iterations < 0:
        raise ValueError(f"iterations must be 0 or more, got {iterations}")
    if workers < 1:
        raise ValueError(f"workers must be 1 or more, got {workers}")

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
    next_iteration = first_iteration
    llm_failures_in_a_row = 0
    stopping = False
    # The iterations in progress: each one's result to come, and its number.
    running: dict[Future[tuple[Program, float]], int] = {}

    def produce_child(
        parent_program: Program, prompt: str, iteration: int
    ) -> tuple[Program, float]:
        """Ask the LLM for a child of the parent and score it. Runs in a worker thread."""
        reply = llm.generate(prompt)
        child_program = make_child_program(parent_program, reply, iteration)
        return child_program, evaluator.execute(child_program)

    def record(future: Future[tuple[Program, float]]) -> None:
        """Store the result of a finished iteration. Runs in the main thread only."""
        nonlocal llm_failures_in_a_row, stopping
        iteration = running.pop(future)
        try:
            child_program, results = future.result()
        except LLMError as error:
            # No reply: this iteration produces no child.
            llm_failures_in_a_row += 1
            print(f"Iteration {iteration}/{last_iteration}: skipped, no reply ({error})")
            if llm_failures_in_a_row >= MAX_LLM_FAILURES_IN_A_ROW and not stopping:
                # The LLM is unreachable.
                print(f"The LLM failed {llm_failures_in_a_row} times in a row; stopping.")
                stopping = True
            return
        llm_failures_in_a_row = 0
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

    # Up to `workers` iterations run at once, each in its own thread. Threads suffice:
    # they spend their time waiting for the LLM's reply and for the program's container.
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        while running or (not stopping and next_iteration <= last_iteration):
            # Keep every worker busy. Parents are picked when an iteration starts, so
            # each one can descend from the children that have finished so far.
            while not stopping and next_iteration <= last_iteration and len(running) < workers:
                parent_program = database.sample()
                prompt = prompt_sampler.build(parent_program)
                future = pool.submit(produce_child, parent_program, prompt, next_iteration)
                running[future] = next_iteration
                next_iteration += 1
            for future in wait_for_finished(running):
                record(future)
    except KeyboardInterrupt:
        # Ctrl+C: start nothing new, but keep the programs already in progress.
        print("\nStopped by the user.")
        try:
            if running:
                print(f"Finishing the {len(running)} programs in progress (Ctrl+C to skip them)...")
            while running:
                for future in wait_for_finished(running):
                    record(future)
        except KeyboardInterrupt:
            print("Programs in progress skipped.")
        if output_folder is not None:
            print(f"Run again with the same output folder to continue: {output_folder}")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    return database
