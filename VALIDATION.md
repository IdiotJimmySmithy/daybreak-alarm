# Validation report · v0.1.2

Date: October 17, 2026. Starting point: the supplied `daybreak-alarm-v0.1.1.zip`.
The supplied GitHub/HACS layout and previous fixes were preserved.

## Results for this update

**119 Python tests and 50 JavaScript tests pass (169 total).** These are local
software checks, not a claim that a physical phone received a notification or
that this update has passed Home Assistant, browser, or HACS installation testing.

| Check | Status | Boundary |
| --- | --- | --- |
| Supplied baseline | 106 Python + 31 JavaScript passed | Reproduced before edits |
| Updated Python suite | 119 passed | Real Python state machine and output tasks; explicit HA/device doubles |
| Updated JavaScript suite | 50 passed | Real templates/configuration/controller logic; small DOM doubles for popup policy |
| Python compilation | Passed | Component and runtime smoke-test syntax |
| JavaScript syntax | Passed | Panel, card entry point, browser script, and generated preview |
| Repository validation | Passed with template identity allowed | Layout, assets, versions, HACS metadata; publishing still requires your real GitHub identity |
| Repository setup helper | Passed on a temporary copy | Real identity substitution and strict validator |
| Release build | Passed | JSON/translations, AST, audio properties, generated preview, ZIP integrity |
| Real Chromium smoke | Not run | Browser binary unavailable; download denied HTTP 403 by this environment |
| Real Home Assistant smoke | Not run | HA is not installed; package lookup/install prerequisites unavailable here |
| Hosted GitHub checks | Not run | No connected repository/release was modified by this update |
| Real speaker / phone | Not run | No connection to the user's installation or hardware |

Runtime for executed checks: Python 3.12.14 and Node 24.19.0. The separate real-HA
job retains the supplied Python 3.14 / Home Assistant 2026.10.2 requirements.
The v0.1.1 archive contained a prior report of browser and HA runtime success;
that report is not carried forward as evidence for the changed v0.1.2 code.

## Verified regressions and changes

- Notification dispatch proceeds while media resolution is blocked. A blocked
  notification call also does not delay audio. Cancellation joins both tasks
  before cleanup, avoiding sends or playback continuing after cleanup.
- A normal alarm clears its own notification on stop; a ten-second full test
  leaves its test notification visible. Each ring keeps a unique notification tag.
- Phone-only tests call only the selected notification actions and report each
  success/failure separately. Their response explicitly does not confirm delivery.
- Disabled notifications, empty/non-phone targets, invalid prompt-delivery flags,
  non-admin users, and requests during HA startup are rejected at the API boundary.
- A stored v0.1.1 alarm receives the new notification option's default without
  changing its existing schedule. Existing scheduling/DST/restart tests still pass.
- A stale dashboard popup's token cannot dismiss a later ring.
- List/card templates expose Edit and omit test buttons outside settings.
  Save & test uses the returned saved alarm ID even if a refresh replaces the
  displayed snapshot. Phone-only tests preserve unsaved edits.
- Card filtering, disabled optional controls, label escaping, and disconnected
  controls are tested. Popup policy tests cover off, preview, hidden/background
  views, alarm-ID filters, duplicate cards, hide-without-dismiss, and a later ring.
- A changed event arriving during a fetch queues a fresh fetch. A detached
  component ignores an outstanding response.

The undelivered phone alert reported by the user has **no confirmed root cause**
in the supplied files: no phone logs or HA runtime access were included. The
timing/short-test-visibility issues are fixed, and diagnostics now distinguish
submission errors from delivery problems. Companion permissions, connectivity,
Focus/Do Not Disturb, or a selected device mismatch still need an on-device check.

## Browser and real-HA checks prepared for CI

`tests/browser-smoke.mjs` covers desktop/mobile editor workflows, visible Edit,
phone-test feedback, resource setup instructions, dashboard Save & test,
popup Snooze/Dismiss/Hide, popup-off/filtering, multiple-card coordination,
visual card-editor events, and theme. It uses the generated preview with a
simulated backend. It has been syntax-checked but not executed here.

`tests/ha_runtime_smoke.py` covers real configuration, authenticated HTTP and
WebSocket schemas, static delivery of the card/panel/audio, phone-test dispatch,
non-admin rejection, schedules, old action tokens, storage, and unload/reload.
Its device services are recorders, so even a successful CI run does not establish
phone delivery or physical audio behavior. It has been compile-checked but not
executed here. `--simulate-network` remains available for restricted test hosts.

The GitHub workflow also runs hassfest and HACS validation. These must run against
the configured repository before publishing the update.

## Reproduce

```sh
python -m unittest discover -s tests -v
node --test tests/frontend.test.mjs
python -m compileall -q custom_components
node --check custom_components/daybreak_alarm/frontend/panel.js
node --check custom_components/daybreak_alarm/frontend/card.js
node --check tests/browser-smoke.mjs
python tools/validate_repository.py --allow-template
python tools/build_release.py --output dist
```

Configure your real repository identity and omit `--allow-template` before
publishing. The template identity is intentionally rejected by strict validation.

With browser dependencies available:

```sh
npm install --no-save playwright
npx playwright install chromium
node tests/browser-smoke.mjs
```

In a separate Python 3.14 environment:

```sh
pip install -r requirements-ha-test.txt
python tests/ha_runtime_smoke.py
```

## Checks on your installation

1. Publish source with your existing repository identity, run GitHub checks,
   publish `v0.1.2`, update via HACS, and restart HA. Keep the integration entry.
2. Confirm existing alarms/schedules remain. Refresh the browser/app frontend.
3. Register the bundled card resource and add the card. Verify Edit, Save,
   enable/disable, optional switches, and a normal scheduled alarm.
4. In an alarm's App notifications settings, select the exact phone and send
   the phone-only test. Check both the per-target result and the actual phone.
5. Test the whole alarm from settings. Close settings to see the card popup;
   try Snooze, Dismiss, Hide, and popup-off. Test while the dashboard is closed
   to confirm backend audio/phone actions still work without a browser.

Administrator-only shared alarms, the existing two-minute missed-alarm policy,
speaker capability/group restrictions, and existing lights/script behavior remain.
