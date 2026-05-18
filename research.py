from providers import get_provider
from models import Contact


def _build_search_guidance(config: dict) -> str:
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

    if not lines:
        return ""
    return "Search guidance:\n" + "\n".join(f"- {l}" for l in lines)


def research_contacts(config: dict, count: int = 10) -> list[Contact]:
    provider = get_provider(config)
    print(f"[research] Using provider: {config.get('provider', 'anthropic')}")

    # Inject search operator guidance into targeting for the provider
    targeting = dict(config["targeting"])
    search_guidance = _build_search_guidance(config)
    if search_guidance:
        targeting["_search_guidance"] = search_guidance

    config_with_guidance = dict(config)
    config_with_guidance["targeting"] = targeting

    contacts = provider.research(config_with_guidance["targeting"], count)
    print(f"[research] Found {len(contacts)} contacts")
    return contacts
