# iCloud Multi-Agent Helper

This repository hosts a **mock** implementation of the multi-agent architecture described in
`agents.md`. It demonstrates how independent agents collaborate to authenticate, discover iCloud
(backed by fixtures), plan downloads, copy data, and produce verification reports.

> ⚠️ **Important:** Apple does not provide a supported public API for downloading full iCloud device
> backups. The implementation here keeps those capabilities behind a policy gate and uses mock data
> only. To work with real backups you must integrate a compliant data source (e.g. Finder/iTunes USB
> backups) or accept the risks of private endpoints.

## Getting Started

1. Ensure Python 3.11+ is available.
2. Install the project in editable mode (optional):

   ```bash
   pip install -e .
   ```

3. Inspect the mock dataset in `data/mock_icloud.json`.
4. Run the CLI:

   ```bash
   python -m icloud_multi_agent.cli --help
   ```

## Example Workflow

```bash
# Authenticate (stores a mock session under ~/.icloud_session.json)
python -m icloud_multi_agent.cli --allow-private auth-login --apple-id user@example.com --code 000000

# List available backups (requires --allow-private)
python -m icloud_multi_agent.cli --allow-private backup-list

# Download the chosen backup into ./outputs/icloud_backups
python -m icloud_multi_agent.cli --allow-private backup-download --id demo-backup
```

The download command will produce:

- A copied folder structure under `outputs/icloud_backups`.
- Integrity logs in `outputs/logs/session.jsonl`.
- A JSON report in `outputs/icloud_backups/reports`.

## Extending to Real Sources

- Replace `MockICloudAPI` with an adapter that interfaces with an approved source (USB backups,
  iCloud Drive files, etc.).
- Implement stronger verification in `HashVerifier`, e.g. by comparing to manifest hashes.
- Expand the CLI or wrap it in a GUI orchestrator as described in `agents.md`.
