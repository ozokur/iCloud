"""Simplified iCloud API agent with a mock data source."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from ..policy import PolicyGate
from . import BackupMeta, DownloadItem, DownloadPlan, ICloudAPI


@dataclass
class MockICloudAPI(ICloudAPI):
    """A mock implementation backed by JSON fixtures on disk."""

    data_file: Path
    policy: PolicyGate

    def _load_data(self) -> dict:
        if not self.data_file.exists():
            return {"photos": [], "drive": [], "device_backups": []}
        return json.loads(self.data_file.read_text())

    def list_photos(self) -> Iterable[str]:
        return self._load_data().get("photos", [])

    def list_drive_items(self) -> Iterable[str]:
        return self._load_data().get("drive", [])

    def list_device_backups(self) -> List[BackupMeta]:
        self.policy.require_private_access("device_backups")
        backups = []
        for entry in self._load_data().get("device_backups", []):
            backups.append(
                BackupMeta(
                    identifier=entry["id"],
                    device_name=entry["device_name"],
                    created_at=entry["created_at"],
                    approx_size_bytes=entry.get("approx_size_bytes", 0),
                    source="icloud",
                )
            )
        return backups

    def plan_download(self, backup_id: str, destination: Path) -> DownloadPlan:
        self.policy.require_private_access("device_backups")
        data = self._load_data()
        matches = [b for b in data.get("device_backups", []) if b["id"] == backup_id]
        if not matches:
            raise FileNotFoundError(f"Backup {backup_id} not found in mock data")
        backup = matches[0]
        items: List[DownloadItem] = []
        total_bytes = 0
        for item in backup.get("items", []):
            source_path = Path(item["source_path"])
            size = int(item.get("size_bytes", source_path.stat().st_size if source_path.exists() else 0))
            total_bytes += size
            items.append(
                DownloadItem(
                    logical_path=item["logical_path"],
                    source_path=source_path,
                    size_bytes=size,
                )
            )
        return DownloadPlan(
            backup=BackupMeta(
                identifier=backup["id"],
                device_name=backup["device_name"],
                created_at=backup["created_at"],
                approx_size_bytes=backup.get("approx_size_bytes", total_bytes),
                source="icloud",
            ),
            total_files=len(items),
            total_bytes=total_bytes,
            items=items,
        )
