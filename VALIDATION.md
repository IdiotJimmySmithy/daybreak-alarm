# Validation report · v0.1.3

Date: October 17, 2026. Starting point: the previously delivered v0.1.2 source.
GitHub/HACS structure and the stored alarm schema are retained.

## Results

**135 Python tests and 50 JavaScript tests pass (185 total).** These are local
software checks using explicit Home Assistant/device doubles. They do not confirm
physical phone delivery or installation into a real Home Assistant instance.

| Check | Result | Boundary |
| --- | --- | --- |
| New notification regressions before fix | Failed as expected | Real engine UUIDs produced 74-byte tags rejected by a simulated 64-byte APNs limit |
| Python suite after fix | 135 passed | Real scheduler/output/entity code with HA and device doubles |
| JavaScript suite | 50 passed | Real frontend logic/templates with small DOM doubles |
| Python and JavaScript syntax | Passed | Component, scripts, and generated preview |
| Repository validation | Passed with template identity allowed | HACS layout, versions, assets, metadata |
| Repository setup helper | Passed on a temporary copy | Real identity substitution and strict validation |
| Release build | Passed | JSON/translations, Python AST, audio properties, preview, ZIP integrity |
| Real Home Assistant smoke | Not run | HA and its required environment are unavailable here |
| Chromium smoke | Not run | Browser binary unavailable; prior download denied HTTP 403 |
| Hosted GitHub/HACS checks | Not run | This update did not publish to a connected repository |
| Physical phone/speakers | Not run | No access to the user's installation or hardware |

Executed with Python 3.12.14 and Node 24.19.0. The GitHub workflow retains the
separate Python 3.14 / Home Assistant 2026.10.2 checks. Dependency restrictions
established earlier in this session prevent running real HA and browser checks
locally. Prior-version reports are not evidence for the changed code.

## Notification regression

The phone-only test used a 52-byte tag. Full tests and scheduled alarms combined
two 32-character UUIDs and a prefix into a 74-byte tag. The fix uses the unique
ring token with the prefix, producing 41 bytes. Apple's APNs documentation limits
`apns-collapse-id` to 64 bytes:
https://developer.apple.com/library/archive/documentation/NetworkingInternet/Conceptual/RemoteNotificationsPG/CommunicatingwithAPNs.html

Three tests failed before the patch and pass after it. They use actual
engine-generated alarm IDs and ring tokens with a gateway rejecting oversized
tags. Coverage includes scheduled alarms, full tests, snoozed rings, unchanged
notification action routing, unique later tags, and matching cleanup. Normal
alarms clear their notification on stop; full tests leave it visible.

This confirms an oversized-tag bug and its correction. It does not establish
that this was the only reason for the user's missing physical-phone delivery.

## Entity and card checks

- Existing/new alarms expose an enabled switch, Snooze and Dismiss buttons,
  status sensor, and next-alarm timestamp sensor.
- Duplicate labels have distinct IDs. Renaming preserves identity. Reloads retain
  stored configuration, next occurrence, and entity IDs. Deletion removes only
  the deleted alarm's registry entries, preserving unrelated integrations.
- Controls update saved state and sensors. Snooze respects its optional switch.
  One-time alarms retain Snooze/Dismiss after their enabled switch turns off.
  The next-alarm sensor reports the earlier of a schedule and snooze deadline.
- Admin controls and system automations work in contract tests. Non-admin entity
  actions and actions before readiness are rejected. Native state visibility
  follows normal Home Assistant permissions.
- Entity listeners are removed on unload. Failed platform unload preserves the
  scheduler and card. Setup failures clean up and allow a later retry.
- Setup registers the versioned card module with Home Assistant's frontend;
  unload removes it. Reload registers one current URL without duplicate static
  paths. Instructions now describe automatic loading and native entities.
- Existing scheduling, DST, restart, output isolation, optional-feature,
  authorization, card, and popup tests still pass.

The frontend helper and awaited platform setup were checked against official
Home Assistant sources:
https://github.com/home-assistant/core/blob/dev/homeassistant/components/frontend/__init__.py
https://developers.home-assistant.io/blog/2024/06/12/async_forward_entry_setups/

## CI checks prepared, not executed locally

`tests/ha_runtime_smoke.py` now checks real entity registration/state, native
switch/button services, non-admin denial, deletion cleanup, reload identity, and
frontend module registration/removal. Its recording phone service rejects tags
over 64 bytes. Existing real HTTP/WebSocket/storage/scheduling checks remain.
The services are test recorders, not physical hardware.

`tests/browser-smoke.mjs` checks the new setup instructions alongside existing
desktop/mobile editing, optional controls, card tests, popup actions, and visual
editor flows. Its preview uses a simulated backend. Both smoke scripts are
syntax-checked here; actual execution remains a release gate in GitHub.

## Reproduce

```sh
python -m unittest discover -s tests -v
node --test tests/frontend.test.mjs
python -m compileall -q custom_components tests tools
node --check custom_components/daybreak_alarm/frontend/panel.js
node --check custom_components/daybreak_alarm/frontend/card.js
node --check tests/browser-smoke.mjs
python tools/validate_repository.py --allow-template
python tools/build_release.py --output dist
```

Configure the repository identity and omit `--allow-template` before publishing.
Strict validation intentionally rejects `YOUR_GITHUB_USERNAME`. With browser
dependencies available, run `npm install --no-save playwright`,
`npx playwright install chromium`, and `node tests/browser-smoke.mjs`.
In a separate Python 3.14 environment, install `requirements-ha-test.txt` and run
`python tests/ha_runtime_smoke.py`.

## Checks on your installation

1. Preserve your real repository identity, upload source, run GitHub checks,
   and publish `v0.1.3`. Update via HACS and restart HA; keep the integration entry.
2. Remove any old manually registered Daybreak card resource. Fully reload the
   browser/app and add **Daybreak Alarms** from the dashboard card picker.
3. Confirm existing alarms/schedules remain. Open **Settings → Devices & services
   → Daybreak Alarms → entities** and check the five entities per saved alarm.
4. Select your phone in an alarm's notification settings. Try the phone-only test,
   full test, and a scheduled alarm a few minutes ahead with the dashboard closed.
   Check the actual phone and any errors shown under the alarm.
5. Exercise native enable/disable, Snooze, and Dismiss. Check the card/sensors
   update, optional popup behavior, and stable IDs/settings after a reload.
