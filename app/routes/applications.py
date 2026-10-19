"""Application query routes and retry endpoint."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Application, AssessmentSession
from app.schemas import ApplicationOut
from app.services.application import process_application
from app.services import assessment as assessment_svc
from app.services.email import send_assessment_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["Applications"])


def _to_application_out(app: Application) -> ApplicationOut:
    return ApplicationOut(
        id=app.id,
        candidate=app.candidate.name,
        email=app.candidate.email,
        job=app.job.title,
        status=app.status,
        created_at=app.created_at,
        processed_at=app.processed_at,
        error_message=app.error_message,
    )


@router.get(
    "",
    response_model=list[ApplicationOut],
    summary="List all applications",
)
def list_applications(db: Session = Depends(get_db)) -> list[ApplicationOut]:
    apps = db.query(Application).order_by(Application.created_at.desc()).all()
    return [_to_application_out(a) for a in apps]


@router.get(
    "/{application_id}",
    response_model=ApplicationOut,
    summary="Get a single application",
)
def get_application(
    application_id: int, db: Session = Depends(get_db)
) -> ApplicationOut:
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found",
        )
    return _to_application_out(app)


@router.post(
    "/{application_id}/retry",
    response_model=ApplicationOut,
    summary="Retry a failed application",
    description="Only FAILED applications can be retried. Reuses existing assessment session if available.",
)
def retry_application(
    application_id: int, db: Session = Depends(get_db)
) -> ApplicationOut:
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found",
        )

    if app.status != "FAILED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry application with status={app.status!r}. Only FAILED applications can be retried.",
        )

    # Find mapping
    from app.models import AssessmentMapping
    mapping = (
        db.query(AssessmentMapping)
        .filter(
            AssessmentMapping.job_id == app.job_id,
            AssessmentMapping.active.is_(True),
        )
        .first()
    )
    if not mapping:
        app.error_message = f"Retry failed: no active mapping for job_id={app.job_id}"
        app.processed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No active assessment mapping found for this job",
        )

    # Reuse existing session or create a new one
    session = assessment_svc.get_existing_session(db, app.id)
    if not session:
        session = assessment_svc.create_assessment_session(
            db, app, mapping.assessment
        )
        app.status = "ASSESSMENT_CREATED"
        db.flush()

    try:
        send_assessment_email(
            to_email=app.candidate.email,
            candidate_name=app.candidate.name,
            job_title=app.job.title,
            assessment_url=session.assessment_url,
            subject=mapping.email_subject,
            body=mapping.email_body,
        )
    except Exception as exc:
        app.status = "FAILED"
        app.error_message = f"Retry email failed: {exc}"
        app.processed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Email send failed during retry",
        ) from exc

    app.status = "EMAIL_SENT"
    app.error_message = None
    app.processed_at = datetime.utcnow()
    db.commit()

    logger.info("Application retried successfully | application_id=%s", app.id)
    return _to_application_out(app)
