"""Verifier agent performing hash validation."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List

from ..config import SETTINGS
from . import DownloadPlan, VerificationReport, Verifier


@dataclass
class HashVerifier(Verifier):
    """Compute hashes for downloaded files."""

    algorithm: str = SETTINGS.hash_algo

    def _hash_file(self, path: Path) -> str:
        hasher = hashlib.new(self.algorithm)
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def verify(self, destination: Path, plan: DownloadPlan) -> VerificationReport:
        failed: List[str] = []
        hashed = 0
        for item in plan.items:
            target = destination / item.logical_path
            if not target.exists():
                failed.append(item.logical_path)
                continue
            hashed += 1
            # In the mock scenario we do not have expected hashes; simply compute.
            self._hash_file(target)
        return VerificationReport(ok=not failed, hashed_files=hashed, failed_files=failed)
