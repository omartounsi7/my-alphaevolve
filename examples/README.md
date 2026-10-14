# Examples

Both examples are OpenEvolve's
([function_minimization](https://github.com/algorithmicsuperintelligence/openevolve/tree/main/examples/function_minimization)
and [circle_packing](https://github.com/algorithmicsuperintelligence/openevolve/tree/main/examples/circle_packing)),
adapted to this project's format, so that runs start from the same baseline as
OpenEvolve's and can be compared with them.

- Source: OpenEvolve, commit `30d97520d4cc2db91e537ec4e9134462445ecaa0`.
- Licence: Apache License 2.0, copied in [LICENSE-openevolve](LICENSE-openevolve).

What is the same as in OpenEvolve:

- **The initial programs**: OpenEvolve's code, with type hints added. The functions
  OpenEvolve's evaluator calls (`run_search`, `run_packing`) keep their names,
  arguments and return values.
- **The scores**: `evaluation.py` computes OpenEvolve's `combined_score`, with
  the cascade evaluation their config files turn on.
- **The packages** programs may import (`requirements.txt`).

What changed:

- The problem description, which OpenEvolve keeps in the `system_message` of a
  config file, is the initial program's docstring here.
- `evaluate` receives the program's names (`namespace`) and returns the score
  alone, instead of receiving a file path and returning several metrics.
- The `EVOLVE-BLOCK` markers, the `if __name__ == "__main__":` block and circle
  packing's `visualize` function are left out: no evaluation runs them.
