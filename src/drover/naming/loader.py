"""Naming policy plugin discovery and loading."""

from drover.naming.base import BaseNamingPolicy
from drover.naming.nara import NARAPolicyNaming

# Registry of built-in naming policies
_BUILTIN_POLICIES: dict[str, type[BaseNamingPolicy]] = {
    "nara": NARAPolicyNaming,
}


class NamingPolicyLoader:
    """Discovers and loads naming policy plugins.

    Built-in policies are always available. User-provided policies
    can be registered programmatically.
    """

    def __init__(self) -> None:
        """Initialize loader with built-in policies."""
        self._policies: dict[str, BaseNamingPolicy] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        """Load all built-in naming policies."""
        for name, policy_cls in _BUILTIN_POLICIES.items():
            self._policies[name] = policy_cls()

    def get(self, name: str) -> BaseNamingPolicy | None:
        """Get a naming policy by name.

        Args:
            name: Policy identifier (e.g., "nara").

        Returns:
            NamingPolicy instance, or None if not found.
        """
        return self._policies.get(name)

    def list_available(self) -> list[str]:
        """Return list of available policy names."""
        return sorted(self._policies.keys())

    def register(self, policy: BaseNamingPolicy) -> None:
        """Register a custom naming policy.

        Args:
            policy: NamingPolicy instance to register.
        """
        self._policies[policy.name] = policy


# Singleton loader instance
_loader: NamingPolicyLoader | None = None


def get_naming_loader() -> NamingPolicyLoader:
    """Get the global naming policy loader instance."""
    global _loader
    if _loader is None:
        _loader = NamingPolicyLoader()
    return _loader


def get_naming_policy(name: str) -> BaseNamingPolicy:
    """Get a naming policy by name.

    Args:
        name: Policy identifier.

    Returns:
        NamingPolicy instance.

    Raises:
        ValueError: If policy not found.
    """
    loader = get_naming_loader()
    if policy := loader.get(name):
        return policy
    available = ", ".join(loader.list_available())
    raise ValueError(f"Unknown naming policy '{name}'. Available: {available}")
