"""Integrity log agent writing JSON lines."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from . import IntegrityLog


@dataclass
class JsonlIntegrityLog(IntegrityLog):
    log_file: Path
    _file_handle: Any = field(init=False, repr=False, default=None)

    def _ensure_handle(self) -> None:
        if self._file_handle is None:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self._file_handle = self.log_file.open("a", encoding="utf-8")

    def record(self, event: str, **context: Dict[str, Any]) -> None:
        self._ensure_handle()
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "context": context,
        }
        self._file_handle.write(json.dumps(entry) + "\n")
        self._file_handle.flush()
