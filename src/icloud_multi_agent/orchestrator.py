"""High level orchestrator for the multi-agent workflow."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .agents import (
    AuthenticationError,
    AuthAgent,
    DownloadManager,
    ICloudAPI,
    IntegrityLog,
    ReportAgent,
    Session,
    StorageManager,
    Verifier,
)
from .agents.backup_indexer import BackupIndexer
from .policy import PolicyGate, PolicyViolation


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

    @dataclass
    class LoginState:
        """Represents the progress of a login attempt."""

        requires_two_factor: bool
        session: Optional[Session] = None

    def start_login(self, apple_id: Optional[str], password: Optional[str]) -> "Orchestrator.LoginState":
        """Kick off the login flow up to the point where 2FA is required."""

        existing = self.auth.load_session()
        if existing:
            self.integrity_log.record(
                "auth_session_restored", apple_id=existing.apple_id, trusted=existing.trusted
            )
            return Orchestrator.LoginState(requires_two_factor=False, session=existing)
        if not apple_id:
            raise ValueError("Apple ID must be provided when starting a new session")
        if not password:
            raise ValueError("Password must be provided when starting a new session")
        self.integrity_log.record("auth_login_attempt", apple_id=apple_id)
        try:
            login_result = self.auth.login(apple_id, password)
        except AuthenticationError as exc:
            self.integrity_log.record("auth_login_failed", apple_id=apple_id, reason=str(exc))
            raise
        except Exception as exc:  # pragma: no cover - unexpected failure path
            self.integrity_log.record("auth_login_error", apple_id=apple_id, error=str(exc))
            raise
        requires_two_factor = bool(login_result.get("requires2FA"))
        session = login_result.get("session")
        if session and not isinstance(session, Session):  # Defensive: tolerate mapping payloads
            session = Session(
                apple_id=getattr(session, "apple_id", apple_id),
                session_token=getattr(session, "session_token", ""),
                trusted=getattr(session, "trusted", False),
            )
        self.integrity_log.record(
            "auth_login",
            apple_id=apple_id,
            requires_2fa=requires_two_factor,
            trusted=session.trusted if session else False,
        )
        return Orchestrator.LoginState(requires_two_factor=requires_two_factor, session=session)

    def complete_two_factor(self, code: Optional[str]) -> Session:
        """Complete the login flow once a 2FA code has been provided."""

        if not code:
            raise ValueError("A 2FA code must be provided to complete login")
        self.integrity_log.record("auth_2fa_attempt")
        try:
            session = self.auth.submit_2fa(code)
        except AuthenticationError as exc:
            self.integrity_log.record("auth_2fa_failed", reason=str(exc))
            raise
        except Exception as exc:  # pragma: no cover - unexpected failure path
            self.integrity_log.record("auth_2fa_error", error=str(exc))
            raise
        self.integrity_log.record("auth", status="trusted" if session.trusted else "untrusted")
        for capability in self.policy.describe_capabilities():
            self.integrity_log.record("policy", capability=capability)
        return session

    def ensure_session(
        self,
        apple_id: Optional[str],
        password: Optional[str] = None,
        two_factor_code: Optional[str] = None,
    ) -> Session:
        state = self.start_login(apple_id, password)
        if state.session:
            return state.session
        code = two_factor_code or input("Enter 2FA code: ")
        return self.complete_two_factor(code)

    def _policy_denied(self, exc: PolicyViolation) -> PermissionError:
        """Translate a policy violation into a user-facing permission error."""

        message = (
            "Özel iCloud cihaz yedeklerine erişim politika gereği devre dışı. "
            "Komutu '--allow-private' bayrağıyla tekrar çalıştırın veya GUI'de "
            "'Özel uç noktalara izin ver' seçeneğini etkinleştirin."
        )
        self.integrity_log.record("policy_denied", capability="device_backups", reason=str(exc))
        return PermissionError(message)

    def list_backups(self) -> list[tuple[str, str, str, int]]:
        try:
            backups = self.indexer.list_backups()
        except PolicyViolation as exc:
            raise self._policy_denied(exc) from exc
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
        try:
            plan = self.api.plan_download(backup_id, destination)
        except PolicyViolation as exc:
            raise self._policy_denied(exc) from exc
        return plan.backup.device_name, plan.total_files, plan.total_bytes

    def download(self, backup_id: str, destination: Path):
        try:
            plan = self.api.plan_download(backup_id, destination)
        except PolicyViolation as exc:
            raise self._policy_denied(exc) from exc
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
