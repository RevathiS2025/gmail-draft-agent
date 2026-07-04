"""Entry point for the scheduled agent run (invoked hourly by GitHub Actions, PRD Section 10)."""

import logging
import sys

from src.orchestrator import run


def main() -> int:
    summary = run()
    return 1 if summary["errored"] > 0 else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(main())
