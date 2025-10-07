"""Report exporting agent."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import DownloadPlan, DownloadResult, ReportAgent as ReportAgentProtocol, VerificationReport


@dataclass
class JsonReportAgent(ReportAgentProtocol):
    reports_dir: Path

    def export(
        self, destination: Path, plan: DownloadPlan, result: DownloadResult, verification: VerificationReport
    ) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.reports_dir / f"session_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
        report = {
            "backup": plan.backup.__dict__,
            "destination": str(destination),
            "download": {
                "files": result.downloaded_files,
                "bytes": result.downloaded_bytes,
                "failed": [item.logical_path for item in result.failed_items],
            },
            "verification": {
                "ok": verification.ok,
                "hashed_files": verification.hashed_files,
                "failed_files": verification.failed_files,
            },
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report_path
