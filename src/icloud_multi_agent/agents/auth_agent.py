"""Simplified authentication agent with local session persistence."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import AuthAgent, Session


_SESSION_FILE = Path.home() / ".icloud_session.json"


@dataclass
class LocalAuthAgent:
    """A toy implementation storing session data locally."""

    session_file: Path = _SESSION_FILE

    def login(self, apple_id: str) -> dict:
        # In the real implementation we would start SRP login here. For now we
        # simply persist the apple_id to the session file and pretend that 2FA
        # is required.
        self.session_file.write_text(json.dumps({"apple_id": apple_id}))
        return {"requires2FA": True}

    def submit_2fa(self, code: str) -> Session:
        # Fake 2FA success and store a trusted session token.
        data = json.loads(self.session_file.read_text())
        session = Session(apple_id=data["apple_id"], session_token="mock-token", trusted=True)
        self.session_file.write_text(
            json.dumps({"apple_id": session.apple_id, "session_token": session.session_token, "trusted": True})
        )
        return session

    def load_session(self) -> Optional[Session]:
        if not self.session_file.exists():
            return None
        try:
            raw = json.loads(self.session_file.read_text())
        except json.JSONDecodeError:
            return None
        if "session_token" not in raw:
            return None
        return Session(apple_id=raw["apple_id"], session_token=raw["session_token"], trusted=raw.get("trusted", False))
