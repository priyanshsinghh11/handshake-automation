"""Mapping management routes – link jobs to assessments."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Assessment, AssessmentMapping, Job
from app.schemas import MappingCreate, MappingOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mappings", tags=["Mappings"])


@router.post(
    "",
    response_model=MappingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job → assessment mapping",
    description=(
        "Maps a job to an assessment with custom email subject and body. "
        "Template variables: {{candidate_name}}, {{job_title}}, {{assessment_url}}"
    ),
)
def create_mapping(
    payload: MappingCreate, db: Session = Depends(get_db)
) -> MappingOut:
    # Validate that job and assessment exist
    job = db.query(Job).filter(Job.id == payload.job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {payload.job_id} not found",
        )

    assessment = (
        db.query(Assessment).filter(Assessment.id == payload.assessment_id).first()
    )
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {payload.assessment_id} not found",
        )

    mapping = AssessmentMapping(
        job_id=payload.job_id,
        assessment_id=payload.assessment_id,
        email_subject=payload.email_subject,
        email_body=payload.email_body,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    logger.info(
        "Mapping created | job_id=%s assessment_id=%s mapping_id=%s",
        mapping.job_id,
        mapping.assessment_id,
        mapping.id,
    )
    return MappingOut.model_validate(mapping)


@router.get(
    "",
    response_model=list[MappingOut],
    summary="List all active mappings",
)
def list_mappings(db: Session = Depends(get_db)) -> list[MappingOut]:
    mappings = (
        db.query(AssessmentMapping)
        .filter(AssessmentMapping.active.is_(True))
        .all()
    )
    return [MappingOut.model_validate(m) for m in mappings]


@router.delete(
    "/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a mapping",
)
def delete_mapping(mapping_id: int, db: Session = Depends(get_db)) -> None:
    mapping = (
        db.query(AssessmentMapping)
        .filter(AssessmentMapping.id == mapping_id)
        .first()
    )
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found",
        )

    mapping.active = False
    db.commit()
    logger.info("Mapping deactivated | mapping_id=%s", mapping_id)
