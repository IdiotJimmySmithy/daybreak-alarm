# Validation report · v0.1.1

Date: October 17, 2026 (UTC). Reviewed from the supplied v0.1.0 archive.

## Result

The local software checks pass. The integration was loaded and exercised in a
real **Home Assistant Core 2026.10.2** process, with real HTTP, WebSocket,
authentication, config-entry, timer-helper, and storage APIs. A real Chromium
browser also exercised the standalone frontend preview. Physical speakers,
phone notifications, and the user's HA installation were not connected.

The repository is prepared for HACS **custom-repository** installation. Its
actual GitHub URL and maintainer must be entered before publishing; use
`tools/configure_repository.py` as explained in `HACS_SETUP.md`. No GitHub
repository, release, or successful HACS download is claimed by this report.

## Executed checks

| Check | Result | Scope |
| --- | --- | --- |
| Original baseline | 98 Python + 30 JavaScript passed | Reproduced the previous suite before editing |
| Revised Python suite | **106 passed** | Scheduling, timezone/DST, state persistence, access control contracts, output routing, new regressions, repository configuration |
| Revised JavaScript suite | **31 passed** | Templates, validation helpers, escaping, feature switches, stale-refresh regression |
| Chromium preview smoke | **Passed** | Desktop 1280×900, mobile 390×844, create/edit, repeat weekdays, snooze toggle, modal sizing, theme, zero page errors |
| Real Home Assistant 2026.10.2 smoke | **Passed** | Configuration, HTTP, WebSocket, services, authentication, schedule transitions, storage, unload/reload/removal |
| Python compile and JavaScript syntax | **Passed** | Component source parses successfully |
| Repository metadata/structure | **Passed with template identity explicitly allowed** | HACS layout, runtime files, versions, metadata keys |
| Repository setup helper | **Passed on a temporary copy** | Replaces identity and passes strict publish validation; rejects invalid repository URLs |
| Release builder | **Passed** | JSON, translations, Python AST, JS syntax, WAV assets, ZIP integrity |

The independent unit and frontend suites total **137 passing tests**. Browser
and real-HA smoke scenarios are additional checks, not included in that count.
The local Python unit suite used Python 3.12.14; HA used Python 3.14.8. Browser
smoke used Playwright 1.51.1 / Chromium 134 after downloads of the runtime's newer
browser bundle returned invalid archives. This is not a test of all browser versions.

## Defects reproduced and fixed

1. **A test could consume the real alarm.** If the scheduled time arrived during
   the ten-second test, the original scheduler could disable a one-time alarm
   without starting its real ring. Scheduled alarms now preempt test playback
   and snoozed tests. Test identity persists independently of status text.
2. **A queued tick could mutate storage after shutdown.** The scheduler checked
   its closed flag before waiting for its lock. It now checks again under the
   lock, preventing a queued tick from consuming an alarm after close.
3. **Media resolution could stall every later output.** Media-source resolution
   had no timeout. It now has an eight-second limit; resolution failure is
   recorded and lights/scripts/notifications can continue.
4. **Overlapping cleanup could stop or restore a speaker twice.** Dismiss and
   unload could enter cleanup for the same run together. They now share one
   cleanup task, with speaker ownership retained until cleanup finishes.
5. **A refresh could race an in-progress save/action.** A background request
   started during mutation could subsequently display older state. Refresh
   requests now defer while a mutation is in progress.

The new regressions were executed against the original behavior and failed
before the corresponding fixes. The existing 128 tests continue to pass.

## Real Home Assistant test details

`tests/ha_runtime_smoke.py` runs independently from the mocked adapter suite.
It creates a temporary HA configuration and uses the installed HA distribution.
It checks:

- The real UI configuration flow creates and loads the entry and refuses a duplicate.
- The registered panel is admin-only, uses the versioned bundled module, and
  the module plus all three audio files return HTTP 200.
- Authenticated WebSocket create/read/update/delete, invalid command rejection,
  and stale revision handling.
- A real HTTP service call starts the alarm; real HA service dispatch reaches
  recorded speaker, light, and notification service handlers. Dismiss calls stop.
- Built-in media resolves to the configured HTTP URL.
- A controlled clock advances a scheduled one-time alarm; it rings and disables,
  notification snooze works, and an old notification token cannot dismiss a later ring.
- A non-admin is denied both WebSocket access and the test service.
- HA storage survives actual config-entry unload/reload without duplicate static
  registration. Explicit entry removal deletes the alarm storage as documented.

**Test boundaries:** the local command uses `--simulate-network` because the
container denies OS network-adapter enumeration. That flag supplies a loopback
adapter list; HA's HTTP listener and requests remain real. Device services are
recorders, not hardware. Scheduled-time transitions use a controlled clock and
explicit engine ticks; actual overnight timing and OS clock corrections are not
measured. The test logs include unrelated environment warnings/errors for
multicast discovery/analytics and missing camera acceleration, plus expected
errors from intentional invalid-command and non-admin requests. The integration
itself loads and completes its asserted scenarios.

The Chromium test uses the self-contained preview's simulated backend. It
proves browser interaction and sizing, not the panel embedded inside the HA UI
or inside an iOS/Android companion app. The separate HA test covers the real
backend boundaries.

## HACS changes

- Added root `hacs.json`, using normal source installation and a conservative
  HA 2026.10.0 minimum. No custom ZIP-release download convention is required.
- Added manifest documentation/issue URLs and maintainer placeholders, with a
  setup helper and strict check that rejects unconfigured publishing metadata.
- Kept one runtime integration at `custom_components/daybreak_alarm`; its panel,
  translations, and sounds are all contained inside that directory.
- Bumped manifest, frontend cache version, and package metadata to 0.1.1.
- Added GitHub validation jobs for unit/browser/runtime tests, hassfest, and HACS.
  HACS's brands check is explicitly excluded for this custom repository.
- Added publishing, releases, install, upgrade, and on-device check instructions.
- Made the source builder exclude virtual environments, node_modules, and build
  output. No installed dependencies or caches are included in the source ZIP.

## Remaining checks

- **GitHub/HACS:** publish the configured source, inspect the hosted workflow
  results, then install through HACS. Hosted hassfest and HACS action results
  cannot be established until a repository exists. Inclusion in the default HACS
  catalog and home-assistant/brands is outside this custom-repository setup.
- **Your HA version/hardware:** Core 2026.10.2 is the runtime tested here. HA OS,
  other releases, real speaker codecs/volume/repeat behavior, group boundaries,
  mobile push delivery, and network URL reachability require installation checks.
- **Behavior retained:** administrator-only shared collection; no guarantee of
  sample-accurate multi-speaker synchronization; no restoration of an earlier
  music queue; lights/scripts are not undone; outages can prevent alarms; the
  configured two-minute late-arrival policy remains unchanged.

## Reproduce

From the source repository root:

```sh
python -m unittest discover -s tests -v
node --test tests/frontend.test.mjs
python tools/validate_repository.py --allow-template
python -m compileall -q custom_components
node --check custom_components/daybreak_alarm/frontend/panel.js
python tools/build_release.py --output dist
npm install --no-save playwright
npx playwright install chromium
node tests/browser-smoke.mjs
```

In a separate Python 3.14 virtual environment:

```sh
pip install -r requirements-ha-test.txt
python tests/ha_runtime_smoke.py
```

Use `--simulate-network` only for restricted test environments, as described
above. After configuring the real GitHub identity, run
`python tools/validate_repository.py` without `--allow-template`.
