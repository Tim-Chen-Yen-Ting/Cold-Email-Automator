import os
from google import genai
from google.genai import types
import instructor
from models import Contact, ContactList, EmailDraft

_raw_client = None    # billed key — only the grounded search call needs this
_light_client = None  # free-tier key — structured extraction + drafting, no grounding involved
_light_instructor_client = None

RESEARCH_MODEL = "gemini-3.6-flash"
DRAFT_MODEL = "gemini-3.6-flash"


def _search_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]


def _light_api_key() -> str:
    # Falls back to the search key if no separate free-tier key is configured.
    return os.environ.get("GEMINI_DRAFT_API_KEY") or _search_api_key()


def _get_raw_client():
    global _raw_client
    if not _raw_client:
        _raw_client = genai.Client(api_key=_search_api_key())
    return _raw_client


def _get_light_client():
    global _light_client
    if not _light_client:
        _light_client = genai.Client(api_key=_light_api_key())
    return _light_client


def _get_instructor_client():
    global _light_instructor_client
    if not _light_instructor_client:
        _light_instructor_client = instructor.from_genai(_get_light_client(), mode=instructor.Mode.GENAI_TOOLS)
    return _light_instructor_client


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
    # Grounded search doesn't reliably combine with forced structured output —
    # do the web search in plain text first, then extract structured contacts below.
    raw_client = _get_raw_client()
    search_result = raw_client.models.generate_content(
        model=RESEARCH_MODEL,
        contents=f"{RESEARCH_SYSTEM}\n\n{prompt}",
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    findings = search_result.text

    client = _get_instructor_client()
    return client.chat.completions.create(
        model=RESEARCH_MODEL,
        messages=[
            {"role": "user", "content": f"Extract structured contact records from the research findings below.\n\n{findings}"},
        ],
        response_model=ContactList,
    ).contacts


def draft(contact: Contact, config: dict) -> EmailDraft:
    sender = config["sender"]
    email_cfg = config["email"]
    profile = _PROFILE
    prompt = f"""
{DRAFT_SYSTEM}

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
    client = _get_instructor_client()
    return client.chat.completions.create(
        model=DRAFT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_model=EmailDraft,
    )
