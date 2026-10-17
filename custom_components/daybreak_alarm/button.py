"""Native snooze and dismiss buttons for active alarms."""

from homeassistant.components.button import ButtonEntity

from .entity import DaybreakEntity, async_setup_alarm_entities


async def async_setup_entry(hass, entry, async_add_entities):
    async_setup_alarm_entities(hass, entry, async_add_entities, "button",
        lambda entry, alarm_id: [AlarmButton(entry, alarm_id, action)
                                for action in ("snooze", "dismiss")])


class AlarmButton(DaybreakEntity, ButtonEntity):
    def __init__(self, entry, alarm_id, action):
        super().__init__(entry, alarm_id, action, action)
        self.action = action
        self._attr_icon = "mdi:alarm-snooze" if action == "snooze" else "mdi:alarm-off"

    @property
    def available(self):
        if not super().available:
            return False
        status = self.record["runtime"]["status"]
        if self.action == "snooze":
            return status == "ringing" and self.record["config"]["snooze_enabled"]
        return status in ("ringing", "snoozed")

    async def async_press(self):
        await self._async_action(self.action)
