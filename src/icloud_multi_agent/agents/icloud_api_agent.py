"""Simplified iCloud API agent with mock and local backup sources."""
from __future__ import annotations

import json
import os
import plistlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence, Tuple

from ..policy import PolicyGate
from . import BackupMeta, DownloadItem, DownloadPlan, ICloudAPI


@dataclass
class MockICloudAPI(ICloudAPI):
    """A mock implementation backed by JSON fixtures on disk."""

    data_file: Path
    policy: PolicyGate

    def _resolve_data_file(self) -> Path | None:
        """Return the path to the mock data file if it can be located."""

        if self.data_file.exists():
            return self.data_file
        if not self.data_file.is_absolute():
            # Allow running the CLI/GUI from outside the project root by
            # resolving the relative path against potential package parents.
            for parent in Path(__file__).resolve().parents:
                candidate = parent / self.data_file
                if candidate.exists():
                    return candidate
        return None

    def _load_data(self) -> dict:
        path = self._resolve_data_file()
        if path is None:
            return {"photos": [], "drive": [], "device_backups": []}
        return json.loads(path.read_text())

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


def _coerce_datetime(value: object) -> str:
    """Return an ISO formatted timestamp for plist values."""

    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)


def _default_mobile_sync_dirs() -> List[Path]:
    """Return default MobileSync backup directories for the host OS."""

    env_override = os.environ.get("MOBILESYNC_BACKUP_DIR")
    if env_override:
        return [Path(part).expanduser() for part in env_override.split(os.pathsep) if part]

    home = Path.home()
    candidates = [
        home / "Library/Application Support/MobileSync/Backup",  # macOS
        home / "Library/MobileSync/Backup",  # legacy macOS path
        home / "AppData/Roaming/Apple Computer/MobileSync/Backup",  # Windows roaming
        home / "AppData/Roaming/Apple/MobileSync/Backup",
        home / "AppData/Local/Apple Computer/MobileSync/Backup",
        home / "AppData/Local/Apple/MobileSync/Backup",
    ]
    # Remove duplicates while preserving order
    seen: Dict[Path, None] = {}
    for candidate in candidates:
        expanded = candidate.expanduser()
        if expanded not in seen:
            seen[expanded] = None
    return list(seen.keys())


@dataclass
class MobileSyncICloudAPI(ICloudAPI):
    """Adapter that reads Finder/iTunes MobileSync backups from disk."""

    policy: PolicyGate
    root_dirs: Sequence[Path] | None = None
    fallback: ICloudAPI | None = None

    def __post_init__(self) -> None:
        roots = self.root_dirs or _default_mobile_sync_dirs()
        self._root_dirs = [Path(path).expanduser() for path in roots]

    def list_photos(self) -> Iterable[str]:
        if self.fallback is not None:
            return self.fallback.list_photos()
        return []

    def list_drive_items(self) -> Iterable[str]:
        if self.fallback is not None:
            return self.fallback.list_drive_items()
        return []

    def _iter_backup_dirs(self) -> Iterator[Path]:
        permission_errors: list[tuple[Path, PermissionError]] = []
        yielded = False
        for root in self._root_dirs:
            try:
                if not root.exists() or not root.is_dir():
                    continue
            except OSError:
                continue
            try:
                entries = list(root.iterdir())
            except PermissionError as exc:
                permission_errors.append((root, exc))
                continue
            except OSError:
                continue
            for child in entries:
                if child.is_dir():
                    yielded = True
                    yield child
        if not yielded and permission_errors:
            attempted = ", ".join(str(root) for root, _ in permission_errors)
            raise PermissionError(
                "MobileSync yedek klasörüne erişim izni bulunamadı. macOS'ta Sistem Ayarları > "
                "Güvenlik ve Gizlilik > Tam Disk Erişimi üzerinden Python'a yetki verin veya CLI'da "
                "'--mobile-sync-dir' bayrağıyla erişilebilir bir dizin belirtin. "
                f"Denenen dizinler: {attempted}"
            ) from permission_errors[0][1]

    def _read_plist_metadata(self, backup_dir: Path) -> Tuple[str, str, int]:
        info_file = backup_dir / "Info.plist"
        device_name = backup_dir.name
        created_at = ""
        approx_size = 0
        if info_file.exists():
            try:
                with info_file.open("rb") as fh:
                    info = plistlib.load(fh)
                device_name = info.get("Device Name", device_name)
                created_at = _coerce_datetime(info.get("Last Backup Date"))
                approx_size = int(info.get("Backup Size", info.get("Approximate Backup Size", 0)) or 0)
            except Exception:
                # Ignore corrupt or unreadable plist files and fall back to defaults.
                pass
        return device_name, created_at, approx_size

    def _discover_backups(self) -> Dict[str, Tuple[Path, BackupMeta]]:
        discovered: Dict[str, Tuple[Path, BackupMeta]] = {}
        for backup_dir in self._iter_backup_dirs():
            device_name, created_at, approx_size = self._read_plist_metadata(backup_dir)
            if not created_at:
                try:
                    created_at = _coerce_datetime(datetime.fromtimestamp(backup_dir.stat().st_mtime))
                except OSError:
                    created_at = ""
            try:
                if approx_size <= 0:
                    approx_size = sum(file.stat().st_size for file in backup_dir.rglob("*") if file.is_file())
            except OSError:
                approx_size = 0
            meta = BackupMeta(
                identifier=backup_dir.name,
                device_name=device_name,
                created_at=created_at,
                approx_size_bytes=approx_size,
                source="mobilesync",
            )
            discovered[backup_dir.name] = (backup_dir, meta)
        return discovered

    def has_any_backups(self) -> bool:
        try:
            next(self._iter_backup_dirs())
            return True
        except StopIteration:
            return False

    def list_device_backups(self) -> List[BackupMeta]:
        self.policy.require_private_access("device_backups")
        return [meta for _, meta in self._discover_backups().values()]

    def plan_download(self, backup_id: str, destination: Path) -> DownloadPlan:
        self.policy.require_private_access("device_backups")
        discovered = self._discover_backups()
        if backup_id not in discovered:
            raise FileNotFoundError(f"Backup {backup_id} not found in MobileSync directories")
        backup_dir, meta = discovered[backup_id]
        items: List[DownloadItem] = []
        total_bytes = 0
        for file in backup_dir.rglob("*"):
            if not file.is_file():
                continue
            try:
                size = file.stat().st_size
            except OSError:
                size = 0
            total_bytes += size
            items.append(
                DownloadItem(
                    logical_path=str(file.relative_to(backup_dir)),
                    source_path=file,
                    size_bytes=size,
                )
            )
        plan_meta = BackupMeta(
            identifier=meta.identifier,
            device_name=meta.device_name,
            created_at=meta.created_at,
            approx_size_bytes=total_bytes or meta.approx_size_bytes,
            source=meta.source,
        )
        return DownloadPlan(
            backup=plan_meta,
            total_files=len(items),
            total_bytes=total_bytes,
            items=items,
        )
