"""Simplified iCloud API agent with mock, local and cloud backup sources."""
from __future__ import annotations

import json
import logging
import os
import plistlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Sequence, Tuple

import requests

from ..policy import PolicyGate
from . import AuthenticationError, BackupMeta, DownloadItem, DownloadPlan, ICloudAPI
from .auth_agent import ICloudPyAuthAgent

_LOGGER = logging.getLogger(__name__)


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


def _normalise_timestamp(value: object) -> str:
    """Best-effort conversion of various timestamp formats to ISO strings."""

    if value is None:
        return ""
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return ""
        try:
            # Allow `Z` suffix while keeping timezone info.
            candidate = cleaned.replace("Z", "+00:00")
            return datetime.fromisoformat(candidate).isoformat()
        except ValueError:
            if cleaned.isdigit():
                value = int(cleaned)
            else:
                return cleaned
    if isinstance(value, (int, float)):
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return str(value)
        if seconds > 1_000_000_000_000:  # Assume milliseconds
            seconds /= 1000.0
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _parse_int(value: object) -> int:
    try:
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        cleaned = str(value).strip()
        if not cleaned:
            return 0
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0


def _maybe_snapshot(node: dict) -> bool:
    keys = {key.lower() for key in node.keys()}
    return any(key in keys for key in {"snapshotid", "snapshotuuid", "snapshotguid"})


def _contains_snapshots(node: dict) -> bool:
    for key in ("snapshots", "snapshotList", "snapshotInfos", "snapshotInfoList"):
        value = node.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def _device_identifier_from(node: dict) -> str:
    for key in ("backupUDID", "backupUUID", "uniqueIdentifier", "udid", "deviceID", "deviceUdid"):
        value = node.get(key) or node.get(key.lower())
        if value:
            return str(value)
    return ""


def _device_name_from(node: dict) -> str:
    for key in (
        "deviceName",
        "deviceDisplayName",
        "name",
        "displayName",
        "productName",
        "modelDisplayName",
    ):
        value = node.get(key)
        if value:
            return str(value)
    return ""


