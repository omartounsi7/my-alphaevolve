"""Entry point: run this file to start my-alphaevolve."""

from my_alphaevolve.loop import run_my_alphaevolve


def main() -> None:
    """Start the evolutionary search."""
    run_my_alphaevolve()


# Only run main() when this file is launched directly, not when it is imported
if __name__ == "__main__":
    main()
