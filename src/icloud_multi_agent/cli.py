"""Command line interface for the iCloud multi-agent helper."""
from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from typing import Optional

from . import __version__
from .agents import AuthenticationError
from .agents.auth_agent import ICloudPyAuthAgent
from .agents.backup_indexer import BackupIndexer
from .agents.crypto_agent import HashVerifier
from .agents.download_manager import LocalDownloadManager
from .agents.icloud_api_agent import CloudBackupICloudAPI, MobileSyncICloudAPI, MockICloudAPI
from .agents.integrity_log import JsonlIntegrityLog
from .agents.report_agent import JsonReportAgent
from .agents.storage_manager import DiskStorageManager
from .config import SETTINGS
from .orchestrator import Orchestrator
from .policy import PolicyGate

DEFAULT_DATA_FILE = Path("data/mock_icloud.json")
DEFAULT_LOG_FILE = Path("outputs/logs/session.jsonl")
DEFAULT_REPORT_DIR = Path("outputs/icloud_backups/reports")


def _maybe_refresh_session(orchestrator: Orchestrator, args: argparse.Namespace) -> bool:
    """Ensure a trusted session exists when Apple ID credentials are supplied."""

    apple_id = getattr(args, "apple_id", None)
    if not apple_id:
        return True
    password = getattr(args, "password", None)
    if password is None:
        password = getpass.getpass("Apple ID password: ")
    try:
        orchestrator.ensure_session(
            apple_id=apple_id,
            password=password,
            two_factor_code=getattr(args, "code", None),
        )
    except AuthenticationError as exc:
        print(str(exc))
        return False
    return True


def build_orchestrator(allow_private: bool, data_file: Path, mobile_sync_dirs: list[Path] | None) -> Orchestrator:
    policy = PolicyGate(allow_private_endpoints=allow_private)
    auth = ICloudPyAuthAgent()
    mock_api = MockICloudAPI(data_file=data_file, policy=policy)
    if allow_private:
        mobilesync_api = MobileSyncICloudAPI(policy=policy, root_dirs=mobile_sync_dirs, fallback=mock_api)
        api = CloudBackupICloudAPI(auth=auth, policy=policy, fallback=mobilesync_api)
    else:
        api = mock_api
    indexer = BackupIndexer(api=api)
    downloader = LocalDownloadManager()
    verifier = HashVerifier()
    storage = DiskStorageManager()
    integrity = JsonlIntegrityLog(log_file=DEFAULT_LOG_FILE)
    reporter = JsonReportAgent(reports_dir=DEFAULT_REPORT_DIR)
    orchestrator = Orchestrator(
        auth=auth,
        api=api,
        indexer=indexer,
        downloader=downloader,
        verifier=verifier,
        storage=storage,
        integrity_log=integrity,
        reporter=reporter,
        policy=policy,
    )
    return orchestrator


def cmd_auth_login(orchestrator: Orchestrator, args: argparse.Namespace) -> None:
    password = args.password or getpass.getpass("Apple ID password: ")
    try:
        session = orchestrator.ensure_session(
            apple_id=args.apple_id,
            password=password,
            two_factor_code=args.code,
        )
        print(f"✅ Giriş başarılı!")
        print(f"   Apple ID: {session.apple_id}")
        print(f"   Oturum Güvenilir: {'Evet' if session.trusted else 'Hayır'}")
        print(f"   Token: {session.session_token[:20]}...")
        print("\n💡 Artık 'backup-list' komutuyla yedeklerinizi listeleyebilirsiniz.")
    except AuthenticationError as exc:
        print(f"❌ Kimlik doğrulama hatası: {exc}")


def cmd_backup_list(orchestrator: Orchestrator, args: argparse.Namespace) -> None:
    if not _maybe_refresh_session(orchestrator, args):
        return
    try:
        backups = orchestrator.list_backups()
    except (AuthenticationError, PermissionError) as exc:
        print(f"❌ Hata: {exc}")
        print("\n💡 İpucu: iCloud yedeklerini görmek için:")
        print("   1. '--allow-private' bayrağını kullanın")
        print("   2. '--apple-id' ile giriş yapın")
        print("\n   Örnek: icloud-helper backup-list --allow-private --apple-id sizin@email.com")
        return
    if not backups:
        print("⚠️  Hiç yedek bulunamadı.")
        print("\n💡 İpucu:")
        print("   • iCloud yedekleri için: '--allow-private --apple-id sizin@email.com' kullanın")
        print("   • USB yerel yedekler için: iOS cihazınızı bilgisayara bağlayın")
        print("   • Mock veriler için: 'data/mock_icloud.json' dosyasına yeni yedekler ekleyin")
        return
    print(f"✅ {len(backups)} yedek bulundu:\n")
    print("ID\t\t\t\tCihaz Adı\t\tOluşturulma Tarihi\t\tBoyut")
    print("=" * 100)
    for identifier, device_name, created_at, approx_size in backups:
        size_mb = approx_size / (1024 * 1024) if approx_size > 1024 * 1024 else approx_size / 1024
        size_unit = "MB" if approx_size > 1024 * 1024 else "KB"
        print(f"{identifier}\t{device_name[:20]}\t{created_at}\t{size_mb:.2f} {size_unit}")


