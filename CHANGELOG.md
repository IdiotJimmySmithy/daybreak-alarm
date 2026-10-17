# Changelog

## 0.1.3 — 2026-10-17

- Fix phone-notification tags in full tests, scheduled alarms, and snoozed rings:
  41 bytes instead of 74, below APNs' 64-byte collapse-ID limit. Preserve unique
  per-ring routing, notification actions, and matching clear-notification tags.
- Add five native entities per saved alarm: enabled switch, Snooze/Dismiss
  buttons, status sensor, and next-alarm timestamp sensor. Existing alarms gain
  entities on upgrade, names follow labels, and registry identities survive reloads.
- Add live entity updates and cleanup when an alarm is deleted. Preserve
  administrator-only controls while allowing system automations.
- Load the dashboard card automatically through Home Assistant's frontend module
  registration. Add/remove registration during integration setup/unload and show
  current setup instructions. Remove old manually registered card resources.
- Pass 135 Python and 50 JavaScript tests (185 total). Reproduce the previous tag
  failure with actual engine-generated UUIDs before fixing it. Expand the real-HA
  CI smoke script for native entities and card registration. Physical phone
  delivery, real HA, and Chromium are not verified in this environment.

## 0.1.2 — 2026-10-17

- Add a bundled dashboard card with the shared alarm editor, enable/disable,
  Skip next, Snooze, Dismiss, and visual card configuration.
- Add an optional ringing popup, filtered by card alarm IDs, with token-protected
  Snooze/Dismiss, hide-without-dismiss, and coordination across multiple cards.
- Add visible Edit buttons and sidebar instructions for card resource setup.
- Move alarm tests into settings; Save & test uses the saved draft and keeps
  settings open with active controls and output errors.
- Dispatch phone notifications alongside device outputs. Slow speaker/media
  actions no longer delay notification submission.
- Keep full-test notifications visible after the ten-second audio test.
- Add a phone-only test with per-target acceptance/error feedback and delivery
  troubleshooting. Tests do not imply a confirmed push receipt.
- Add optional prompt delivery for Android, off by default.
- Queue frontend refresh events during a request; ignore disconnected responses.
  Save & test retains its own save response even if a refresh completes first.
- Preserve HACS source layout, domain, storage key, and existing alarm settings.
- Pass 119 Python and 50 JavaScript checks. Extend browser/real-HA CI checks;
  those checks could not be executed in this revision's local environment.

## 0.1.1 — 2026-10-17

- Prepare repository for HACS custom integration installation, with repository
  identity setup, publishing instructions, and GitHub validation workflows.
- Preserve scheduled alarms when a test or snoozed test overlaps the due time.
- Prevent queued scheduler ticks from consuming alarms after unload/shutdown.
- Bound media resolution so a stalled source cannot indefinitely block other outputs.
- Serialize cleanup per alarm run to prevent duplicate stop/restore operations.
- Defer frontend polling during saves and actions.
- Add regression tests and independent real Home Assistant runtime smoke coverage.
- Preserve the existing domain, storage key, and existing v0.1.0 alarm settings.

## 0.1.0

Initial manually installable release supplied for review.
