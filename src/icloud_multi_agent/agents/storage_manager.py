"""Storage quota checks."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import StorageManager


@dataclass
class DiskStorageManager(StorageManager):
    safety_ratio: float = 0.15

    def ensure_capacity(self, required_bytes: int, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(destination)
        free_after = usage.free - required_bytes
        if free_after < 0 or free_after < usage.total * self.safety_ratio:
            raise OSError(
                "Insufficient disk space for download. "
                f"Required: {required_bytes}, Available: {usage.free}, Safety ratio: {self.safety_ratio:.0%}."
            )
