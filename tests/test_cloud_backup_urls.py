from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from icloud_multi_agent.agents.icloud_api_agent import CloudBackupICloudAPI
from icloud_multi_agent.policy import PolicyGate


def _build_api():
    dummy_auth = SimpleNamespace(require_authenticated_service=lambda: None)
    policy = PolicyGate(allow_private_endpoints=True)
    return CloudBackupICloudAPI(auth=dummy_auth, policy=policy)


def test_backup_service_urls_prefers_explicit_mobilebackup_endpoint():
    api = _build_api()
    service = SimpleNamespace(
        setup_endpoint="https://setup.icloud.com/setup/ws/1",
        data={
            "webservices": {
                "mobilebackup": {"url": "https://setup.icloud.com/setup/ws/1/mobilebackup"}
            }
        },
    )

    def _get_webservice_url(key: str) -> str:
        assert key == "mobilebackup"
        return "https://p123-mobilebackup.icloud.com/mbs"

    service._get_webservice_url = _get_webservice_url  # type: ignore[attr-defined]

    urls = api._backup_service_urls(service)
    assert urls[0] == "https://p123-mobilebackup.icloud.com/mbs"
    assert "https://p123-mobilebackup.icloud.com/mbs" in urls
    assert urls[1] == "https://setup.icloud.com/setup/ws/1/mobilebackup"
    assert urls[-1] == "https://setup.icloud.com/setup/ws/1/backup"


def test_backup_service_urls_handles_missing_helpers():
    api = _build_api()
    service = SimpleNamespace(
        setup_endpoint="https://setup.icloud.com/setup/ws/1",
        data={},
    )

    urls = api._backup_service_urls(service)
    assert urls == ["https://setup.icloud.com/setup/ws/1/backup"]
