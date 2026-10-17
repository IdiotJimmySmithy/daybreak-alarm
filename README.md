# Daybreak Alarms · v0.1.2

A Home Assistant custom integration with an **Alarms** sidebar, a dashboard card, and an Apple-inspired alarm editor. The Python backend schedules the alarms; a browser or phone does not need to remain open.

Prepared for installation through a **HACS custom GitHub repository**, with regression fixes and automated checks. Start with [HACS_SETUP.md](HACS_SETUP.md) to configure your repository identity, publish the source, and install. The minimum declared version is Home Assistant 2026.10.0.

**169 automated tests pass** for this update. Browser and real Home Assistant checks are included in CI but could not run in the current environment because their dependencies could not be downloaded. Phone delivery and physical devices have not been tested here. See [VALIDATION.md](VALIDATION.md). This package has not been published to GitHub by this update.

New in 0.1.2: a dashboard card with an optional ringing popup, visible **Edit** buttons, tests inside alarm settings, and phone-only notification diagnostics. Existing saved alarms are retained.

## Install through HACS (recommended)

After publishing the repository as described in [HACS_SETUP.md](HACS_SETUP.md):

1. HACS → three-dot menu → **Custom repositories**.
2. Enter your public GitHub repository URL and choose **Integration**.
3. Add it, download **Daybreak Alarms**, and restart Home Assistant.
4. Settings → Devices & services → Add integration → **Daybreak Alarms**.
5. Open **Alarms** in the sidebar as an administrator.

HACS installs the backend, sidebar, card, and sounds together. The sidebar needs no resource setup. To use the optional dashboard card, register its bundled JavaScript resource once as described below. No OS add-on or separate HACS frontend repository is needed.

## Install on Home Assistant OS

1. Extract this ZIP on your computer.
2. Copy the entire `custom_components/daybreak_alarm` folder into your Home Assistant configuration directory, producing **`/config/custom_components/daybreak_alarm/manifest.json`**. Use your existing file-access method for the HA configuration directory. Do not copy the outer release folder into `custom_components`.
3. Restart Home Assistant.
4. In **Settings → Devices & services → Add integration**, search for **Daybreak Alarms** and finish the one-step setup.
5. Open **Alarms** in the sidebar. Refresh the browser if the item does not immediately appear.

The sidebar registers automatically. The optional dashboard card needs one JavaScript resource entry. You do not need Node, Python tooling, or npm on Home Assistant OS. This is a **custom integration**, not an OS app/add-on. The same component can be installed manually or through your HACS custom repository.

The first version is **administrator-only**, including its sidebar and WebSocket controls. It provides one shared collection for HA administrators. This keeps scheduled device control within the administrators’ existing authority. User-specific collections and non-admin delegation are not implemented.

## Dashboard card and ringing popup

Open **Alarms → Add a dashboard card** for the setup instructions in Home Assistant.

1. In your HA profile, enable **Advanced mode**. Open **Settings → Dashboards → menu → Resources**.
2. Add `/daybreak_alarm/static/card.js?v=0.1.2` with type **JavaScript module**. If a Daybreak resource already exists, update it instead of adding a duplicate.
3. Reload the browser/app frontend. Edit your dashboard → **Add card → Daybreak Alarms**. The visual editor lets you toggle the popup, Add/Edit buttons, and 24-hour display, or filter by alarm IDs.

For a Manual card:

```yaml
type: custom:daybreak-alarm-card
title: Alarms
show_popup: true
```

For YAML-managed resources, register the same URL under `lovelace.resources` with `type: module`. The integration must be configured for the static URL to exist.

The card supports creating/editing alarms, enable/disable, Skip next, Snooze, and Dismiss. Clicking **Edit** opens the same settings as the sidebar, including all tests. Snooze and Skip respect each alarm’s switches.

The ringing popup provides Snooze and Dismiss. **Hide popup · keep ringing** closes only the popup; Escape does the same. A hidden popup stays hidden for that ring in this browser, but a later ring can appear again. Multiple cards share one popup at a time. Popup buttons carry a ring token, so a stale popup cannot dismiss a later occurrence.

