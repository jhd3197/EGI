# Shared pytest fixtures for the EGI server suite.
#
# Each test gets a fresh, isolated SQLite database in a tmp dir. We point
# db.DB_PATH at a temp file (not ":memory:") because db.get_db() opens a NEW
# connection per call, so an in-memory DB would not persist across calls.
# All test data here is fake — see docs/TESTING.md test-data policy.
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make the server package importable when pytest is run from anywhere.
SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

import db  # noqa: E402
import main  # noqa: E402
from metrics import metrics  # noqa: E402
from ratelimit import limiter  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Clear the process-global metrics registry between tests."""
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Keep the in-memory rate limiter out of the way of normal tests.

    Counters are process-global, so without this a suite that POSTs more than
    the default limit would start getting 429s. We set a high ceiling and clear
    counters before each test; the dedicated rate-limit test reconfigures the
    limiter itself to a low value.
    """
    limiter.configure(max_requests=100000, window_seconds=300)
    yield
    limiter.configure(max_requests=100000, window_seconds=300)


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point db.DB_PATH at a fresh temp file and initialize the schema."""
    db_file = tmp_path / "test_egi.db"
    monkeypatch.setattr(db, "DB_PATH", db_file)
    db.init_db()
    return db_file


@pytest.fixture()
def client(temp_db, tmp_path, monkeypatch):
    """A TestClient bound to the isolated DB with a throwaway upload dir."""
    upload = tmp_path / "uploads"
    upload.mkdir(exist_ok=True)
    monkeypatch.setattr(main, "UPLOAD_DIR", upload)
    # The TestClient context manager fires startup (db.init_db, idempotent).
    with TestClient(main.app) as test_client:
        yield test_client
