"""Download manager implementing chunked copy for local sources."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..config import SETTINGS
from . import DownloadManager as DownloadManagerProtocol, DownloadPlan, DownloadResult


@dataclass
class LocalDownloadManager(DownloadManagerProtocol):
    """Download manager copying files from local paths."""

    chunk_size: int = SETTINGS.chunk_size_bytes

    def _copy_file(self, source: Path, destination: Path) -> int:
        destination.parent.mkdir(parents=True, exist_ok=True)
        bytes_written = 0
        with source.open("rb") as src, destination.open("wb") as dst:
            while True:
                chunk = src.read(self.chunk_size)
                if not chunk:
                    break
                dst.write(chunk)
                bytes_written += len(chunk)
        shutil.copystat(source, destination, follow_symlinks=True)
        return bytes_written

    def run(self, plan: DownloadPlan, destination: Path) -> DownloadResult:
        downloaded_bytes = 0
        downloaded_files = 0
        failed_items = []
        for item in plan.items:
            target = destination / item.logical_path
            try:
                downloaded_bytes += self._copy_file(item.source_path, target)
                downloaded_files += 1
            except (FileNotFoundError, OSError):
                failed_items.append(item)
        return DownloadResult(downloaded_bytes=downloaded_bytes, downloaded_files=downloaded_files, failed_items=failed_items)
