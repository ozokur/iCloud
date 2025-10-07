"""Simplified authentication agent with local session persistence."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from . import AuthAgent, AuthenticationError, Session


_SESSION_FILE = Path.home() / ".icloud_session.json"


try:  # pragma: no cover - defensive path calculation
    _DEFAULT_CREDENTIALS_FILE = Path(__file__).resolve().parents[3] / "data" / "mock_accounts.json"
except IndexError:  # pragma: no cover - running from an unexpected location
    _DEFAULT_CREDENTIALS_FILE = Path("data/mock_accounts.json").resolve()


@dataclass
class LocalAuthAgent:
    """A toy implementation storing session data locally."""

    session_file: Path = _SESSION_FILE
    credentials_file: Path = _DEFAULT_CREDENTIALS_FILE
    _cached_credentials: Dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def _load_credentials(self) -> Dict[str, str]:
        """Return a mapping of known Apple IDs to their passwords."""

        if self._cached_credentials:
            return self._cached_credentials

        if not self.credentials_file.exists():
            self._cached_credentials = {}
            return self._cached_credentials

        try:
            raw = json.loads(self.credentials_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - configuration error path
            raise AuthenticationError("Kimlik doğrulama bilgileri okunamadı.") from exc

        accounts = {}
        for entry in raw.get("accounts", []):
            apple_id = entry.get("apple_id")
            password = entry.get("password")
            if not apple_id or not password:
                continue
            accounts[apple_id.lower()] = password

        self._cached_credentials = accounts
        return self._cached_credentials

    def _write_session(self, payload: dict) -> None:
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.session_file.write_text(json.dumps(payload), encoding="utf-8")

    def login(self, apple_id: str, password: str) -> dict:
        # In the real implementation we would start SRP login here with the
        # provided password. For now we validate credentials against a mock
        # store and persist the Apple ID so the 2FA step can complete.
        if not password:
            raise ValueError("Password must be provided for login")

        credentials = self._load_credentials()
        expected_password = credentials.get(apple_id.lower())
        if expected_password is None or expected_password != password:
            raise AuthenticationError("Apple ID veya parola hatalı.")

        self._write_session({"apple_id": apple_id})
        return {"requires2FA": True}

    def submit_2fa(self, code: str) -> Session:
        # Fake 2FA success and store a trusted session token.
        if not code:
            raise AuthenticationError("2FA kodu boş olamaz.")
        if not self.session_file.exists():
            raise AuthenticationError("Aktif oturum bulunamadı. Lütfen önce Apple ID ve parolanızı gönderin.")
        data = json.loads(self.session_file.read_text(encoding="utf-8"))
        apple_id = data.get("apple_id")
        if not apple_id:
            raise AuthenticationError("Oturum bilgisi bozuk. Lütfen yeniden giriş yapın.")
        session = Session(apple_id=apple_id, session_token="mock-token", trusted=True)
        self._write_session({"apple_id": session.apple_id, "session_token": session.session_token, "trusted": True})
        return session

    def load_session(self) -> Optional[Session]:
        if not self.session_file.exists():
            return None
        try:
            raw = json.loads(self.session_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if "session_token" not in raw:
            return None
        return Session(apple_id=raw["apple_id"], session_token=raw["session_token"], trusted=raw.get("trusted", False))
