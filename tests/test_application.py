"""Tests for application service and retry flow."""

from unittest.mock import patch

from tests.conftest import SAMPLE_PAYLOAD, WEBHOOK_HEADERS


def _seed_job_and_mapping(db_session=None):
    """Seed job + assessment + mapping. Uses a fresh session if none provided."""
    from tests.conftest import TestSessionLocal
    from app.models import Assessment, AssessmentMapping, Job

    db = db_session or TestSessionLocal()
    close_after = db_session is None
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
            email_subject="Your Assessment",
            email_body="Hi {{candidate_name}}, link: {{assessment_url}}",
        )
        db.add(mapping)
        db.commit()
    finally:
        if close_after:
            db.close()


# ---------------------------------------------------------------------------
# Test 7: Retrying a failed application reuses the existing assessment session
# ---------------------------------------------------------------------------

def test_retry_reuses_existing_assessment_session(client):
    """
    Simulate an email failure, then retry.
    The retry must reuse the same assessment session (same URL/token).
    """
    _seed_job_and_mapping()

    # First webhook call – make email fail
    with patch(
        "app.services.email.send_assessment_email",
        side_effect=RuntimeError("SMTP unavailable"),
    ):
        r1 = client.post(
            "/webhooks/handshake",
            json=SAMPLE_PAYLOAD,
            headers=WEBHOOK_HEADERS,
        )

    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["status"] == "FAILED"
    application_id = data1["application_id"]

    # Capture the assessment session URL created before the email failed
    from tests.conftest import TestSessionLocal
    from app.models import AssessmentSession

    db = TestSessionLocal()
    try:
        sessions_before = db.query(AssessmentSession).all()
        assert len(sessions_before) == 1, "Session should exist even after email failure"
        original_url = sessions_before[0].assessment_url
    finally:
        db.close()

    # Retry – email succeeds this time
    with patch("app.services.email.send_assessment_email") as mock_send:
        r2 = client.post(f"/applications/{application_id}/retry")

    assert r2.status_code == 200
    assert r2.json()["status"] == "EMAIL_SENT"
    mock_send.assert_called_once()

    # Verify no new session was created
    db2 = TestSessionLocal()
    try:
        sessions_after = db2.query(AssessmentSession).all()
        assert len(sessions_after) == 1, "Should still be exactly one session"
        assert sessions_after[0].assessment_url == original_url, "URL must not change on retry"
    finally:
        db2.close()


# ---------------------------------------------------------------------------
# Additional: retry of non-FAILED application is rejected with 400
# ---------------------------------------------------------------------------

def test_retry_non_failed_application_returns_400(client):
    _seed_job_and_mapping()

    r1 = client.post(
        "/webhooks/handshake",
        json=SAMPLE_PAYLOAD,
        headers=WEBHOOK_HEADERS,
    )
    assert r1.json()["status"] == "EMAIL_SENT"
    app_id = r1.json()["application_id"]

    r2 = client.post(f"/applications/{app_id}/retry")
    assert r2.status_code == 400
