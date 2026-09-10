import pytest

from coach import tools


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """Every test gets its own data directory and a fresh tools module state."""
    monkeypatch.setenv("COACH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("COACH_TEST", "1")
    tools.configure(None, None)
    yield
    tools.configure(None, None)
