# Changelog

## 0.1.3 — 2026-10-17

### Added

- Five native Home Assistant entities per saved alarm: an Enabled switch, Snooze and Dismiss buttons, a Status sensor, and a Next alarm timestamp sensor.
- Automatic entity creation for existing and newly saved alarms, live state updates, and entity cleanup when an alarm is deleted.
- Stable entity identities across label changes and integration reloads.
- Automatic dashboard card loading when the integration is configured, with updated setup instructions.

### Fixed

- Shortened notification tags used by full alarm tests, scheduled alarms, and snoozed rings from 74 to 41 bytes to fit the iOS push limit.
- Preserved unique notification routing for each ring and matching notification cleanup on dismissal.
- Added entity-platform setup and unload handling, including cleanup after setup failures.

## 0.1.2 — 2026-10-17

### Added

- A bundled dashboard card with the shared alarm editor, enable/disable, Skip next, Snooze, and Dismiss.
- A visual card editor with configurable title, Add/Edit controls, time format, and alarm-ID filters.
- An optional ringing popup with Snooze, Dismiss, and Hide without stopping the alarm.
- Coordination across multiple cards to avoid duplicate popups, with controls tied to the current alarm occurrence.
- Visible Edit buttons and sidebar instructions for adding the dashboard card.
- A phone-only notification test with individual target results.
- Optional prompt delivery for Android notifications, disabled by default.

### Changed

- Moved alarm tests into the editor. Save & test saves the current settings before running the enabled outputs.
- Kept settings open during a test, with active alarm controls and output errors.
- Dispatched phone notifications alongside device outputs so slow speaker or media actions do not delay notification submission.
- Kept full-test notifications visible after the ten-second audio test finishes.

### Fixed

- Queued frontend refreshes that arrive during an existing request and ignored responses for disconnected components.
- Kept Save & test tied to its own save result when a background refresh completes first.

## 0.1.1 — 2026-10-17

### Added

- GitHub repository structure and metadata for installation as a HACS custom integration.
- Repository identity configuration, publishing instructions, and GitHub validation workflows.

### Fixed

- Preserved scheduled alarms when an alarm test or snoozed test overlaps the scheduled time.
- Prevented queued scheduler ticks from consuming alarms after unload or shutdown.
- Bounded media resolution so a stalled source cannot indefinitely block other outputs.
- Serialized cleanup for each alarm run to prevent duplicate stop and volume-restoration operations.
- Deferred frontend polling during saves and actions.

Existing v0.1.0 alarm settings, integration domain, and storage key were retained.

## 0.1.0

Initial release for manual installation on Home Assistant, including Home Assistant OS.

### Alarm management and interface

- Dedicated **Alarms** sidebar page with an Apple-inspired alarm editor.
- Create, edit, delete, enable, and disable alarms with individual labels and times.
- One-time alarms that disable after firing, and repeating alarms with independent Monday–Sunday selections.
- Optional Snooze with a duration of 1–120 minutes, including for one-time alarms after they fire.
- Optional Skip next, Dismiss, and auto-dismiss with a duration of 1–120 minutes.
- A next-alarm overview with a countdown, repeat-day summaries, and active ringing/snoozed states.
- Responsive desktop/mobile layouts, Home Assistant light/dark theme support, and a remembered 12-/24-hour display preference.
- Confirmation before deleting alarms or running a full alarm test.
- A ten-second audio test that also runs the alarm's enabled lights, scripts, and notifications.
- Per-alarm output errors and clear explanations for unavailable or unsupported targets.
- Administrator-only sidebar and controls, with one shared alarm collection.

### Sound and speaker targeting

- Playback through standard Home Assistant media-player actions, without a required speaker brand.
- Selection of individual speakers, existing groups, rooms, or a combination.
- Room membership resolved at ring time using entity areas or inherited device areas.
- Expansion of media-player helper groups and deduplication of selected targets.
- Group-boundary checks to prevent playback on unselected members of a native speaker group.
- Capability checks for playback, stopping/pausing, volume, and repeat.
- Three original bundled WAV tones: Daybreak, Soft, and Pulse.
- Custom media URLs and identifiers, including Home Assistant media sources and local media paths.
- Optional sound looping using native repeat where supported, with replay for compatible players.
- Optional alarm volume and restoration of the previous volume after stopping.
- Speaker ownership tracking so overlapping alarms do not control the same speaker simultaneously.

### Lights, scripts, and phone notifications

- Optional light activation with an independently configurable brightness override.
- Optional execution of selected Home Assistant scripts when an alarm rings, including after snooze.
- Companion-app notifications through selected `notify.mobile_app_*` actions.
- Optional notification Snooze and Dismiss buttons, with a unique token for each ring so old notifications cannot control a later occurrence.
- Independent switches for sound, lights, scripts, notifications, and their optional behaviors.
- New alarms start with external outputs disabled; alarms can also run with every output off.

### Scheduling and persistence

- Backend scheduling that continues with the browser and companion app closed.
- Persistent alarm configurations, next occurrences, and snooze deadlines in Home Assistant storage.
- Scheduling in Home Assistant's configured timezone, using an exact timer and periodic clock rechecks.
- Daylight-saving handling that skips nonexistent spring times and uses only the first occurrence of a repeated autumn time.
- Recalculation of future schedules after a timezone change while preserving absolute snooze deadlines.
- A two-minute grace period for late occurrences after an outage; older occurrences are marked missed.
- Restart recovery for snoozed alarms and interruption handling for alarms that were already ringing.
- Graceful stop and cleanup of active outputs when the integration unloads or Home Assistant shuts down.
- State persistence before external actions, revision checks for concurrent edits, and validation of saved alarm data.
- Independent output error handling so a failed device does not prevent attempts to run the remaining configured actions.
- Support for up to 100 saved alarms.

### Home Assistant integration and project tools

- A configuration flow for adding the integration through Devices & services, with one shared configuration entry.
- Automatic sidebar registration and bundled frontend/audio assets.
- WebSocket operations for loading, saving, deleting, and controlling alarms.
- The `daybreak_alarm.enable`, `disable`, `snooze`, `dismiss`, `skip`, and `test` actions for administrators and system automations.
- A visible Automation ID in the alarm editor.
- The `daybreak_alarm_fired` event with alarm ID, label, and test status, plus change events for frontend updates.
- A self-contained interactive preview with sample alarms and no device control.
- Tools to generate the bundled sounds and build a release archive.
