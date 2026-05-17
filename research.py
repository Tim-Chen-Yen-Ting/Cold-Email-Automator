from providers import get_provider
from models import Contact


def research_contacts(config: dict, count: int = 10) -> list[Contact]:
    provider = get_provider(config)
    print(f"[research] Using provider: {config.get('provider', 'anthropic')}")
    contacts = provider.research(config["targeting"], count)
    print(f"[research] Found {len(contacts)} contacts")
    return contacts
