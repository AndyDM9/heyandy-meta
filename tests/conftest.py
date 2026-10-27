import pytest


@pytest.fixture(autouse=True)
def paid_calls_in_a_sandbox(tmp_path, monkeypatch):
    """Fakes stand in for the API; the spend ledger goes to a temporary folder, never logs/."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HEYANDY_PAID_CALLS", "1")
