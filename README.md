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

5. Launch the GUI (optional):

   ```bash
   python -m icloud_multi_agent.gui
   ```

   The window lets you configure whether private endpoints are allowed, browse to a mock data
   source, authenticate with your Apple ID/2FA code, refresh the backup list, and trigger downloads
   into a local directory.

## macOS One-Click Launcher

For macOS users the repository ships with `macos-launcher.command`. Double-clicking this file from
Finder (or running `open macos-launcher.command` from Terminal) will:

1. Verify that you are on macOS and locate `python3` (3.11+).
2. Create a dedicated virtual environment under `.venv_macos/` on the first run.
3. Install or update the project in editable mode inside that environment.
4. Start the Tkinter GUI once setup completes.

If `python3` cannot be found the launcher prints guidance for installing it from python.org. You can
pass additional arguments to the GUI (for example, `--allow-private`) by editing the command to call
`open macos-launcher.command --args --allow-private`. The script keeps the Terminal window open at
the end so you can review any messages or errors before closing.

## Example Workflow

```bash
# Authenticate (stores a mock session under ~/.icloud_session.json)
python -m icloud_multi_agent.cli --allow-private auth-login --apple-id user@example.com --code 000000

# List available backups (requires --allow-private). When Finder/iTunes
# MobileSync backups are present they will be listed automatically; otherwise
# the bundled mock data is used as a fallback.
python -m icloud_multi_agent.cli --allow-private backup-list

# Download the chosen backup into ./outputs/icloud_backups
python -m icloud_multi_agent.cli --allow-private backup-download --id demo-backup
```

The download command will produce:

- A copied folder structure under `outputs/icloud_backups`.
- Integrity logs in `outputs/logs/session.jsonl`.
- A JSON report in `outputs/icloud_backups/reports`.

On macOS the MobileSync directory is protected by "Full Disk Access". If you see a
`PermissionError` while listing backups, grant the Python interpreter access under **System
Settings → Privacy & Security → Full Disk Access** or copy the backups to a directory you control.

If your MobileSync backups live in a non-standard directory you can point the CLI at additional
locations using repeated `--mobile-sync-dir` flags:

```bash
python -m icloud_multi_agent.cli --allow-private \
  --mobile-sync-dir "D:/Backups/MobileSync" \
  backup-list
```

## Extending to Real Sources

- The `MobileSyncICloudAPI` adapter enumerates Finder/iTunes USB backups when private endpoints
  are allowed. You can add additional adapters (for example, to integrate with approved cloud
  storage) by following the same pattern.
- Implement stronger verification in `HashVerifier`, e.g. by comparing to manifest hashes.
- Extend the CLI/GUI to integrate with additional storage providers or richer verification flows.
