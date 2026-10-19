"""Read-only job and assessment listings – used by the web UI to label mappings."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Assessment, Job
from app.schemas import AssessmentOut, JobOut

router = APIRouter(tags=["Catalog"])


@router.get(
    "/jobs",
    response_model=list[JobOut],
    summary="List all jobs",
)
def list_jobs(db: Session = Depends(get_db)) -> list[JobOut]:
    jobs = db.query(Job).order_by(Job.title).all()
    return [JobOut.model_validate(j) for j in jobs]


@router.get(
    "/assessments",
    response_model=list[AssessmentOut],
    summary="List all assessments",
)
def list_assessments(db: Session = Depends(get_db)) -> list[AssessmentOut]:
    assessments = db.query(Assessment).order_by(Assessment.name).all()
    return [AssessmentOut.model_validate(a) for a in assessments]
