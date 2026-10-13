"""Turns the LLM's reply, which is plain text, into a child Program."""

import re

from my_alphaevolve.program import Program

# Describes what a code block looks like in a reply, so that every one can be found:
#   ```          the three backticks that open the block
#   [^\n`]*      an optional language name such as "python", up to the end of the line
#   \n           the end of that opening line
#   (.*?)        the code itself; the parentheses mark the part we want to keep
#   ```          the three backticks that close the block
# re.DOTALL lets the code span several lines.
CODE_BLOCK_PATTERN = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)

# The same, for a block that is opened but never closed (a reply that was cut short)
UNCLOSED_CODE_BLOCK_PATTERN = re.compile(r"```[^\n`]*\n(.*)", re.DOTALL)


def extract_code(reply: str) -> str:
    """Return the program contained in an LLM's reply.

    The prompt asks for code only, but an LLM does not always obey: it may wrap
    the code in a code block or write sentences around it. So:
    - if the reply has code blocks, the longest one is the program;
    - if a code block is opened but never closed, everything after its opening is;
    - if there is no code block at all, the whole reply is.
    """
    # The contents of every complete code block, in the order they appear
    code_blocks: list[str] = CODE_BLOCK_PATTERN.findall(reply)
    if code_blocks:
        # A reply may show small snippets before the full program; the full one is the longest
        code = max(code_blocks, key=len)
    else:
        unclosed_block = UNCLOSED_CODE_BLOCK_PATTERN.search(reply)
        # group(1) is the part of the match inside the parentheses of the pattern
        code = unclosed_block.group(1) if unclosed_block else reply
    # Remove blank lines around the code, and end it with exactly one line break
    return code.strip() + "\n"


def make_child_program(parent_program: Program, reply: str) -> Program:
    """Create the child Program that an LLM's reply proposes for a parent.

    The child is not evaluated yet: its score stays None until the Evaluator runs it.
    """
    return Program(
        code=extract_code(reply),
        # Remember where the child came from, so its ancestry can be traced
        parent_id=parent_program.id,
        # The child is one mutation step further from the initial program than its parent
        generation=parent_program.generation + 1,
    )