Popups require the card’s dashboard to be open and visible. They do not appear over other apps, on a closed dashboard, or in the HA card editor preview. Turning off the popup does not turn off sound, schedules, or phone notifications. The card retains the integration’s administrator-only access.

| Card option | Default | Purpose |
| --- | --- | --- |
| `show_popup` | `true` | Show the ringing dialog on this visible dashboard |
| `show_add` | `true` | Show Add alarm |
| `show_edit` | `true` | Show Edit buttons |
| `use_24h` | `false` | Display 24-hour times on this card |
| `alarm_ids` | `[]` | Empty means all alarms; otherwise show and pop up only these IDs |

Copy an alarm ID from **Edit → Automation ID**. Filters affect this card’s display, not backend scheduling or authorization.

## Create an alarm

Choose **Add alarm**, set the time and label, and turn on the outputs you want. New alarms have all external outputs off until you choose them. Saving with every output off is allowed; the alarm still updates its status and emits its Home Assistant event.

To change a saved alarm, use its visible **Edit** button. On the sidebar, the time/label is also clickable.

| Setting | Behavior |
| --- | --- |
| Alarm enabled | Master switch. Turning it off also cancels ringing or snooze. |
| Repeat | Pick any combination of Monday–Sunday, separately for each alarm. Off creates a one-time alarm, which disables when it fires. |
| Sound | Optional. Select individual media players, existing groups, rooms, or a combination. |
| Alarm sound | Three original bundled WAV tones, or your own URL/media identifier. `media-source://` identifiers and `/local/` paths are supported. |
| Repeat sound | Optional. Uses native repeat when available; otherwise bundled tones replay every eight seconds. Custom audio replays when the player reports `idle`. |
| Set alarm volume | Optional. Off preserves the current speaker volume. Restore volume afterwards is separately optional. |
| Lights | Optional. Turn on chosen lights; brightness override is independently optional. Lights remain on after dismissing. |
| Scripts | Optional. Start chosen existing HA scripts on each ring, including after snooze. Dismiss does not cancel or undo them. |
| App notifications | Optional. Send through selected `notify.mobile_app_*` actions. Notification buttons can be disabled separately. |
| Prompt delivery on Android | Optional, off by default. Uses `priority: high` and `ttl: 0` to request immediate delivery; offline devices do not receive a delayed alert. Does not override silent mode or Focus. |
| Snooze | Optional, with 1–120 minutes. Works for a one-time alarm even after its enabled switch turns off. |
| Allow skip next | Optional. Skip one scheduled occurrence; skipping a one-time alarm disables it. |
| Auto-dismiss | Optional, with 1–120 minutes. Off allows ringing until dismissed or disabled. |

The **12h / 24h** button changes the time display on that browser. The scheduling timezone is always the one configured in Home Assistant. Edit an alarm to find its ID under **Automation ID**.

Testing lives inside alarm settings, on both the sidebar and dashboard card. **Save & test alarm** saves your current settings, then runs every enabled output, including lights and scripts. Audio stops after ten seconds. Saving schedule changes recalculates the next occurrence normally; test playback itself does not consume it. A scheduled occurrence takes priority if it becomes due during a test. Test notifications remain on your phone until you clear them, so they are not removed before you can inspect them; their buttons only control the live test. You can Snooze or Dismiss from inside the settings while the test runs.

## Speaker compatibility and room targeting

The integration uses standard Home Assistant `media_player` actions and does not require one speaker brand. Direct alarm playback requires `PLAY_MEDIA` and either `STOP` or `PAUSE`. Volume and native repeat are used only when supported. The picker shows unsupported players with an explanation. A device that cannot play or stop arbitrary media may still be usable through an existing HA script.

“Connected to Home Assistant” alone does not guarantee playback of every media format. Some integrations accept only particular media IDs or streams. Use custom media supported by your player if the bundled WAV is incompatible. Speakers must be able to reach Home Assistant’s media URL; set a reachable internal URL in Home Assistant’s network settings if necessary. In particular, some speakers cannot resolve `homeassistant.local` or reach an HTTPS endpoint with a private certificate.

