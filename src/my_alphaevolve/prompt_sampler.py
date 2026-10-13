"""The PromptSampler class: writes the text that is sent to the LLM."""

from my_alphaevolve.program import Program

# The text sent to the LLM, with three blanks that are filled in for each parent:
# {description} becomes the problem description, {score} the parent's score
# and {code} the parent's source code
PROMPT_TEMPLATE = """\
Problem description:
{description}

Here is a program and its score. Improve it so the score gets higher.

Score: {score}

Program:
```python
{code}
```

Reply with only the complete new program, as Python code. Do not write any \
text outside the code: put every explanation in comments inside the code.
"""


class PromptSampler:
    """Builds the prompt that asks the LLM to improve a parent program."""

    def __init__(self, problem_description: str, template: str = PROMPT_TEMPLATE) -> None:
        # What the problem is, in plain words; the same in every prompt of a run
        self.problem_description: str = problem_description
        # The prompt text with its {description}, {score} and {code} blanks still unfilled
        self.template: str = template

    def build(self, parent_program: Program) -> str:
        """Return the prompt for one parent program, ready to send to the LLM.

        Raises ValueError if the parent has not been evaluated yet.
        """
        if parent_program.score is None:
            # A prompt saying "Score: None" would only confuse the LLM
            raise ValueError("Cannot build a prompt from a program that has no score.")
        return self.template.format(
            description=self.problem_description,
            score=parent_program.score,
            # strip() removes blank lines at the start and end of the code
            code=parent_program.code.strip(),
        )
