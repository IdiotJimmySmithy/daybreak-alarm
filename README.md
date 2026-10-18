# Daybreak Alarms

Custom wake-up alarms for Home Assistant, with an Apple-inspired editor, a dedicated **Alarms** sidebar, and a dashboard card.

Set your schedule, choose where the alarm plays, and combine sound with lights, scripts, and companion-app notifications. Alarms run in Home Assistant, so your browser or phone does not need to stay open.

## Features

- One-time alarms or repeating alarms on any combination of weekdays.
- Individual speaker, existing speaker group, and room targeting.
- Three bundled alarm tones, plus custom media URLs and Home Assistant media sources.
- Optional sound looping, volume control, and volume restoration.
- Optional lights, brightness settings, scripts, and phone notifications.
- Snooze, Skip next, Dismiss, and configurable auto-dismiss.
- A sidebar editor and dashboard card with an optional ringing popup.
- Native entities for alarm controls, status, and the next scheduled occurrence.
- Persistent schedules and snooze deadlines, with Home Assistant timezone support.
- Responsive light/dark layouts and 12- or 24-hour display.

Each output and optional alarm behavior can be enabled or disabled independently. New alarms start with external outputs off until you choose them.

## Installation

Requires **Home Assistant 2026.10.0 or newer**. Daybreak is a custom integration and works on Home Assistant OS; it does not require an OS add-on.

### HACS

1. Open **HACS → menu → Custom repositories**.
2. Enter this repository's GitHub URL and select **Integration**.
3. Add the repository and download **Daybreak Alarms**.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration** and select **Daybreak Alarms**.
6. Open **Alarms** in the sidebar.

The backend, sidebar, dashboard card, and sounds install together. No separate frontend repository or manual dashboard resource is required.

### Manual installation

1. Download and extract the repository.
2. Copy `custom_components/daybreak_alarm` into your Home Assistant configuration directory, creating `/config/custom_components/daybreak_alarm/manifest.json`.
3. Restart Home Assistant and add **Daybreak Alarms** under **Settings → Devices & services**.

## Create an alarm

Open **Alarms → Add alarm**, choose a time and label, then select the features you want. Turn on **Repeat** to choose individual days of the week. Use **Edit** to change an existing alarm.

| Setting | Behavior |
| --- | --- |
| Enabled | Schedule the alarm. Turning it off also stops ringing or cancels snooze. |
| Repeat | Run on selected weekdays. With Repeat off, the alarm disables after firing once. |
| Sound | Play on selected speakers, existing groups, rooms, or a combination. |
| Alarm sound | Choose Daybreak, Soft, Pulse, or a custom media URL/identifier. |
| Repeat sound | Keep playing until dismissed or the auto-dismiss time is reached. |
| Alarm volume | Optionally set playback volume and restore the previous volume afterwards. |
| Lights | Turn on selected lights, with an optional brightness override. |
| Scripts | Run selected Home Assistant scripts when the alarm rings. |
| App notifications | Notify selected companion-app devices, with optional Snooze/Dismiss buttons. |
| Snooze | Delay the current alarm by 1–120 minutes. |
| Skip next | Skip the next occurrence without changing a repeating schedule. |
| Auto-dismiss | Stop ringing after 1–120 minutes, or turn off to dismiss manually. |

Lights stay on after dismissal. Scripts run again when a snoozed alarm rings; dismissing does not cancel or undo their actions.

Inside the editor, **Save & test alarm** saves your settings and runs every enabled output. Audio stops after ten seconds, while the test notification stays visible on your phone. **Send phone-only test** checks the selected notification actions without saving edits or activating other outputs.

## Dashboard card

Edit a dashboard, choose **Add card**, and search for **Daybreak Alarms**. The card loads automatically when the integration is configured.

For a Manual card:

```yaml
type: custom:daybreak-alarm-card
title: Alarms
show_popup: true
```

The card provides alarm creation, editing, enable/disable, Skip next, Snooze, and Dismiss. Its visual editor exposes these display options:

| Option | Default | Description |
| --- | --- | --- |
| `title` | `Alarms` | Card heading. |
| `show_popup` | `true` | Show a ringing popup while this dashboard is open and visible. |
| `show_add` | `true` | Show the Add alarm control. |
| `show_edit` | `true` | Show Edit controls. |
| `use_24h` | `false` | Display times in 24-hour format. |
| `alarm_ids` | `[]` | Show all alarms, or only the listed IDs. |

Find an alarm's ID under **Edit → Automation ID**. Card filters affect which alarms appear on that card; they do not change scheduling.

The ringing popup offers Snooze and Dismiss. **Hide popup · keep ringing** or Escape closes only the popup. Disabling popups leaves sound and phone notifications enabled. Popups appear only on an open, visible dashboard containing the card.

