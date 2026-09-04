import database as db
from providers import get_provider
from models import Contact


def _build_search_guidance(config: dict, exclude_companies: list[str]) -> str:
    ops = config.get("search_operators", {})
    lines = []

    prefer = ops.get("prefer_sites", [])
    if prefer:
        lines.append(f"Prefer results from: {', '.join(prefer)}")

    exclude_sites = ops.get("exclude_sites", [])
    if exclude_sites:
        lines.append(f"Exclude these sites from searches: {', '.join(exclude_sites)}")

    exclude_terms = ops.get("exclude_terms", [])
    if exclude_terms:
        lines.append(f"Exclude results containing these terms: {', '.join(exclude_terms)}")

    if exclude_companies:
        lines.append(
            "Do NOT return contacts from these companies — already researched: "
            + ", ".join(exclude_companies)
        )

    if not lines:
        return ""
    return "Search guidance:\n" + "\n".join(f"- {l}" for l in lines)


def research_contacts(config: dict, count: int = 10) -> list[Contact]:
    provider = get_provider(config, role="research")
    print(f"[research] Using provider: {config.get('research_provider') or config.get('provider', 'anthropic')}")

    # Steer the LLM away from re-searching companies already in the DB
    campaign = config.get("campaign_label")
    exclude_companies = db.get_researched_companies(campaign)

    # Inject search operator guidance into targeting for the provider
    targeting = dict(config["targeting"])
    search_guidance = _build_search_guidance(config, exclude_companies)
    if search_guidance:
        targeting["_search_guidance"] = search_guidance

    config_with_guidance = dict(config)
    config_with_guidance["targeting"] = targeting

    contacts = provider.research(config_with_guidance["targeting"], count)

    # Hard filter: drop any contact whose company matches the exclusion list,
    # regardless of whether the LLM honored the search guidance.
    if exclude_companies:
        excluded_lower = {c.lower() for c in exclude_companies}
        before = len(contacts)
        contacts = [c for c in contacts if c.company.lower() not in excluded_lower]
        dropped = before - len(contacts)
        if dropped:
            print(f"[research] Filtered out {dropped} contact(s) from already-researched companies")

    print(f"[research] Found {len(contacts)} contacts")
    return contacts
