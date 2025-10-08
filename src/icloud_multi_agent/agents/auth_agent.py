"""Authentication agent backed by the real iCloud web service."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from icloudpy import ICloudPyService
from icloudpy.exceptions import (
    ICloudPy2SARequiredException,
    ICloudPyAPIResponseException,
    ICloudPyFailedLoginException,
)

from . import AuthenticationError, Session


@dataclass
class ICloudPyAuthAgent:
    """Authenticate against Apple's web endpoints via :mod:`icloudpy`."""

    session_file: Path = Path.home() / ".icloud_session.json"
    cookie_directory: Path = Path.home() / ".icloudpy"
    _service: Optional[ICloudPyService] = field(default=None, init=False, repr=False)
    _apple_id: Optional[str] = field(default=None, init=False, repr=False)
    _pending_device: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)

    def _write_session_state(
        self,
        *,
        apple_id: str,
        session_token: Optional[str],
        trusted: bool,
    ) -> None:
        payload = {"apple_id": apple_id, "trusted": trusted}
        if session_token:
            payload["session_token"] = session_token
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.session_file.write_text(json.dumps(payload), encoding="utf-8")

    def _build_session(self, service: ICloudPyService, apple_id: str) -> Session:
        data = service.session_data
        token = data.get("session_token") or data.get("session_id") or ""
        trusted = bool(service.is_trusted_session)
        return Session(apple_id=apple_id, session_token=str(token), trusted=trusted)

    # ------------------------------------------------------------------
    # AuthAgent API
    # ------------------------------------------------------------------
    def login(self, apple_id: str, password: str) -> dict:
        if not password:
            raise ValueError("Password must be provided for login")
        self.cookie_directory.mkdir(parents=True, exist_ok=True)
        try:
            service = ICloudPyService(
                apple_id,
                password,
                cookie_directory=str(self.cookie_directory),
            )
        except ICloudPyFailedLoginException as exc:
            raise AuthenticationError("Apple ID veya parola hatalı.") from exc
        except ICloudPyAPIResponseException as exc:
            raise AuthenticationError(f"iCloud oturum açma isteği reddedildi: {exc}") from exc
        except ICloudPy2SARequiredException as exc:
            # ``icloudpy`` raises this if the account mandates 2SA before we can
            # even inspect session state.
            raise AuthenticationError(str(exc)) from exc

        self._service = service
        self._apple_id = apple_id
        self._pending_device = None

        requires_two_factor = service.requires_2fa or service.requires_2sa
        if service.requires_2sa:
            devices = service.trusted_devices or []
            if not devices:
                raise AuthenticationError(
                    "İki adımlı doğrulama için kayıtlı cihaz bulunamadı."
                )
            device = devices[0]
            if not service.send_verification_code(device):
                raise AuthenticationError("Doğrulama kodu gönderilemedi.")
            self._pending_device = device

        session = None
        if not requires_two_factor:
            session = self._build_session(service, apple_id)
        self._write_session_state(
            apple_id=apple_id,
            session_token=session.session_token if session else None,
            trusted=session.trusted if session else service.is_trusted_session,
        )
        response = {"requires2FA": requires_two_factor}
        if session:
            response["session"] = session
        return response

    def submit_2fa(self, code: str) -> Session:
        if not code:
            raise AuthenticationError("2FA kodu boş olamaz.")
        if not self._service or not self._apple_id:
            raise AuthenticationError(
                "Aktif oturum bulunamadı. Lütfen önce Apple ID ve parolanızı gönderin."
            )

        service = self._service
        success = False
        try:
            if service.requires_2fa:
                success = service.validate_2fa_code(code)
            elif service.requires_2sa:
                device = self._pending_device
                if device is None:
                    devices = service.trusted_devices or []
                    if not devices:
                        raise AuthenticationError(
                            "Doğrulama için kullanılacak cihaz bulunamadı."
                        )
                    device = devices[0]
                success = service.validate_verification_code(device, code)
            else:
                success = True
        except ICloudPyAPIResponseException as exc:
            raise AuthenticationError(f"2FA doğrulaması başarısız: {exc}") from exc

        if not success:
            raise AuthenticationError("Girilen 2FA kodu geçersiz.")

        session = self._build_session(service, self._apple_id)
        self._write_session_state(
            apple_id=session.apple_id,
            session_token=session.session_token,
            trusted=session.trusted,
        )
        return session

    def load_session(self) -> Optional[Session]:
        # A completely password-less session restoration is not reliable across
        # processes, so for now we always require an explicit login.
        return None

    # ------------------------------------------------------------------
    # Helpers for other agents
    # ------------------------------------------------------------------
    def require_authenticated_service(self) -> ICloudPyService:
        """Return the active :class:`ICloudPyService` or raise an error.

        Cloud backup discovery relies on the authenticated service instance. The
        GUI/CLI must complete the login (including 2FA when required) before
        attempting to list iCloud backups. Raising :class:`AuthenticationError`
        here keeps the surface consistent with other auth failures.
        """

        if self._service is None:
            raise AuthenticationError(
                "iCloud oturumu bulunamadı. Önce Apple ID ile giriş yapıp 2FA doğrulamasını tamamlayın."
            )
        return self._service
