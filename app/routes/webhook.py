"""Webhook routes – entry point for incoming application events."""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.handshake import parse_handshake_payload
from app.config import settings
from app.database import get_db
from app.schemas import HandshakeApplicationPayload, WebhookResponse
from app.services.application import process_application

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def _verify_secret(x_webhook_secret: str = Header(...)) -> None:
    """Dependency: reject requests with wrong webhook secret."""
    if x_webhook_secret != settings.webhook_secret:
        logger.warning("Invalid webhook secret received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )


@router.post(
    "/handshake",
    response_model=WebhookResponse,
    summary="Receive Handshake application event",
    description=(
        "Accepts a normalised application payload. "
        "Requires the X-Webhook-Secret header."
    ),
)
def handshake_webhook(
    payload: HandshakeApplicationPayload,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_secret),
) -> WebhookResponse:
    parsed = parse_handshake_payload(payload)

    application = process_application(
        db,
        candidate_external_id=parsed.candidate_external_id,
        candidate_name=parsed.candidate_name,
        candidate_email=parsed.candidate_email,
        job_external_id=parsed.job_external_id,
        job_title=parsed.job_title,
        source=parsed.source,
    )

    success = application.status not in ("FAILED",)
    return WebhookResponse(
        success=success,
        application_id=application.id,
        status=application.status,
    )
