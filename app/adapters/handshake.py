"""Handshake adapter.

Converts a Handshake-originated payload into our internal normalised format.

Design note:
  Handshake does not currently offer a verified outbound webhook. This adapter
  is a conversion layer only. For MVP, we receive a normalised payload on our
  own endpoint and this adapter validates + converts it. When Handshake provides
  a real webhook, update this file to handle their specific payload shape and
  signature verification – nothing else in the application needs to change.

All Handshake-specific logic lives here. The rest of the application only sees
the normalised InternalApplicationInput dataclass.
"""

from dataclasses import dataclass

from app.schemas import HandshakeApplicationPayload


@dataclass
class InternalApplicationInput:
    """Normalised representation of an incoming job application."""

    candidate_external_id: str
    candidate_name: str
    candidate_email: str
    job_external_id: str
    job_title: str
    source: str


def parse_handshake_payload(
    payload: HandshakeApplicationPayload,
) -> InternalApplicationInput:
    """
    Convert a Handshake application payload into our internal format.

    When Handshake adds real webhook support, update this function to map their
    actual field names. Everything downstream stays unchanged.
    """
    return InternalApplicationInput(
        candidate_external_id=payload.candidate_id,
        candidate_name=payload.candidate_name,
        candidate_email=str(payload.candidate_email),
        job_external_id=payload.job_id,
        job_title=payload.job_title,
        source="handshake",
    )
