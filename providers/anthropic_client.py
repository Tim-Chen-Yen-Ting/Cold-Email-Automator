import os
import anthropic
import instructor
from models import Contact, ContactList, EmailDraft

_client = None


def _get_client():
    global _client
    if not _client:
        _client = instructor.from_anthropic(
            anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        )
    return _client


RESEARCH_SYSTEM = """You are a B2B sales researcher. Find real people matching a target profile,
discover their contact emails, and gather personalization hooks (recent news, product launches,
blog posts) that make cold emails feel relevant.

Search thoroughly. Guess email formats from any public emails found on the domain.
If you cannot find an email with reasonable confidence, omit that contact."""

DRAFT_SYSTEM = """You are an expert cold email copywriter helping a candidate land jobs and internships.
You have access to their full experience inventory. Your job is to pick the 1-2 experiences or
skills that will resonate most with this specific recipient and their company — not everything, just
the most relevant angle. Rules:
- 3-5 sentences max in the body (not counting greeting/sign-off)
- Lead with something specific about the recipient or their company
- Connect ONE relevant part of the candidate's background to something they clearly need
- One clear, low-friction call to action (e.g. a quick call, not "please review my resume")
- No buzzwords, no fake urgency, no ALL CAPS
- Sound like a curious, capable person reaching out — not a cover letter
- Plain text only — this is sent as a plain-text email, not rendered markdown. Never use
  markdown link syntax like [text](url), bold/italic markers, or bullet characters. Write
  URLs and the signature exactly as given, verbatim, with no reformatting."""


def _load_profile() -> str:
    try:
        with open("profile.md", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

_PROFILE = _load_profile()


def research(targeting: dict, count: int) -> list[Contact]:
    search_guidance = targeting.get("_search_guidance", "")
    prompt = f"""
Find {count} real contacts matching this profile:
- Description: {targeting['description']}
- Industries: {', '.join(targeting['industries'])}
- Target roles: {', '.join(targeting['roles'])}
- Keywords: {', '.join(targeting['keywords'])}
- Geography: {targeting['geography']}
- Exclude: {', '.join(targeting.get('exclude_keywords', []))}
{search_guidance}
For each contact: search for the company, find the right person, find their email,
find a recent personalization hook (last 3 months ideally).
"""
    client = _get_client()
    result = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=RESEARCH_SYSTEM,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 30}],
        messages=[{"role": "user", "content": prompt}],
        response_model=ContactList,
    )
    return result.contacts


def draft(contact: Contact, config: dict) -> EmailDraft:
    sender = config["sender"]
    email_cfg = config["email"]
    profile = _PROFILE
    prompt = f"""
Write a cold email from {sender['name']} to {contact.name} at {contact.company}.

CANDIDATE FULL PROFILE (pick the most relevant angle — do not dump everything):
{profile}

SENDER INFO:
- Name: {sender['name']}
- Goal: {email_cfg['goal']}
- Signature: {sender['signature']}

RECIPIENT:
- Name: {contact.name}, {contact.role} at {contact.company}
- Website: {contact.website}
- Personalization hook: {contact.notes}

Return subject, body (greeting through sign-off), and appeal_angle (which part of the profile you led with and why).
"""
    client = _get_client()
    return client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=DRAFT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        response_model=EmailDraft,
    )
