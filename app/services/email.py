"""Email service with provider abstraction.

Supports:
  - mock  (default, logs to console – no external dependency)
  - brevo (stub, add real implementation when BREVO_API_KEY is set)

Design decision: Keep this dead-simple for MVP. Adding a new provider means
implementing the _send_via_<provider> helper and wiring it in send_assessment_email.
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def _render_template(template: str, variables: dict[str, str]) -> str:
    """Replace {{key}} placeholders with values."""
    for key, value in variables.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def _send_via_mock(
    to_email: str,
    candidate_name: str,
    subject: str,
    body: str,
) -> None:
    """Mock provider – logs to stdout, no external calls needed."""
    logger.info("=" * 60)
    logger.info("MOCK EMAIL SENT")
    logger.info("To      : %s <%s>", candidate_name, to_email)
    logger.info("Subject : %s", subject)
    logger.info("Body    :\n%s", body)
    logger.info("=" * 60)


def _send_via_brevo(
    to_email: str,
    candidate_name: str,
    subject: str,
    body: str,
) -> None:
    """Brevo (Sendinblue) provider – stub, implement when API key is available."""
    if not settings.brevo_api_key:
        raise RuntimeError("BREVO_API_KEY is not configured")

    # TODO: Implement Brevo API call using httpx
    # import httpx
    # response = httpx.post(
    #     "https://api.brevo.com/v3/smtp/email",
    #     headers={"api-key": settings.brevo_api_key},
    #     json={...},
    # )
    # response.raise_for_status()
    raise NotImplementedError("Brevo provider is not yet implemented")


_PROVIDERS = {
    "mock": _send_via_mock,
    "brevo": _send_via_brevo,
}


def send_assessment_email(
    to_email: str,
    candidate_name: str,
    job_title: str,
    assessment_url: str,
    subject: str,
    body: str,
) -> None:
    """
    Send the assessment email using the configured provider.

    Template variables supported in subject/body:
      {{candidate_name}}, {{job_title}}, {{assessment_url}}
    """
    variables = {
        "candidate_name": candidate_name,
        "job_title": job_title,
        "assessment_url": assessment_url,
    }
    rendered_subject = _render_template(subject, variables)
    rendered_body = _render_template(body, variables)

    provider_name = settings.email_provider.lower()
    provider_fn = _PROVIDERS.get(provider_name)

    if provider_fn is None:
        raise ValueError(f"Unknown email provider: {provider_name!r}")

    provider_fn(to_email, candidate_name, rendered_subject, rendered_body)
    logger.info(
        "Assessment email sent | provider=%s candidate_email=%s",
        provider_name,
        to_email,
    )
