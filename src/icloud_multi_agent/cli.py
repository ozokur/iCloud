"""Command line interface for the iCloud multi-agent helper."""
from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from typing import Optional

from .agents.auth_agent import LocalAuthAgent
from .agents.backup_indexer import BackupIndexer
from .agents.crypto_agent import HashVerifier
from .agents.download_manager import LocalDownloadManager
from .agents.icloud_api_agent import MockICloudAPI
from .agents.integrity_log import JsonlIntegrityLog
from .agents.report_agent import JsonReportAgent
from .agents.storage_manager import DiskStorageManager
from .config import SETTINGS
from .orchestrator import Orchestrator
from .policy import PolicyGate

DEFAULT_DATA_FILE = Path("data/mock_icloud.json")
DEFAULT_LOG_FILE = Path("outputs/logs/session.jsonl")
DEFAULT_REPORT_DIR = Path("outputs/icloud_backups/reports")


def build_orchestrator(allow_private: bool, data_file: Path) -> Orchestrator:
    policy = PolicyGate(allow_private_endpoints=allow_private)
    api = MockICloudAPI(data_file=data_file, policy=policy)
    indexer = BackupIndexer(api=api)
    downloader = LocalDownloadManager()
    verifier = HashVerifier()
    storage = DiskStorageManager()
    integrity = JsonlIntegrityLog(log_file=DEFAULT_LOG_FILE)
    reporter = JsonReportAgent(reports_dir=DEFAULT_REPORT_DIR)
    orchestrator = Orchestrator(
        auth=LocalAuthAgent(),
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
    password = args.password
    if password is None:
        password = getpass.getpass("Apple ID password: ")
    session = orchestrator.ensure_session(
        apple_id=args.apple_id,
        password=password,
        two_factor_code=args.code,
    )
    print(f"Trusted session for {session.apple_id} (token: {session.session_token})")


def cmd_backup_list(orchestrator: Orchestrator, args: argparse.Namespace) -> None:
    backups = orchestrator.list_backups()
    if not backups:
        print("No backups available under current policy.")
        return
    for identifier, device_name, created_at, approx_size in backups:
        print(f"{identifier}\t{device_name}\t{created_at}\t{approx_size} bytes")


def cmd_backup_plan(orchestrator: Orchestrator, args: argparse.Namespace) -> None:
    device_name, total_files, total_bytes = orchestrator.plan(args.id, Path(args.dest))
    print(f"Backup {args.id} ({device_name}) -> {total_files} files, {total_bytes} bytes")


def cmd_backup_download(orchestrator: Orchestrator, args: argparse.Namespace) -> None:
    destination = Path(args.dest)
    plan, result, verification, report = orchestrator.download(args.id, destination)
    print(f"Downloaded {result.downloaded_files}/{plan.total_files} files to {destination}")
    print(f"Verification {'OK' if verification.ok else 'FAILED'}")
    print(f"Report saved to {report}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="iCloud backup helper (mock implementation)")
    parser.add_argument("--data-file", default=DEFAULT_DATA_FILE, type=Path, help="Mock data JSON path")
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
    backup_list.set_defaults(func=cmd_backup_list)

    backup_plan = subparsers.add_parser("backup-plan", help="Summarise a backup before download")
    backup_plan.add_argument("--id", required=True)
    backup_plan.add_argument("--dest", default=str(SETTINGS.download_dir))
    backup_plan.set_defaults(func=cmd_backup_plan)

    backup_download = subparsers.add_parser("backup-download", help="Download a backup")
    backup_download.add_argument("--id", required=True)
    backup_download.add_argument("--dest", default=str(SETTINGS.download_dir))
    backup_download.set_defaults(func=cmd_backup_download)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    orchestrator = build_orchestrator(allow_private=args.allow_private, data_file=args.data_file)
    try:
        args.func(orchestrator, args)
    except Exception as exc:  # noqa: BLE001 - CLI surface should show errors
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
