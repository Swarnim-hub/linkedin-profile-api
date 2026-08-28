"""Tests for FastAPI endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.response import ProfileResponse, ExperienceItem
from app.services.cache import clear_cache
from app.services.linkedin_client import LinkedInAPIError

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    clear_cache()
    yield
    clear_cache()


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "docs" in data
    assert "endpoints" in data


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@patch("app.routers.profile.LinkedInClient.get_profile")
def test_post_profile_success(mock_get_profile):
    mock_profile = ProfileResponse(
        public_identifier="williamhgates",
        profile_url="https://www.linkedin.com/in/williamhgates/",
        first_name="Bill",
        last_name="Gates",
        full_name="Bill Gates",
        headline="Co-chair, Bill & Melinda Gates Foundation",
        location="Seattle, WA",
        about="Philanthropist and technologist.",
        experience=[
            ExperienceItem(
                title="Co-chair",
                company_name="Bill & Melinda Gates Foundation",
                is_current=True,
            )
        ],
    )
    mock_get_profile.return_value = mock_profile

    response = client.post(
        "/api/profile",
        json={"linkedin_url": "https://www.linkedin.com/in/williamhgates/"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["public_identifier"] == "williamhgates"
    assert data["full_name"] == "Bill Gates"
    assert len(data["experience"]) == 1
    assert data["is_cached"] is False


@patch("app.routers.profile.LinkedInClient.get_profile")
def test_caching_behavior(mock_get_profile):
    mock_profile = ProfileResponse(
        public_identifier="testuser",
        profile_url="https://www.linkedin.com/in/testuser/",
        first_name="Test",
        last_name="User",
        full_name="Test User",
    )
    mock_get_profile.return_value = mock_profile

    # First call: cache miss
    resp1 = client.post("/api/profile", json={"linkedin_url": "testuser"})
    assert resp1.status_code == 200
    assert resp1.json()["is_cached"] is False
    assert mock_get_profile.call_count == 1

    # Second call: cache hit
    resp2 = client.post("/api/profile", json={"linkedin_url": "https://www.linkedin.com/in/testuser/"})
    assert resp2.status_code == 200
    assert resp2.json()["is_cached"] is True
    # mock_get_profile should still have been called only once
    assert mock_get_profile.call_count == 1


@patch("app.routers.profile.LinkedInClient.get_profile")
def test_get_profile_endpoint(mock_get_profile):
    mock_profile = ProfileResponse(
        public_identifier="satyanadella",
        profile_url="https://www.linkedin.com/in/satyanadella/",
        full_name="Satya Nadella",
    )
    mock_get_profile.return_value = mock_profile

    response = client.get("/api/profile?url=https://www.linkedin.com/in/satyanadella/")
    assert response.status_code == 200
    assert response.json()["full_name"] == "Satya Nadella"


@patch("app.routers.profile.LinkedInClient.get_profile")
def test_profile_not_found(mock_get_profile):
    mock_get_profile.side_effect = LinkedInAPIError(
        message="LinkedIn profile 'nonexistent' not found.",
        status_code=404,
    )

    response = client.post("/api/profile", json={"linkedin_url": "nonexistent"})
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@patch("app.routers.profile.LinkedInClient.get_profile")
def test_rate_limited(mock_get_profile):
    mock_get_profile.side_effect = LinkedInAPIError(
        message="Rate limited by LinkedIn.",
        status_code=429,
    )

    response = client.post("/api/profile", json={"linkedin_url": "someuser"})
    assert response.status_code == 429


def test_empty_url_validation_error():
    response = client.post("/api/profile", json={"linkedin_url": "   "})
    assert response.status_code == 422  # Pydantic validation error
