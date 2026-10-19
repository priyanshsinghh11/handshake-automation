"""Pydantic v2 schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


# ---------------------------------------------------------------------------
# Incoming webhook payload (normalised – Handshake adapter converts to this)
# ---------------------------------------------------------------------------

class HandshakeApplicationPayload(BaseModel):
    candidate_id: str
    candidate_name: str
    candidate_email: EmailStr
    job_id: str
    job_title: str

    @field_validator("candidate_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("candidate_name must not be blank")
        return v.strip()

    @field_validator("job_title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("job_title must not be blank")
        return v.strip()


# ---------------------------------------------------------------------------
# Webhook response
# ---------------------------------------------------------------------------

class WebhookResponse(BaseModel):
    success: bool
    application_id: int
    status: str


# ---------------------------------------------------------------------------
# Mapping schemas
# ---------------------------------------------------------------------------

class MappingCreate(BaseModel):
    job_id: int
    assessment_id: int
    email_subject: str
    email_body: str


class MappingOut(BaseModel):
    id: int
    job_id: int
    assessment_id: int
    email_subject: str
    email_body: str
    active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Application schemas
# ---------------------------------------------------------------------------

class ApplicationOut(BaseModel):
    id: int
    candidate: str
    email: str
    job: str
    status: str
    created_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Job + Assessment read schemas (used by the web UI)
# ---------------------------------------------------------------------------

class JobOut(BaseModel):
    id: int
    external_id: str
    title: str
    active: bool

    model_config = {"from_attributes": True}


class AssessmentOut(BaseModel):
    id: int
    name: str
    base_url: str
    active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Assessment + Job seed schemas (internal use)
# ---------------------------------------------------------------------------

class AssessmentCreate(BaseModel):
    name: str
    base_url: str


class JobCreate(BaseModel):
    external_id: str
    title: str
