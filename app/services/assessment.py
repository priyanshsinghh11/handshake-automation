"""Assessment service – generates secure sessions and assessment URLs."""

import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Assessment, AssessmentSession, Application

logger = logging.getLogger(__name__)


def generate_token() -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(32)


def build_assessment_url(base_url: str, token: str) -> str:
    """Combine configurable base URL with the token."""
    base = base_url.rstrip("/")
    return f"{base}/{token}"


def create_assessment_session(
    db: Session,
    application: Application,
    assessment: Assessment,
    expires_hours: int = 72,
) -> AssessmentSession:
    """
    Create and persist a new AssessmentSession for the given application.
    Caller is responsible for ensuring no duplicate session is created.
    """
    token = generate_token()
    url = build_assessment_url(assessment.base_url, token)
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)

    session = AssessmentSession(
        application_id=application.id,
        assessment_id=assessment.id,
        token=token,
        status="ASSESSMENT_CREATED",
        assessment_url=url,
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()  # get id without committing

    # Log only first 8 chars of token – never the full token
    logger.info(
        "Assessment session created | application_id=%s token_prefix=%s",
        application.id,
        token[:8],
    )
    return session


def get_existing_session(
    db: Session, application_id: int
) -> AssessmentSession | None:
    """Return the most recent assessment session for an application, if any."""
    return (
        db.query(AssessmentSession)
        .filter(AssessmentSession.application_id == application_id)
        .order_by(AssessmentSession.created_at.desc())
        .first()
    )
