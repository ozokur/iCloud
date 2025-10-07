"""Package exposing the mock iCloud multi-agent helpers."""

from __future__ import annotations

try:  # pragma: no cover - metadata lookup is a trivial helper
    from importlib import metadata as importlib_metadata
except ImportError:  # Python <3.8 fallback, not expected but keeps lint happy
    import importlib_metadata  # type: ignore[import-not-found]


def _detect_version() -> str:
    """Return the installed package version if available."""

    package_name = "icloud-multi-agent"
    try:
        return importlib_metadata.version(package_name)
    except importlib_metadata.PackageNotFoundError:
        # Fallback for editable installs / direct source execution. Keep in sync
        # with ``pyproject.toml``.
        return "0.1.1"


__all__ = ["__version__"]
__version__ = _detect_version()
