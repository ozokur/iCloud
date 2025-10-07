"""Configuration helpers for the iCloud multi-agent tool."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    """Runtime configuration derived from environment variables."""

    download_dir: Path = Path(os.getenv("DOWNLOAD_DIR", "./outputs/icloud_backups")).expanduser()
    chunk_size_mb: int = int(os.getenv("CHUNK_SIZE_MB", "16"))
    max_parallel: int = int(os.getenv("MAX_PARALLEL", "4"))
    hash_algo: str = os.getenv("HASH_ALGO", "sha256")
    allow_private_endpoints: bool = os.getenv("ALLOW_PRIVATE_ENDPOINTS", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def chunk_size_bytes(self) -> int:
        return self.chunk_size_mb * 1024 * 1024


SETTINGS = Settings()
