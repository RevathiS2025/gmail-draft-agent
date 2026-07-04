"""Entry point for the scheduled agent run (invoked hourly by GitHub Actions, PRD Section 10)."""

import logging

from src.orchestrator import run

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run()