Room choices are resolved when the alarm rings, using entity areas or inherited device areas. They include speakers, receivers, and media players without a TV/projector class. Check room membership if you have unclassified TVs. Explicit individual targets remain available. Duplicate selections are deduplicated, and media-player helper groups are expanded.

A native speaker group that includes an unselected member is **blocked**, with an error shown on the alarm, rather than unexpectedly sounding in another room. Select every member of that group or ungroup it in the speaker’s existing controls. This release does not create, modify, or restore native multiroom groups. Synchronization of an existing group is supplied by its integration; separate players are not guaranteed sample-accurate synchronization. Group-boundary checks depend on the integration exposing its group membership.

Two ringing alarms cannot simultaneously take ownership of the same speaker. The later one reports that conflict but still runs its other selected outputs. Dismissing an alarm only stops players it claimed. Playback may interrupt existing music; this release does not snapshot or resume a previous queue.

## Scheduling and restart behavior

- Alarm configurations, one-time dates, next scheduled occurrences, and snooze deadlines are saved in HA’s private storage. State is saved **before** issuing external actions.
- The scheduler uses an exact UTC timer, with a 30-second recheck for clock corrections. Actual audio start time also depends on the speaker and network.
- After an outage, an occurrence up to **two minutes late** can still fire. Older occurrences are marked missed; they do not suddenly sound hours later. A missed one-time alarm is disabled, not moved to tomorrow.
- A snoozed alarm survives a restart, subject to the same late-arrival policy. An alarm already ringing at shutdown is marked interrupted and is not replayed on startup. During a graceful unload/shutdown the integration tries to stop its output. A power loss can leave an external stream playing; the integration cannot stop devices while HA is offline.
- During the spring daylight-saving gap, nonexistent local alarm times are skipped. During the autumn repeated hour, an alarm rings only at the **first** occurrence of that time. This policy is covered by automated tests.
- Changing HA’s timezone recomputes future schedule times in the new zone. Existing snooze deadlines remain absolute durations.
- Concurrent edits are protected with revisions: saving a stale editor returns a message to reopen it.
- Device failures are isolated. An unavailable speaker does not prevent a notification or another configured action. Errors appear under the alarm and in HA logs as appropriate.

Home Assistant and the relevant devices must be powered and available. Until the on-device checks below pass, retain your existing wake-up alarm.

## Phone app

Install/connect the Home Assistant companion app and grant it notification permission. Devices with a registered `notify.mobile_app_*` action appear automatically. When enabled, notifications offer **Dismiss** and, if allowed, **Snooze**. Buttons use a unique token for each ring, so tapping an old notification cannot dismiss a later occurrence.

In **Edit → App notifications**, select the phone and choose **Send phone-only test**. This uses the current phone selection without saving an alarm or starting speakers, lights, or scripts. Results identify each exact notification action and report acceptance or its error. Acceptance confirms Home Assistant processed the action, **not that the phone received a push**. Phone-only tests stay visible until cleared and have no alarm-action buttons.

Notifications now dispatch alongside device outputs, so a slow speaker/media lookup cannot hold up a phone alert. If no notification arrives after an accepted test, verify notification permission, Focus / Do Not Disturb, the exact selected device, and the companion app’s notification settings. Run the same `notify.mobile_app_*` action in **Developer tools → Actions** to separate a companion delivery problem from an alarm setup problem. Renamed/removed targets are shown as unavailable in the picker; replace them and retest. No specific cause for an undelivered physical-phone alert can be confirmed from this source package alone.

These are HA app notifications, not native alarms in Apple’s Clock or Android’s Clock. This release does not request critical-alert or Do Not Disturb overrides. Notification delivery depends on the companion app, permissions, connectivity, and platform behavior.

## Automation actions

Available actions: `daybreak_alarm.enable`, `disable`, `snooze`, `dismiss`, `skip`, and `test`. Each accepts `alarm_id`. For example:

```yaml
action: daybreak_alarm.dismiss
data:
  alarm_id: "COPY_THE_ID_FROM_THE_ALARM_EDITOR"
```

