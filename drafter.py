from providers import get_provider
from models import Contact, EmailDraft


def draft_email(contact: Contact, config: dict) -> tuple[str, str, str]:
    """Returns (subject, body, appeal_angle)."""
    provider = get_provider(config, role="draft")

    subject_template = config["email"]["subject_template"]
    subject = subject_template.format(
        company=contact.company,
        name=contact.name.split()[0] if contact.name else "there"
    )

    draft: EmailDraft = provider.draft(contact, config)
    return subject, draft.body, draft.appeal_angle
