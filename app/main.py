"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.routes import applications, catalog, mappings, webhook

STATIC_DIR = Path(__file__).parent / "static"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

def create_tables() -> None:
    """Create all tables. No-op if they already exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready")


# ---------------------------------------------------------------------------
# Demo seed data
# ---------------------------------------------------------------------------

def seed_demo_data() -> None:
    """
    Insert seed data for local testing:
      - AI Engineer Intern  → AI Engineer Assessment
      - Full Stack Engineer → Full Stack Assessment

    Safe to run multiple times (idempotent get-or-create).
    """
    from sqlalchemy.orm import Session
    from app.models import Assessment, AssessmentMapping, Job

    with Session(engine) as db:
        jobs_data = [
            ("seed_job_ai", "AI Engineer Intern"),
            ("seed_job_fs", "Full Stack Engineer"),
        ]
        jobs: dict[str, Job] = {}
        for ext_id, title in jobs_data:
            job = db.query(Job).filter(Job.external_id == ext_id).first()
            if not job:
                job = Job(external_id=ext_id, title=title)
                db.add(job)
                db.flush()
                logger.info("Seeded job: %s", title)
            jobs[ext_id] = job

        assessments_data = [
            ("AI Engineer Assessment", settings.assessment_base_url),
            ("Full Stack Assessment", settings.assessment_base_url),
        ]
        seeded_assessments: list[Assessment] = []
        for name, base_url in assessments_data:
            assessment = db.query(Assessment).filter(Assessment.name == name).first()
            if not assessment:
                assessment = Assessment(name=name, base_url=base_url)
                db.add(assessment)
                db.flush()
                logger.info("Seeded assessment: %s", name)
            seeded_assessments.append(assessment)

        db.commit()

        mapping_pairs = [
            (jobs["seed_job_ai"], seeded_assessments[0]),
            (jobs["seed_job_fs"], seeded_assessments[1]),
        ]
        for job, assessment in mapping_pairs:
            exists = (
                db.query(AssessmentMapping)
                .filter(
                    AssessmentMapping.job_id == job.id,
                    AssessmentMapping.assessment_id == assessment.id,
                )
                .first()
            )
            if not exists:
                m = AssessmentMapping(
                    job_id=job.id,
                    assessment_id=assessment.id,
                    email_subject=f"{assessment.name} – Next Step",
                    email_body=(
                        "Hi {{candidate_name}},\n\n"
                        "Thank you for applying for the {{job_title}} role.\n\n"
                        "Please complete your assessment here:\n{{assessment_url}}\n\n"
                        "Good luck!\nThe Recruitment Team"
                    ),
                )
                db.add(m)
                logger.info("Seeded mapping: %s → %s", job.title, assessment.name)
        db.commit()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    create_tables()
    seed_demo_data()
    logger.info("Application started | UI at / | docs at /docs")
    yield
    # Shutdown logic goes here if needed


app = FastAPI(
    title="Recruitment Assessment Automation",
    description=(
        "Automatically sends assessment links to candidates when they apply via Handshake. "
        "POST to /webhooks/handshake with X-Webhook-Secret header."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(webhook.router)
app.include_router(applications.router)
app.include_router(mappings.router)
app.include_router(catalog.router)

# Web UI (plain HTML/CSS/JS, served from app/static)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["Health"])
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
