"""The PromptSampler class: writes the text that is sent to the LLM."""

from my_alphaevolve.program import Program

# The prompt, with blanks for the problem description, the parent's score and its code.
PROMPT_TEMPLATE = """\
Problem description:
{description}

Below is a Python program written to solve this problem, together with its \
score. The score measures how well the program solves the problem: the higher, \
the better.

Score: {score}

Program:
```python
{code}
```

Write an improved version of this program that solves the problem better, \
so that it gets a higher score.

Reply with only the complete new program, as Python code. Do not write any \
text outside the code: put every explanation in comments inside the code.
"""


class PromptSampler:
    """Builds the prompt that asks the LLM to improve a parent program."""

    def __init__(self, problem_description: str, template: str = PROMPT_TEMPLATE) -> None:
        self.problem_description: str = problem_description
        self.template: str = template

    def build(self, parent_program: Program) -> str:
        """Return the prompt for one parent program, ready to send to the LLM.

        Raises ValueError if the parent has not been evaluated yet.
        """
        if parent_program.score is None:
            raise ValueError("Cannot build a prompt from a program that has no score.")
        return self.template.format(
            description=self.problem_description,
            score=parent_program.score,
            code=parent_program.code.strip(),
        )
