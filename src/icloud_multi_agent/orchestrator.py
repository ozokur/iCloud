"""High level orchestrator for the multi-agent workflow."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .agents import AuthAgent, DownloadManager, ICloudAPI, IntegrityLog, ReportAgent, Session, StorageManager, Verifier
from .agents.backup_indexer import BackupIndexer
from .policy import PolicyGate


@dataclass
class Orchestrator:
    auth: AuthAgent
    api: ICloudAPI
    indexer: BackupIndexer
    downloader: DownloadManager
    verifier: Verifier
    storage: StorageManager
    integrity_log: IntegrityLog
    reporter: ReportAgent
    policy: PolicyGate

    def ensure_session(self, apple_id: Optional[str], two_factor_code: Optional[str] = None) -> Session:
        session = self.auth.load_session()
        if session:
            return session
        if not apple_id:
            raise ValueError("Apple ID must be provided when no trusted session exists")
        login_result = self.auth.login(apple_id)
        if not login_result.get("requires2FA"):
            raise RuntimeError("Unexpected login flow; mock implementation always requires 2FA")
        code = two_factor_code or input("Enter 2FA code: ")
        session = self.auth.submit_2fa(code)
        self.integrity_log.record("auth", status="trusted" if session.trusted else "untrusted")
        for capability in self.policy.describe_capabilities():
            self.integrity_log.record("policy", capability=capability)
        return session

    def list_backups(self) -> list[tuple[str, str, str, int]]:
        backups = self.indexer.list_backups()
        return [
            (
                backup.identifier,
                backup.device_name,
                backup.created_at,
                backup.approx_size_bytes,
            )
            for backup in backups
        ]

    def plan(self, backup_id: str, destination: Path) -> tuple[str, int, int]:
        plan = self.api.plan_download(backup_id, destination)
        return plan.backup.device_name, plan.total_files, plan.total_bytes

    def download(self, backup_id: str, destination: Path):
        plan = self.api.plan_download(backup_id, destination)
        self.storage.ensure_capacity(plan.total_bytes, destination)
        self.integrity_log.record(
            "download_start",
            backup_id=backup_id,
            files=plan.total_files,
            bytes=plan.total_bytes,
        )
        result = self.downloader.run(plan, destination)
        verification = self.verifier.verify(destination, plan)
        self.integrity_log.record(
            "download_complete",
            backup_id=backup_id,
            downloaded_bytes=result.downloaded_bytes,
            downloaded_files=result.downloaded_files,
            verification_ok=verification.ok,
        )
        report = self.reporter.export(destination, plan, result, verification)
        return plan, result, verification, report
