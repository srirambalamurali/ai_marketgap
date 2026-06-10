from types import SimpleNamespace
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.database.postgres import get_db
from app.api import auth as auth_api
from app.services.auth import get_current_user as get_current_user_dep


class DummyDB:
    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def flush(self):
        return None


@pytest.fixture(autouse=True)
def override_db():
    async def _override():
        yield DummyDB()

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def fake_user():
    return SimpleNamespace(
        id=uuid4(),
        name="Sriram",
        email="test@example.com",
        hashed_password="$2b$12$fakehash",
    )


def test_register_user(client, fake_user, monkeypatch):
    monkeypatch.setattr(auth_api, "get_user_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(auth_api, "create_user", AsyncMock(return_value=fake_user))

    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "Sriram", "email": "test@example.com", "password": "password123"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test@example.com"
    assert data["access_token"]


def test_duplicate_email_fails(client, fake_user, monkeypatch):
    monkeypatch.setattr(auth_api, "get_user_by_email", AsyncMock(return_value=fake_user))

    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "Sriram", "email": "test@example.com", "password": "password123"},
    )

    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"].lower()


def test_login_user(client, fake_user, monkeypatch):
    monkeypatch.setattr(auth_api, "authenticate_user", AsyncMock(return_value=fake_user))

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["user"]["id"]
    assert data["access_token"]


def test_wrong_password_fails(client, monkeypatch):
    monkeypatch.setattr(auth_api, "authenticate_user", AsyncMock(return_value=None))

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrong-password"},
    )

    assert resp.status_code == 401
    assert "invalid email or password" in resp.json()["detail"].lower()


def test_me_returns_user(client, fake_user, monkeypatch):
    async def _override_current_user():
        return fake_user

    app.dependency_overrides[get_current_user_dep] = _override_current_user

    try:
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
    finally:
        app.dependency_overrides.pop(get_current_user_dep, None)