They are available to administrators and system automations. The `daybreak_alarm_fired` event has `alarm_id`, `label`, and `test`. Internal `daybreak_alarm_changed` events refresh the panel.

## First checks on your installation

1. Create a one-time alarm two minutes ahead with **sound only**, targeting one speaker. Use a low volume initially. Verify that it rings, dismiss stops it, and it disables after firing.
2. Enable snooze and verify the next ring, then disable snooze and confirm its controls disappear.
3. Enable app notifications and test their Dismiss/Snooze buttons. Confirm an old notification does not affect a newer alarm.
4. Try a room and an existing full group; confirm no unselected speaker sounds. Verify your selected custom audio format if applicable.
5. Test lights and scripts separately, then the combined alarm. Turn each feature off and confirm it does nothing.
6. Save an alarm, restart HA, and confirm the same schedule returns. Check on desktop and in the phone app.

The tests bundled here do not substitute for those hardware checks.

## Preview and development

Open **`preview.html`** in a modern browser to try the same editor and alarm list with sample data. Choose **Dashboard view** to try the card; use Save & test alarm inside Edit, then close the editor to see the popup. It is self-contained and requires no installation. No device is controlled, and a phone-test acceptance in this preview is simulated. Changes live only in the tab. The installed integration uses the Python engine.

Run the dependency-free automated suite from this directory with Python 3.12+ and Node 20+:

```sh
python3 -m unittest discover -s tests -v
node --test tests/frontend.test.mjs
python3 -m compileall -q custom_components
node --check custom_components/daybreak_alarm/frontend/panel.js
```

Optional real browser smoke checks (see VALIDATION.md for execution status):

```sh
npm install --no-save playwright
npx playwright install chromium
node tests/browser-smoke.mjs
```

Rebuild the original tones and release archive:

```sh
python3 tools/generate_sounds.py
python3 tools/build_release.py
```

## Troubleshooting, update, and removal

- Missing sidebar: ensure you are a HA administrator, the integration was added, and the browser refreshed. Review HA logs for `daybreak_alarm` if setup failed.
- No speakers or phones: first make them work through their normal HA integrations; this component does not pair hardware.
- No sound: open the alarm’s output-issue details; check player capabilities, media format, selected group members, and the reachable media URL.
- Card not found: ensure its resource URL is registered as a JavaScript module, the integration is loaded, and the browser has been refreshed. The type is `custom:daybreak-alarm-card`.
- No phone alert: use **Edit → App notifications → Send phone-only test**, check its exact per-target result, and follow the Phone app section above.
- Bad saved storage: setup fails rather than silently discarding alarms. Restore the HA backup or inspect the error before retrying.
- Update via HACS: download the new release and restart HA; keep the existing integration entry. For manual updates, replace only `/config/custom_components/daybreak_alarm` with the new version and restart HA. The stored alarms remain in `.storage`. Update the dashboard resource’s `?v=` value to the installed version and refresh the browser/app frontend.
- Remove: delete the Daybreak Alarms integration through HA’s Devices & services UI, which removes its stored alarms; then remove the component folder if desired. Restore a Home Assistant backup to recover removed alarms.

## Implementation references

Checked against the official guidance available on October 17, 2026:

- [Custom panels](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/)
- [Async static-path registration](https://developers.home-assistant.io/blog/2024/06/18/async_register_static_paths/)
- [WebSocket API extensions](https://developers.home-assistant.io/docs/frontend/extending/websocket-api/)
- [Config flows](https://developers.home-assistant.io/docs/core/integration/config_flow/)
- [Media playback](https://www.home-assistant.io/actions/media_player.play_media/)
- [Media-player groups](https://www.home-assistant.io/actions/media_player.join/)
- [Companion actionable notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/)
- [Custom dashboard cards](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card/)
- [Card editor and picker](https://contributors.home-assistant.io/frontend/custom-ui/card-editor/)
- [Notification clearing and behavior](https://companion.home-assistant.io/docs/notifications/notifications-basic/)
- [Android notification priority](https://companion.home-assistant.io/docs/notifications/critical-notifications/)

The included audio was synthesized for this project. No Apple code, icons, branding, or sound recordings are included.
