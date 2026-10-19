"""Tests for the webhook endpoint."""

from unittest.mock import patch

from tests.conftest import SAMPLE_PAYLOAD, WEBHOOK_HEADERS
from app.models import Assessment, AssessmentMapping, Job


def _seed_job_and_mapping():
    """Helper: seed job + assessment + mapping into the test DB."""
    from tests.conftest import TestSessionLocal

    db = TestSessionLocal()
    try:
        job = Job(external_id="hs_job_456", title="AI Engineer Intern")
        db.add(job)
        db.flush()

        assessment = Assessment(
            name="AI Engineer Assessment",
            base_url="http://localhost:8000/assessment",
        )
        db.add(assessment)
        db.flush()

        mapping = AssessmentMapping(
            job_id=job.id,
            assessment_id=assessment.id,
            email_subject="Your AI Engineer Assessment",
            email_body="Hi {{candidate_name}}, complete here: {{assessment_url}}",
        )
        db.add(mapping)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1: Valid webhook creates an application
# ---------------------------------------------------------------------------

def test_valid_webhook_creates_application(client):
    _seed_job_and_mapping()

    response = client.post(
        "/webhooks/handshake",
        json=SAMPLE_PAYLOAD,
        headers=WEBHOOK_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["application_id"] is not None
    assert data["status"] == "EMAIL_SENT"


# ---------------------------------------------------------------------------
# Test 2: Invalid webhook secret returns 401
# ---------------------------------------------------------------------------

def test_invalid_webhook_secret_returns_401(client):
    response = client.post(
        "/webhooks/handshake",
        json=SAMPLE_PAYLOAD,
        headers={"X-Webhook-Secret": "wrong-secret"},
    )
    assert response.status_code == 401


def test_missing_webhook_secret_returns_422(client):
    """No header at all → FastAPI returns 422 (missing required header)."""
    response = client.post("/webhooks/handshake", json=SAMPLE_PAYLOAD)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test 3: Job with assessment mapping creates assessment session
# ---------------------------------------------------------------------------

def test_assessment_session_created(client):
    _seed_job_and_mapping()

    response = client.post(
        "/webhooks/handshake",
        json=SAMPLE_PAYLOAD,
        headers=WEBHOOK_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "EMAIL_SENT"

    # Verify session exists in DB
    from tests.conftest import TestSessionLocal
    from app.models import AssessmentSession

    db = TestSessionLocal()
    try:
        sessions = db.query(AssessmentSession).all()
        assert len(sessions) == 1
        assert sessions[0].assessment_url.startswith("http://localhost:8000/assessment/")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 4: Assessment email is sent (mock provider)
# ---------------------------------------------------------------------------

def test_assessment_email_sent(client):
    _seed_job_and_mapping()

    with patch("app.services.email.send_assessment_email") as mock_send:
        response = client.post(
            "/webhooks/handshake",
            json=SAMPLE_PAYLOAD,
            headers=WEBHOOK_HEADERS,
        )

    assert response.status_code == 200
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_email"] == "rahul@example.com"
    assert call_kwargs["candidate_name"] == "Rahul Sharma"


# ---------------------------------------------------------------------------
# Test 5: Duplicate webhook does NOT send another email
# ---------------------------------------------------------------------------

def test_duplicate_webhook_does_not_resend_email(client):
    _seed_job_and_mapping()

    with patch("app.services.email.send_assessment_email") as mock_send:
        r1 = client.post(
            "/webhooks/handshake",
            json=SAMPLE_PAYLOAD,
            headers=WEBHOOK_HEADERS,
        )
        r2 = client.post(
            "/webhooks/handshake",
            json=SAMPLE_PAYLOAD,
            headers=WEBHOOK_HEADERS,
        )

    assert r1.status_code == 200
    assert r2.status_code == 200
    # Email must only be sent once
    assert mock_send.call_count == 1
    # Both responses point to the same application
    assert r1.json()["application_id"] == r2.json()["application_id"]


# ---------------------------------------------------------------------------
# Test 6: Missing assessment mapping results in FAILED status
# ---------------------------------------------------------------------------

def test_missing_mapping_results_in_failed(client):
    """No mapping seeded → application must end up as FAILED."""
    response = client.post(
        "/webhooks/handshake",
        json=SAMPLE_PAYLOAD,
        headers=WEBHOOK_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["status"] == "FAILED"
