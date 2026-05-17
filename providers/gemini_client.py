import os
import google.generativeai as genai
import instructor
from models import Contact, ContactList, EmailDraft

_client = None


def _get_client():
    global _client
    if not _client:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            tools="google_search_retrieval",  # built-in grounded search
        )
        _client = instructor.from_gemini(model, mode=instructor.Mode.GEMINI_JSON)
    return _client


def _get_draft_client():
    # Draft doesn't need search grounding
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(model_name="gemini-2.0-flash")
    return instructor.from_gemini(model, mode=instructor.Mode.GEMINI_JSON)


RESEARCH_SYSTEM = """You are a B2B sales researcher. Find real people matching a target profile,
discover their contact emails, and gather personalization hooks (recent news, product launches,
blog posts) that make cold emails feel relevant.

Search thoroughly. Guess email formats from any public emails found on the domain.
If you cannot find an email with reasonable confidence, omit that contact."""

DRAFT_SYSTEM = """You are an expert cold email copywriter. Write concise, human, personalized
cold emails that do NOT sound like marketing spam.
- 3-5 sentences max in the body (not counting greeting/sign-off)
- Lead with a specific observation about the recipient, not about the sender
- One clear, low-friction call to action
- No buzzwords, no fake urgency, no ALL CAPS"""


def research(targeting: dict, count: int) -> list[Contact]:
    prompt = f"""
{RESEARCH_SYSTEM}

Find {count} real contacts matching this profile:
- Description: {targeting['description']}
- Industries: {', '.join(targeting['industries'])}
- Target roles: {', '.join(targeting['roles'])}
- Keywords: {', '.join(targeting['keywords'])}
- Geography: {targeting['geography']}
- Exclude: {', '.join(targeting.get('exclude_keywords', []))}

For each contact: search for the company, find the right person, find their email,
find a recent personalization hook (last 3 months ideally).
"""
    client = _get_client()
    result = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        response_model=ContactList,
    )
    return result.contacts


def draft(contact: Contact, config: dict) -> EmailDraft:
    sender = config["sender"]
    email_cfg = config["email"]
    prompt = f"""
{DRAFT_SYSTEM}

Write a cold email from {sender['name']} to {contact.name} at {contact.company}.

SENDER: {sender['name']}, {sender['role']} at {sender['company']}
Value prop: {sender['pitch']}
Goal: {email_cfg['goal']}
Signature: {sender['signature']}

RECIPIENT: {contact.name}, {contact.role} at {contact.company}
Website: {contact.website}
Hook: {contact.notes}

Return subject, body (greeting through sign-off), and appeal_angle.
"""
    client = _get_draft_client()
    return client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        response_model=EmailDraft,
    )
