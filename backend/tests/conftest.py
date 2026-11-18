import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.accounting  # noqa: F401 - registers every model on Base.metadata
from app.auth.security import ADMIN_EMAIL, ADMIN_PASSWORD
from app.main import app
from app.db.session import Base, get_db

DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample_invoices")
)


@pytest.fixture
def anonymous_client():
    """Isolated in-memory database, no credentials attached."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client(anonymous_client):
    """Signed-in client. Existing API tests use this, so auth stays transparent."""
    response = anonymous_client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    anonymous_client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return anonymous_client