## Native entities

Find entities under **Settings → Devices & services → Daybreak Alarms → entities**, or open the **Daybreak Alarms** device. Each saved alarm creates five entities:

| Entity | Purpose |
| --- | --- |
| Enabled switch | Enable or disable the alarm. |
| Snooze button | Snooze a ringing alarm when its Snooze option is enabled. |
| Dismiss button | Stop ringing or cancel a snoozed occurrence. |
| Status sensor | Report `idle`, `ringing`, `snoozed`, or `disabled`. |
| Next alarm sensor | Report the next scheduled or snoozed occurrence. |

Entity names include the alarm label. Their IDs remain stable when the label changes, and existing alarms receive entities automatically after upgrading. Snooze and Dismiss are unavailable when their action does not apply. A one-time alarm can still be snoozed or dismissed after its Enabled switch turns off.

Use these entities in standard dashboard cards and automations. Disabling an entity in Home Assistant's entity settings does not disable the alarm itself; use the alarm's Enabled switch for that.

## Speakers and phone notifications

Daybreak uses standard Home Assistant media-player actions. Direct playback requires a player that supports **Play media** and either **Stop** or **Pause**. Volume and native repeat are used when supported. Custom URLs, `/local/` paths, and `media-source://` identifiers are supported, subject to the player's media compatibility.

Speakers must be able to reach Home Assistant's media URL. Room membership is resolved when the alarm rings. Existing speaker groups are supported, but Daybreak does not create or regroup speakers. Select every member of a native group to avoid the alarm being blocked for including unselected speakers. Overlapping alarms cannot take control of the same speaker at the same time.

For phone notifications, connect the Home Assistant companion app and allow notifications. Select your device under **Edit → App notifications**. Devices appear through their `notify.mobile_app_*` actions. Optional **Prompt delivery on Android** requests immediate delivery and is off by default.

Notifications use the companion app and respect phone permissions, connectivity, and Focus/Do Not Disturb. Daybreak does not create alarms in the phone's Clock app or request critical-alert overrides.

## Automations

Daybreak exposes the following actions, each accepting `alarm_id`:

| Action | Purpose |
| --- | --- |
| `daybreak_alarm.enable` | Enable an alarm. |
| `daybreak_alarm.disable` | Disable an alarm and stop active output. |
| `daybreak_alarm.snooze` | Snooze the current ring. |
| `daybreak_alarm.dismiss` | Dismiss ringing or snooze. |
| `daybreak_alarm.skip` | Skip the next occurrence. |
| `daybreak_alarm.test` | Run the alarm's enabled outputs for a short test. |

```yaml
action: daybreak_alarm.dismiss
data:
  alarm_id: "COPY_FROM_THE_ALARM_EDITOR"
```

The `daybreak_alarm_fired` event includes `alarm_id`, `label`, and `test` for use in event-triggered automations.

Editing and control are available to Home Assistant administrators and system automations. Native entity state visibility follows Home Assistant's normal permissions. Alarms are shared across administrators.

## Scheduling and restarts

Schedules use Home Assistant's configured timezone. Saved alarms and snooze deadlines survive restarts. An occurrence up to two minutes late can still fire after an outage; older occurrences are marked missed. A missed one-time alarm is disabled.

An alarm interrupted while ringing is not replayed on startup. During daylight-saving changes, nonexistent spring times are skipped and a repeated autumn time rings only on its first occurrence. Changing Home Assistant's timezone recalculates future schedules while preserving snooze durations.

Home Assistant and the selected devices must remain available for alarms to run.

## Updates and troubleshooting

Update through HACS and restart Home Assistant, then fully reload the browser or companion app. For manual updates, replace `custom_components/daybreak_alarm` and restart. **Keep the existing integration entry** to retain your saved alarms; deleting the entry removes its alarm storage.

If upgrading from a version that required manual card registration, remove the old Daybreak entry from **Settings → Dashboards → Resources**, or from YAML-managed resources. The integration now loads the card automatically.

| Problem | Check |
| --- | --- |
| Sidebar missing | Add the integration under Devices & services, sign in as an administrator, and refresh the frontend. |
| Card missing | Confirm the integration is loaded, remove any old Daybreak resource, and fully reload the frontend. |
| Entities missing | Save at least one alarm, then filter the Entities list by Daybreak Alarms. |
| No sound | Check the alarm's output errors, player capabilities, media format, group membership, and media URL reachability. |
| No phone notification | Use the phone-only test, check the selected device and reported error, and verify companion-app notification settings. |

See [CHANGELOG.md](CHANGELOG.md) for release history and [HACS_SETUP.md](HACS_SETUP.md) for repository publishing instructions. Open `preview.html` to explore the interface with sample alarms without controlling devices.
