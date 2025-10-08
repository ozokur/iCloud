# iCloud Multi-Agent Helper

This repository hosts a reference implementation of the multi-agent architecture described in
`agents.md`. It demonstrates how independent agents collaborate to authenticate, discover iCloud
backups, plan downloads, copy data, and produce verification reports. When private endpoints are
allowed the tool now queries Apple's (undocumented) backup listing endpoint via `icloudpy`, so your
**gerçek iCloud cihaz yedekleri** appear in the GUI/CLI. If the cloud API cannot be reached the
agents gracefully fall back to Finder/iTunes MobileSync folders or bundled mock data.

> ⚠️ **Important:** Apple does not provide a supported public API for downloading full iCloud device
> backups. Listing them requires granting the tool access to private endpoints after signing in with
> your Apple ID and completing 2FA. **Downloading** those cloud snapshots is still intentionally
> blocked—only local Finder/iTunes (MobileSync) backups can be copied. Proceed at your own risk and
> respect the platform's terms of service.

## Getting Started

1. Ensure Python 3.11+ is available.
2. Install the project in editable mode (optional):

   ```bash
   pip install -e .
   ```

3. Inspect the mock dataset in `data/mock_icloud.json`.
4. (Optional) Prepare Finder/iTunes MobileSync backups or ensure your iCloud account has active
   device backups.
5. Run the CLI:

   ```bash
   python -m icloud_multi_agent.cli --help
   ```

6. Launch the GUI (optional):

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
# Authenticate (stores session metadata under ~/.icloud_session.json)
python -m icloud_multi_agent.cli --allow-private \
  auth-login --apple-id user@example.com --password '••••••••' --code 000000

# List available backups. When private endpoints are enabled the command first attempts to
# contact Apple's backup service. Real iCloud snapshots will be listed alongside any local
# Finder/iTunes (MobileSync) backups. You can refresh the session inline by supplying the
# same Apple ID credentials.
python -m icloud_multi_agent.cli --allow-private \
  backup-list --apple-id user@example.com --password '••••••••' --code 000000

# Download the chosen backup into ./outputs/icloud_backups
python -m icloud_multi_agent.cli --allow-private \
  backup-download --id demo-backup \
  --apple-id user@example.com --password '••••••••' --code 000000
```

> ❗ **Cloud snapshots cannot be downloaded yet.** If you select an identifier that originates from
> the cloud API the CLI/GUI will stop and explain that only MobileSync folders are supported for
> copying. This keeps the project in line with Apple's published tooling while still letting you see
> which backups exist in iCloud.

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

- The `CloudBackupICloudAPI` adapter relies on icloudpy to talk to Apple's private backup listing
  endpoint. Oturum açıldıktan sonra hangi MobileBackup URL'si dönerse dönsün otomatik olarak onu
  hedefler. İndirme tarafı hâlâ devre dışı, ancak `agents/icloud_api_agent.py` içindeki analiz
  kodunu inceleyerek yeni veri kaynaklarıyla deney yapabilirsiniz.
- The `MobileSyncICloudAPI` adapter enumerates Finder/iTunes USB backups when private endpoints
  are allowed. You can add additional adapters (for example, to integrate with approved cloud
  storage) by following the same pattern.
- Implement stronger verification in `HashVerifier`, e.g. by comparing to manifest hashes.
- Extend the CLI/GUI to integrate with additional storage providers or richer verification flows.
