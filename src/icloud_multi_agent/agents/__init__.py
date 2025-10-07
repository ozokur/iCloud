"""Agent interfaces for the iCloud backup helper."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Protocol


@dataclass
class Session:
    """Represents an authenticated iCloud session."""

    apple_id: str
    session_token: str
    trusted: bool


class AuthAgent(Protocol):
    """Authentication agent interface."""

    def login(self, apple_id: str, password: Optional[str] | None = None) -> dict:
        ...

    def submit_2fa(self, code: str) -> Session:
        ...

    def load_session(self) -> Optional[Session]:
        ...


@dataclass
class BackupMeta:
    """Metadata describing a discovered backup."""

    identifier: str
    device_name: str
    created_at: str
    approx_size_bytes: int
    source: str


@dataclass
class DownloadPlan:
    """Concrete plan to download a backup."""

    backup: BackupMeta
    total_files: int
    total_bytes: int
    items: List["DownloadItem"]


@dataclass
class DownloadItem:
    """Individual item that needs to be downloaded."""

    logical_path: str
    source_path: Path
    size_bytes: int


class ICloudAPI(Protocol):
    """Interface for iCloud API access."""

    def list_photos(self) -> Iterable[str]:
        ...

    def list_drive_items(self) -> Iterable[str]:
        ...

    def list_device_backups(self) -> List[BackupMeta]:
        ...

    def plan_download(self, backup_id: str, destination: Path) -> DownloadPlan:
        ...


class DownloadManager(Protocol):
    def run(self, plan: DownloadPlan, destination: Path) -> "DownloadResult":
        ...


@dataclass
class DownloadResult:
    downloaded_bytes: int
    downloaded_files: int
    failed_items: List[DownloadItem]


class Verifier(Protocol):
    def verify(self, destination: Path, plan: DownloadPlan) -> "VerificationReport":
        ...


@dataclass
class VerificationReport:
    ok: bool
    hashed_files: int
    failed_files: List[str]


class StorageManager(Protocol):
    def ensure_capacity(self, required_bytes: int, destination: Path) -> None:
        ...


class IntegrityLog(Protocol):
    def record(self, event: str, **context) -> None:
        ...


class ReportAgent(Protocol):
    def export(self, destination: Path, plan: DownloadPlan, result: DownloadResult, verification: VerificationReport) -> Path:
        ...
