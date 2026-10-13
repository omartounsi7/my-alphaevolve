"""The RunStorage class: keeps the programs of a run in a folder on disk.

Saving lets a run be inspected afterwards, and stopped and continued later.
"""

import json
from pathlib import Path

from my_alphaevolve.program import Program

# The file holding every program of the run, one per line
PROGRAMS_FILE_NAME = "programs.jsonl"
# The file holding the code of the best program found so far
BEST_PROGRAM_FILE_NAME = "best_program.py"


class RunStorage:
    """Reads and writes the programs of one run in its output folder.

    Every program is written as one line of JSON, a standard text format for
    structured data, at the end of programs.jsonl. Adding a line costs the same
    however many programs are already saved, and a run that stops abruptly
    loses nothing that was already written.
    """

    def __init__(self, folder: Path) -> None:
        """Use the given folder for this run, creating it if it does not exist."""
        # The output folder of the run
        self.folder: Path = folder
        # The file with one line per program
        self.programs_path: Path = folder / PROGRAMS_FILE_NAME
        # The file with the code of the best program
        self.best_program_path: Path = folder / BEST_PROGRAM_FILE_NAME
        # parents=True also creates missing folders above it; exist_ok=True accepts an existing one
        folder.mkdir(parents=True, exist_ok=True)

    def append_program(self, program: Program) -> None:
        """Add one program at the end of the programs file."""
        # ensure_ascii=False keeps characters such as accents readable in the file.
        # A failed program's score, minus infinity, is written as -Infinity.
        line = json.dumps(program.to_dict(), ensure_ascii=False)
        # "a" opens the file for appending: what is written goes after what is there
        with self.programs_path.open("a", encoding="utf-8") as programs_file:
            programs_file.write(line + "\n")

    def load_programs(self) -> list[Program]:
        """Return every saved program, in the order they were saved.

        Returns an empty list if nothing has been saved in this folder yet.
        Raises ValueError if a line of the file cannot be read.
        """
        if not self.programs_path.is_file():
            return []
        lines = self.programs_path.read_text(encoding="utf-8").splitlines()

        programs: list[Program] = []
        for line_number, line in enumerate(lines, start=1):
            try:
                programs.append(Program.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                if line_number == len(lines):
                    # Only the last line is damaged: the run was cut off while writing it.
                    # Drop it, and rewrite the file so new lines are not glued to its remains.
                    self._rewrite_programs_file(programs)
                    break
                raise ValueError(
                    f"{self.programs_path}, line {line_number}: cannot read this program"
                ) from error
        return programs

    def save_best_program(self, program: Program) -> None:
        """Write the code of the best program so far, replacing the previous best."""
        # Comment lines saying where this code comes from, then the code itself
        header = (
            f"# Best program so far: score {program.score}, "
            f"found at iteration {program.iteration}\n"
            f"# Program id: {program.id}\n\n"
        )
        self.best_program_path.write_text(header + program.code, encoding="utf-8")

    def _rewrite_programs_file(self, programs: list[Program]) -> None:
        """Replace the programs file by one holding exactly the given programs."""
        lines = [json.dumps(program.to_dict(), ensure_ascii=False) for program in programs]
        self.programs_path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
