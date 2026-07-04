import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main as main_module


def test_main_returns_zero_when_no_errors(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "run",
        lambda: {"fetched": 2, "triaged_out": 1, "drafted": 1, "needs_human": 0, "errored": 0},
    )
    assert main_module.main() == 0


def test_main_returns_nonzero_when_any_email_errored(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "run",
        lambda: {"fetched": 2, "triaged_out": 0, "drafted": 1, "needs_human": 0, "errored": 1},
    )
    assert main_module.main() == 1
