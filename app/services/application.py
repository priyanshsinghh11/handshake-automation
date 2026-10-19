"""Core application processing service.

Architecture:
  Normalised payload
      → find_or_create_candidate
      → find_or_create_job
      → create_application (idempotent)
      → find_assessment_mapping
      → create_assessment_session (or reuse existing)
      → send email
      → update status

This service knows nothing about Handshake. It works with any normalised input.
"""

import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Application, AssessmentMapping, Candidate, Job
from app.services import assessment as assessment_svc
from app.services.email import send_assessment_email

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_or_create_candidate(
    db: Session, external_id: str, name: str, email: str
) -> Candidate:
    candidate = (
        db.query(Candidate).filter(Candidate.external_id == external_id).first()
    )
    if candidate:
        return candidate

    candidate = Candidate(external_id=external_id, name=name, email=email)
    db.add(candidate)
    db.flush()
    logger.info("Candidate created | external_id=%s", external_id)
    return candidate


def _find_or_create_job(
    db: Session, external_id: str, title: str
) -> Job:
    job = db.query(Job).filter(Job.external_id == external_id).first()
    if job:
        return job

    job = Job(external_id=external_id, title=title)
    db.add(job)
    db.flush()
    logger.info("Job created | external_id=%s title=%s", external_id, title)
    return job


def _get_or_create_application(
    db: Session, candidate: Candidate, job: Job, source: str
) -> tuple["Application", bool]:
    """
    Returns (application, created).
    created=False means the application already existed (duplicate).
    """
    existing = (
        db.query(Application)
        .filter(
            Application.candidate_id == candidate.id,
            Application.job_id == job.id,
        )
        .first()
    )
    if existing:
        return existing, False

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        source=source,
        status="RECEIVED",
    )
    db.add(application)
    db.flush()
    logger.info("Application created | application_id=%s", application.id)
    return application, True


def _find_active_mapping(
    db: Session, job_id: int
) -> AssessmentMapping | None:
    return (
        db.query(AssessmentMapping)
        .filter(
            AssessmentMapping.job_id == job_id,
            AssessmentMapping.active.is_(True),
        )
        .first()
    )


def _mark_failed(db: Session, application: Application, message: str) -> None:
    application.status = "FAILED"
    application.error_message = message
    application.processed_at = datetime.utcnow()
    db.commit()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def process_application(
    db: Session,
    *,
    candidate_external_id: str,
    candidate_name: str,
    candidate_email: str,
    job_external_id: str,
    job_title: str,
    source: str = "handshake",
) -> Application:
    """
    Idempotent end-to-end application processing.

    If the same candidate+job is submitted twice:
      - The existing application is returned.
      - No second email is sent.
      - No second assessment session is created.
    """
    logger.info("Application received | source=%s job=%s", source, job_external_id)

    # 1. Find or create candidate
    candidate = _find_or_create_candidate(
        db, candidate_external_id, candidate_name, candidate_email
    )

    # 2. Find or create job
    job = _find_or_create_job(db, job_external_id, job_title)

    # 3. Get or create application (idempotency gate)
    application, created = _get_or_create_application(db, candidate, job, source)

    if not created:
        # Already processed or in progress – return without re-processing
        logger.info(
            "Duplicate application ignored | application_id=%s status=%s",
            application.id,
            application.status,
        )
        return application

    # 4. Update status to PROCESSING
    application.status = "PROCESSING"
    db.flush()

    # 5. Find assessment mapping for this job
    mapping = _find_active_mapping(db, job.id)
    if not mapping:
        _mark_failed(
            db,
            application,
            f"No active assessment mapping found for job_id={job.id}",
        )
        logger.error(
            "No assessment mapping | job_id=%s application_id=%s",
            job.id,
            application.id,
        )
        return application

    logger.info(
        "Assessment mapped | assessment_id=%s application_id=%s",
        mapping.assessment_id,
        application.id,
    )

    # 6. Check for an existing session (retry path)
    existing_session = assessment_svc.get_existing_session(db, application.id)

    if existing_session:
        session = existing_session
        logger.info(
            "Reusing existing assessment session | session_id=%s", session.id
        )
    else:
        # 7. Create new assessment session
        session = assessment_svc.create_assessment_session(
            db, application, mapping.assessment
        )
        application.status = "ASSESSMENT_CREATED"
        db.flush()

    # 8. Send the assessment email
    try:
        send_assessment_email(
            to_email=candidate.email,
            candidate_name=candidate.name,
            job_title=job.title,
            assessment_url=session.assessment_url,
            subject=mapping.email_subject,
            body=mapping.email_body,
        )
    except Exception as exc:
        _mark_failed(db, application, f"Email failed: {exc}")
        logger.error(
            "Assessment email failed | application_id=%s error=%s",
            application.id,
            exc,
        )
        return application

    # 9. Mark complete
    application.status = "EMAIL_SENT"
    application.processed_at = datetime.utcnow()
    db.commit()

    logger.info(
        "Application processed successfully | application_id=%s status=EMAIL_SENT",
        application.id,
    )
    return application
