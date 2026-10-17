# Changelog

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
