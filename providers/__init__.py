from typing import Protocol
from models import Contact, EmailDraft


class AIProvider(Protocol):
    def research(self, targeting: dict, count: int) -> list[Contact]: ...
    def draft(self, contact: Contact, config: dict) -> EmailDraft: ...


_PROVIDERS = {
    "anthropic": "providers.anthropic_client",
    "openai": "providers.openai_client",
    "gemini": "providers.gemini_client",
}


def get_provider(config: dict):
    name = config.get("provider", "anthropic").lower()
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown provider '{name}'. Choose from: {list(_PROVIDERS)}")
    import importlib
    return importlib.import_module(_PROVIDERS[name])