@dataclass
class CloudBackupICloudAPI(ICloudAPI):
    """Adapter that queries Apple's private backup endpoints via icloudpy."""

    auth: ICloudPyAuthAgent
    policy: PolicyGate
    fallback: ICloudAPI | None = None

    def list_photos(self) -> Iterable[str]:
        if self.fallback is not None:
            return self.fallback.list_photos()
        return []

    def list_drive_items(self) -> Iterable[str]:
        if self.fallback is not None:
            return self.fallback.list_drive_items()
        return []

    # ------------------------------------------------------------------
    # Cloud backup helpers
    # ------------------------------------------------------------------
    def _fetch_payload(self) -> dict:
        service = self.auth.require_authenticated_service()
        url = f"{service.setup_endpoint}/backup/list"
        params = getattr(service, "params", {})
        errors: list[Exception] = []
        for method in ("post", "get"):
            try:
                response = getattr(service.session, method)(
                    url,
                    params=params,
                    json={} if method == "post" else None,
                )
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status in {401, 403}:
                    raise AuthenticationError(
                        "iCloud oturumu süresi dolmuş görünüyor. Lütfen tekrar giriş yapın."
                    ) from exc
                errors.append(exc)
            except Exception as exc:  # noqa: BLE001 - defensive parsing for private APIs
                errors.append(exc)
        if errors:
            last = errors[-1]
            _LOGGER.debug("Failed to fetch iCloud backup list: %s", last, exc_info=last)
        return {}

    def _iter_backups(self, payload: Any) -> Iterator[tuple[dict, dict]]:
        stack: list[tuple[Any, dict]] = [(payload, {})]
        while stack:
            node, context = stack.pop()
            if isinstance(node, dict):
                device_name = _device_name_from(node)
                device_identifier = _device_identifier_from(node)
                new_context = context.copy()
                if device_name:
                    new_context.setdefault("device_name", device_name)
                if device_identifier:
                    new_context.setdefault("device_identifier", device_identifier)
                for key in (
                    "snapshotTimestamp",
                    "snapshotDate",
                    "modificationTimestamp",
                    "modificationTime",
                    "lastModified",
                    "lastUpdate",
                    "lastUpdateTimestamp",
                    "lastBackupDate",
                    "date",
                ):
                    if key in node and node.get(key) is not None:
                        new_context.setdefault("last_timestamp", node.get(key))
                        break
                for key in (
                    "sizeInBytes",
                    "snapshotSize",
                    "size",
                    "backupSize",
                    "storageUsed",
                    "quotaUsedInBytes",
                    "bytesUsed",
                ):
                    if key in node and node.get(key) is not None:
                        new_context.setdefault("size", node.get(key))
                        break
                if _maybe_snapshot(node):
                    yield node, new_context
                elif not _contains_snapshots(node) and device_identifier:
                    yield node, new_context
                for value in node.values():
                    if isinstance(value, (dict, list)):
                        stack.append((value, new_context))
            elif isinstance(node, list):
                for item in node:
                    stack.append((item, context))

    def _parse_backups(self, payload: Any) -> List[BackupMeta]:
        metas: Dict[str, BackupMeta] = {}
        for node, context in self._iter_backups(payload):
            identifier = None
            for key in (
                "snapshotID",
                "snapshotId",
                "snapshotUUID",
                "snapshotGuid",
                "backupUUID",
                "backupUDID",
                "uniqueIdentifier",
                "udid",
                "id",
            ):
                value = node.get(key)
                if value:
                    identifier = str(value)
                    break
            if not identifier:
                identifier = context.get("device_identifier")
            if not identifier:
                continue
            device_name = _device_name_from(node) or context.get("device_name") or "Bilinmeyen Cihaz"
            timestamp = ""
            for key in (
                "snapshotTimestamp",
                "snapshotDate",
                "modificationTimestamp",
                "modificationTime",
                "lastModified",
                "lastUpdate",
                "lastUpdateTimestamp",
                "lastBackupDate",
                "date",
            ):
                if key in node:
                    timestamp = _normalise_timestamp(node.get(key))
                    break
            if not timestamp:
                timestamp = _normalise_timestamp(context.get("last_timestamp"))
            size = 0
            for key in (
                "sizeInBytes",
                "snapshotSize",
                "size",
                "backupSize",
                "storageUsed",
                "quotaUsedInBytes",
                "bytesUsed",
            ):
                if key in node:
                    size = _parse_int(node.get(key))
                    break
            if not size:
                size = _parse_int(context.get("size"))
            metas[identifier] = BackupMeta(
                identifier=identifier,
                device_name=device_name,
                created_at=timestamp,
                approx_size_bytes=size,
                source="icloud",
            )
        return list(metas.values())

    # ------------------------------------------------------------------
    # ICloudAPI implementation
    # ------------------------------------------------------------------
    def list_device_backups(self) -> List[BackupMeta]:
        self.policy.require_private_access("device_backups")
        payload = self._fetch_payload()
        cloud_backups = self._parse_backups(payload)
        fallback_backups: List[BackupMeta] = []
        if self.fallback is not None:
            try:
                fallback_backups = self.fallback.list_device_backups()
            except PermissionError:
                # Propagate policy errors from fallbacks so they surface correctly.
                raise
            except Exception as exc:  # noqa: BLE001 - ignore best-effort fallbacks
                _LOGGER.debug("Fallback backup discovery failed: %s", exc, exc_info=exc)
        if not cloud_backups:
            return fallback_backups
        merged: Dict[str, BackupMeta] = {backup.identifier: backup for backup in fallback_backups}
        for backup in cloud_backups:
            merged[backup.identifier] = backup
        return list(merged.values())

    def plan_download(self, backup_id: str, destination: Path) -> DownloadPlan:
        self.policy.require_private_access("device_backups")
        payload = self._fetch_payload()
        cloud_backups = self._parse_backups(payload)
        cloud_ids = {backup.identifier for backup in cloud_backups}
        if backup_id in cloud_ids:
            raise NotImplementedError(
                "iCloud bulut yedekleri için doğrudan indirme henüz desteklenmiyor. "
                "Lütfen Finder/iTunes (MobileSync) yedeklerini kullanın."
            )
        if self.fallback is None:
            raise FileNotFoundError(f"Backup {backup_id} not available in fallbacks")
        return self.fallback.plan_download(backup_id, destination)
