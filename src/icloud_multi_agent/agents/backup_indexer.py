"""Backup indexing agent."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from . import BackupMeta, ICloudAPI


@dataclass
class BackupIndexer:
    api: ICloudAPI

    def list_backups(self) -> List[BackupMeta]:
        return self.api.list_device_backups()
