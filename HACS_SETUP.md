# Publish and install Daybreak Alarms through HACS

This is a **Home Assistant integration**, installed through HACS as **Integration**.
It is not a separate HACS frontend plugin or Home Assistant OS add-on.
The sidebar, optional dashboard card, and audio install with the integration.
The dashboard card loads automatically; no manual resource entry is needed.

## 1. Fill in your GitHub repository details

Extract the archive. Open a terminal in the extracted folder containing `hacs.json`.
Replace `YOUR_USERNAME` below with your GitHub account name:

```sh
python tools/configure_repository.py YOUR_USERNAME/daybreak-alarm
python tools/validate_repository.py
```

On Windows, `py` can be used instead of `python`. The first command changes only
`custom_components/daybreak_alarm/manifest.json`: documentation URL, issue tracker,
and code owner. It does not connect to GitHub or upload anything. For an organization,
add `--maintainer YOUR_PERSONAL_USERNAME`.

If you prefer not to run Python, edit that JSON file directly:

- `documentation`: `https://github.com/YOUR_USERNAME/daybreak-alarm`
- `issue_tracker`: `https://github.com/YOUR_USERNAME/daybreak-alarm/issues`
- `codeowners`: `["@YOUR_USERNAME"]`

Use the actual repository name if it differs. Do not leave `YOUR_GITHUB_USERNAME`
in the manifest. The validation workflow deliberately rejects that placeholder.

## 2. Create and populate the GitHub repository

Create a **public** repository, such as `daybreak-alarm`. Enable Issues, add a short
description, and set topics such as `home-assistant`, `hacs`, `custom-integration`,
and `alarm`. HACS does not support private repositories.

Upload the **contents** of the extracted folder, not the ZIP and not its outer
`daybreak-alarm-v0.1.3` folder. These paths must exist at the repository root:

| Path | Purpose |
| --- | --- |
| `hacs.json` | HACS metadata and minimum HA version |
| `README.md` | User documentation |
| `custom_components/daybreak_alarm/manifest.json` | HA integration metadata |
| `custom_components/daybreak_alarm/frontend/` | Sidebar, dashboard card, and three sounds |
| `.github/workflows/validate.yml` | Tests, hassfest, and HACS checks |

GitHub Desktop is a convenient option on Windows. With Git CLI in an empty new
remote repository, you can instead use:

```sh
git init
git add .
git commit -m "Release Daybreak Alarms 0.1.3"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/daybreak-alarm.git
git push -u origin main
```

Wait for the **Validate** GitHub workflow and inspect any failures. The workflow
runs real HA 2026.10.2 checks, unit tests, a browser smoke test, hassfest, and HACS
validation. These hosted checks have not been run merely by creating this ZIP.
The brands check is explicitly excluded because this is a custom repository;
listing in HACS's default catalog is a separate submission process.

## 3. Publish version 0.1.3 (recommended)

In GitHub, choose **Releases → Draft a new release**, create tag `v0.1.3` on the
validated commit, and publish it as a normal release. No release asset upload is
required: HACS downloads `custom_components/daybreak_alarm` from repository source.
Keep `zip_release` disabled. This source ZIP includes docs/tests and is not a
HACS `zip_release` component-only asset.

Without a release, HACS can install the default branch. A tag alone is not a
published GitHub Release. For future versions, update `manifest.json`, `const.py`,
and `package.json` to matching versions, plus `FRONTEND_VERSION` in `panel.js`
and the versioned import in `card.js`. Test, then publish a matching release.

## 4. Install into Home Assistant

Requires Home Assistant **2026.10.0 or newer** and an already working HACS installation.
This deliberately conservative minimum targets the 2026.10 API family checked in
this review. Older versions have not been runtime-tested.

1. Open **HACS** in Home Assistant.
2. Open the **three-dot menu → Custom repositories**.
3. Paste your public repository URL.
4. Choose **Integration**, then **Add**.
5. Find **Daybreak Alarms**, open it, and **Download** the release.
6. Restart Home Assistant.
7. Open **Settings → Devices & services → Add integration → Daybreak Alarms**.
8. Complete setup, then open **Alarms** in the sidebar. Refresh the browser if needed.

The sidebar is visible only to administrators and registers automatically. Do
not add `panel_custom:` YAML or a second frontend repository. Fully reload the
browser/app, then add **Daybreak Alarms** in the dashboard card picker. The card's
module loads automatically. Native controls appear under **Settings → Devices &
services → Daybreak Alarms → entities** for every saved alarm.

## Update an existing GitHub/HACS repository to 0.1.3

Replace the repository's source with the contents of this archive, preserving
your real GitHub `documentation`, `issue_tracker`, and `codeowners` in the
integration manifest. The attached template still has `YOUR_GITHUB_USERNAME`;
run the setup helper with your existing repository identity if needed. Preserve
your repository's other custom files and settings. Run validation, inspect CI,
then publish the `v0.1.3` release. Do not upload only this ZIP as the repository.

After HACS downloads the update, restart HA and refresh the browser/app frontend.
Keep the integration entry and existing storage. Remove any old manually added
Daybreak resource under **Settings → Dashboards → Resources**, or from YAML-managed
resources. The integration now loads the correct module automatically. Existing
alarms gain five native entities without recreating the alarms.

## Updating an existing manual installation

Back up Home Assistant first. Add the repository to HACS and download the
integration, then restart. Its domain and storage key are unchanged, so the
existing config entry and saved alarms remain. **Do not delete the integration
entry to update**: removing the entry intentionally deletes its alarm storage.
If HACS reports an existing unmanaged folder and cannot replace it, stop HA and
move only `/config/custom_components/daybreak_alarm` aside, install from HACS,
and restart; retain `.storage` and the integration entry.

## Verify your actual devices

Create a low-volume one-time alarm two minutes ahead. Close the browser and check
that it rings; verify dismiss, snooze, and auto-dismiss. Then test each optional
light, script, and phone notification. Restart HA and confirm the saved schedule
returns. Real device playback and phone delivery cannot be established by local
software tests; see `VALIDATION.md` for exact test boundaries.

Official references:
- https://www.hacs.xyz/docs/publish/integration/
- https://www.hacs.xyz/docs/publish/start/
- https://www.hacs.xyz/docs/faq/custom_repositories/
- https://www.hacs.xyz/docs/publish/action/
