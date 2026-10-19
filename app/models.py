"""SQLAlchemy ORM models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="candidate"
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="job"
    )
    assessment_mappings: Mapped[list["AssessmentMapping"]] = relationship(
        "AssessmentMapping", back_populates="job"
    )


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    base_url: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    assessment_mappings: Mapped[list["AssessmentMapping"]] = relationship(
        "AssessmentMapping", back_populates="assessment"
    )
    sessions: Mapped[list["AssessmentSession"]] = relationship(
        "AssessmentSession", back_populates="assessment"
    )


class AssessmentMapping(Base):
    __tablename__ = "assessment_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"))
    assessment_id: Mapped[int] = mapped_column(Integer, ForeignKey("assessments.id"))
    email_subject: Mapped[str] = mapped_column(String(500))
    email_body: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    job: Mapped["Job"] = relationship("Job", back_populates="assessment_mappings")
    assessment: Mapped["Assessment"] = relationship(
        "Assessment", back_populates="assessment_mappings"
    )


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_candidate_job"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidates.id"))
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"))
    source: Mapped[str] = mapped_column(String(100), default="handshake")
    status: Mapped[str] = mapped_column(String(50), default="RECEIVED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    candidate: Mapped["Candidate"] = relationship(
        "Candidate", back_populates="applications"
    )
    job: Mapped["Job"] = relationship("Job", back_populates="applications")
    assessment_sessions: Mapped[list["AssessmentSession"]] = relationship(
        "AssessmentSession", back_populates="application"
    )


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("applications.id"), index=True
    )
    assessment_id: Mapped[int] = mapped_column(Integer, ForeignKey("assessments.id"))
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="ASSESSMENT_CREATED")
    assessment_url: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    application: Mapped["Application"] = relationship(
        "Application", back_populates="assessment_sessions"
    )
    assessment: Mapped["Assessment"] = relationship(
        "Assessment", back_populates="sessions"
    )