def cmd_backup_plan(orchestrator: Orchestrator, args: argparse.Namespace) -> None:
    if not _maybe_refresh_session(orchestrator, args):
        return
    try:
        device_name, total_files, total_bytes = orchestrator.plan(args.id, Path(args.dest))
        size_gb = total_bytes / (1024 ** 3)
        print(f"📦 Yedek Planı:")
        print(f"   ID: {args.id}")
        print(f"   Cihaz: {device_name}")
        print(f"   Toplam Dosya: {total_files:,}")
        print(f"   Toplam Boyut: {size_gb:.2f} GB ({total_bytes:,} bytes)")
        print(f"   Hedef: {args.dest}")
    except (AuthenticationError, PermissionError, NotImplementedError) as exc:
        print(f"❌ Hata: {exc}")


def cmd_backup_download(orchestrator: Orchestrator, args: argparse.Namespace) -> None:
    destination = Path(args.dest)
    if not _maybe_refresh_session(orchestrator, args):
        return
    try:
        print("⏳ İndirme başlatılıyor...")
        plan, result, verification, report = orchestrator.download(args.id, destination)
        print(f"\n✅ İndirme tamamlandı!")
        print(f"   Dosyalar: {result.downloaded_files}/{plan.total_files}")
        print(f"   İndirilen: {result.downloaded_bytes / (1024**2):.2f} MB")
        print(f"   Hedef: {destination}")
        print(f"   Doğrulama: {'✅ Başarılı' if verification.ok else '❌ Başarısız'}")
        print(f"   Rapor: {report}")
    except (AuthenticationError, PermissionError, NotImplementedError) as exc:
        print(f"❌ Hata: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="iCloud backup helper (mock implementation)")
    parser.add_argument("--data-file", default=DEFAULT_DATA_FILE, type=Path, help="Mock data JSON path")
    parser.add_argument(
        "--mobile-sync-dir",
        action="append",
        type=Path,
        default=[],
        help="Additional MobileSync backup directory to search (can be repeated)",
    )
    parser.add_argument("--version", "-V", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--allow-private",
        action="store_true",
        default=SETTINGS.allow_private_endpoints,
        help="Enable private iCloud backup inspection (requires risk acknowledgement)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    auth_login = subparsers.add_parser("auth-login", help="Authenticate with Apple ID")
    auth_login.add_argument("--apple-id", required=True)
    auth_login.add_argument("--password", required=False, help="Apple ID password (prompted if omitted)")
    auth_login.add_argument("--code", required=False, help="2FA code (otherwise prompted)")
    auth_login.set_defaults(func=cmd_auth_login)

    backup_list = subparsers.add_parser("backup-list", help="List available backups")
    backup_list.add_argument("--apple-id", required=False, help="Apple ID (required for iCloud backups)")
    backup_list.add_argument("--password", required=False, help="Apple ID password (prompted if omitted when --apple-id is set)")
    backup_list.add_argument("--code", required=False, help="2FA/2SA code for the current login attempt")
    backup_list.set_defaults(func=cmd_backup_list)

    backup_plan = subparsers.add_parser("backup-plan", help="Summarise a backup before download")
    backup_plan.add_argument("--id", required=True)
    backup_plan.add_argument("--dest", default=str(SETTINGS.download_dir))
    backup_plan.add_argument("--apple-id", required=False, help="Apple ID for session refresh")
    backup_plan.add_argument("--password", required=False, help="Apple ID password (optional)")
    backup_plan.add_argument("--code", required=False, help="2FA/2SA code if required")
    backup_plan.set_defaults(func=cmd_backup_plan)

    backup_download = subparsers.add_parser("backup-download", help="Download a backup")
    backup_download.add_argument("--id", required=True)
    backup_download.add_argument("--dest", default=str(SETTINGS.download_dir))
    backup_download.add_argument("--apple-id", required=False, help="Apple ID for session refresh")
    backup_download.add_argument("--password", required=False, help="Apple ID password (optional)")
    backup_download.add_argument("--code", required=False, help="2FA/2SA code if required")
    backup_download.set_defaults(func=cmd_backup_download)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    mobile_sync_dirs = args.mobile_sync_dir or None
    orchestrator = build_orchestrator(
        allow_private=args.allow_private,
        data_file=args.data_file,
        mobile_sync_dirs=mobile_sync_dirs,
    )
    try:
        args.func(orchestrator, args)
    except Exception as exc:  # noqa: BLE001 - CLI surface should show errors
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
