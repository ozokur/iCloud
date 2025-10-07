"""Policy gate helpers to ensure private endpoints remain opt-in."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class PolicyViolation(RuntimeError):
    """Raised when an operation violates the configured policy."""


@dataclass
class PolicyGate:
    """Simple helper encapsulating whether gated operations are allowed."""

    allow_private_endpoints: bool

    def require_private_access(self, capability: str) -> None:
        """Ensure the caller explicitly enabled private endpoints."""

        if not self.allow_private_endpoints:
            raise PolicyViolation(
                "Private iCloud backup endpoints are disabled. "
                "Set ALLOW_PRIVATE_ENDPOINTS=true to opt-in after acknowledging the risk."
            )

    def describe_capabilities(self) -> Iterable[str]:
        if self.allow_private_endpoints:
            yield "Private iCloud device backup inspection is ENABLED."
        else:
            yield "Private iCloud device backup inspection is DISABLED by policy."
