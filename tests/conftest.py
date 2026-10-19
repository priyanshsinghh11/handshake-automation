"""Shared pytest fixtures.

Key design decisions:
  - SQLite :memory: with StaticPool so ALL connections share the same in-memory DB.
    Without StaticPool, each new connection creates a fresh empty DB.
  - We patch `app.database.engine` and `app.main.engine` so the app's lifespan
    and any other engine-using code operate on the test DB.
  - `get_db` is overridden so route handlers also use the test session.
  - Tables are dropped and re-created between tests for full isolation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.database import Base, get_db

# ---------------------------------------------------------------------------
# Shared in-memory SQLite engine using StaticPool
# ---------------------------------------------------------------------------

test_engine = create_engine(
    "sqlite://",  # pure in-memory
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # single shared connection – tables persist across sessions
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """FastAPI dependency override – routes use test DB."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_db():
    """
    Create tables in test_engine before every test; drop after.

    Patches both app.database.engine and app.main.engine so that startup
    (create_tables + seed_demo_data) use the in-memory test DB.
    """
    with patch("app.database.engine", test_engine), \
         patch("app.main.engine", test_engine):
        Base.metadata.create_all(bind=test_engine)
        yield
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Yield a raw test DB session for direct inspection in tests."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(setup_db):
    """TestClient with DB dependency override applied."""
    from app.main import app
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = "change-me"
WEBHOOK_HEADERS = {"X-Webhook-Secret": WEBHOOK_SECRET}

SAMPLE_PAYLOAD = {
    "candidate_id": "hs_candidate_123",
    "candidate_name": "Rahul Sharma",
    "candidate_email": "rahul@example.com",
    "job_id": "hs_job_456",
    "job_title": "AI Engineer Intern",
}
