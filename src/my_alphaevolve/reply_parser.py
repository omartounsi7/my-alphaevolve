"""Turns the LLM's reply, which is plain text, into a child Program."""

import ast
import re

from my_alphaevolve.program import Program

# Describes what a code block looks like in a reply, so that every one can be found.
# A code block starts with a line of three backticks, optionally followed by a
# language name, and ends with a line holding only three backticks:
#   ^[ \t]*```      three backticks at the start of a line (spaces before are allowed)
#   [^\n`]*\n       an optional language name such as "python", up to the end of the line
#   (.*?)           the code itself; the parentheses mark the part we want to keep
#   ^[ \t]*```      three backticks at the start of a later line
#   [ \t]*$         and nothing else on that line
# Asking for the backticks to stand alone on their line matters: three backticks
# that appear inside the code, for example in a piece of text, do not end the block.
# re.DOTALL lets the code span several lines; re.MULTILINE makes ^ and $ mean
# "start of a line" and "end of a line" instead of start and end of the whole reply.
CODE_BLOCK_PATTERN = re.compile(
    r"^[ \t]*```[^\n`]*\n(.*?)^[ \t]*```[ \t]*$", re.DOTALL | re.MULTILINE
)

# A code block squeezed onto a single line: three backticks, the code, three backticks
ONE_LINE_CODE_BLOCK_PATTERN = re.compile(r"```(.+?)```")

# A code block that is opened but never closed (a reply that was cut short)
UNCLOSED_CODE_BLOCK_PATTERN = re.compile(r"^[ \t]*```[^\n`]*\n(.*)", re.DOTALL | re.MULTILINE)

# Everything from the first opening line of backticks to the last closing one.
# Unlike CODE_BLOCK_PATTERN, the code part (.*) is "greedy": it takes as much as it can.
WIDEST_CODE_BLOCK_PATTERN = re.compile(
    r"^[ \t]*```[^\n`]*\n(.*)^[ \t]*```[ \t]*$", re.DOTALL | re.MULTILINE
)

# Some models write their reasoning before the answer, between <think> and </think>.
# It is not part of the program, and may even contain code they then discard.
THINKING_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def is_valid_python(code: str) -> bool:
    """Tell whether a piece of text is Python code that could be run.

    The code is only read, not run. This checks its grammar, not what it does.
    """
    try:
        ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    return True


def is_same_program(first_code: str, second_code: str) -> bool:
    """Tell whether two pieces of code are the same program.

    Comments, blank lines and spacing are ignored: only what Python would
    actually run is compared. Code that is not valid Python is never "the same".
    """
    try:
        # ast.dump writes out the structure of the code, without comments or layout
        return ast.dump(ast.parse(first_code)) == ast.dump(ast.parse(second_code))
    except (SyntaxError, ValueError):
        return False


def choose_code_block(code_blocks: list[str], reply: str, parent_code: str | None) -> str:
    """Return the code block of a reply most likely to be the new program.

    A reply can hold several code blocks: the original program quoted back, a
    sample of output, a small snippet shown before the full program... Three
    rules are applied in turn, each only if it leaves at least one block:

    1. keep the blocks that are valid Python;
    2. drop the blocks that merely repeat the parent program;
    3. keep the longest block.
    """
    candidates = [block for block in code_blocks if is_valid_python(block)]
    if not candidates:
        # No block is valid on its own. The program may itself contain lines of
        # three backticks, which cut it into pieces: try the widest span instead.
        widest_block = WIDEST_CODE_BLOCK_PATTERN.search(reply)
        if widest_block and is_valid_python(widest_block.group(1)):
            return widest_block.group(1)
        # Nothing is valid Python: fall back on every block, and let evaluation fail
        candidates = code_blocks

    if parent_code is not None:
        new_blocks = [block for block in candidates if not is_same_program(block, parent_code)]
        if new_blocks:
            candidates = new_blocks

    # A reply may show small snippets next to the full program; the full one is the longest
    return max(candidates, key=len)


def extract_code(reply: str, parent_code: str | None = None) -> str:
    """Return the program contained in an LLM's reply.

    The prompt asks for code only, but an LLM does not always obey: it may wrap
    the code in a code block or write sentences around it. So:
    - if the reply has code blocks, the most likely one is the program
      (see choose_code_block);
    - if a code block is opened but never closed, everything after its opening is;
    - if there is no code block at all, the whole reply is.

    parent_code is the code of the program the reply was asked to improve. When
    given, a code block that merely repeats it is not taken for the new program.
    """
    # Drop the reasoning that "thinking" models write before their answer
    reply = THINKING_PATTERN.sub("", reply)

    # The contents of every complete code block, in the order they appear
    code_blocks: list[str] = CODE_BLOCK_PATTERN.findall(reply)
    if not code_blocks:
        code_blocks = ONE_LINE_CODE_BLOCK_PATTERN.findall(reply)

    if code_blocks:
        code = choose_code_block(code_blocks, reply, parent_code)
    else:
        unclosed_block = UNCLOSED_CODE_BLOCK_PATTERN.search(reply)
        # group(1) is the part of the match inside the parentheses of the pattern
        code = unclosed_block.group(1) if unclosed_block else reply
    # Remove blank lines around the code, and end it with exactly one line break
    return code.strip() + "\n"


def make_child_program(parent_program: Program, reply: str, iteration: int = 0) -> Program:
    """Create the child Program that an LLM's reply proposes for a parent.

    iteration is the iteration of the run in which the child is made.
    The child is not evaluated yet: its score stays None until the Evaluator runs it.
    """
    return Program(
        code=extract_code(reply, parent_program.code),
        # Remember where the child came from, so its ancestry can be traced
        parent_id=parent_program.id,
        # The child is one mutation step further from the initial program than its parent
        generation=parent_program.generation + 1,
        iteration=iteration,
    )
