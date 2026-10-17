"""Enable or disable each saved alarm using a native switch."""

from homeassistant.components.switch import SwitchEntity

from .entity import DaybreakEntity, async_setup_alarm_entities


async def async_setup_entry(hass, entry, async_add_entities):
    async_setup_alarm_entities(hass, entry, async_add_entities, "switch",
                              lambda entry, alarm_id: [AlarmEnabledSwitch(entry, alarm_id)])


class AlarmEnabledSwitch(DaybreakEntity, SwitchEntity):
    _attr_icon = "mdi:alarm-check"

    def __init__(self, entry, alarm_id):
        super().__init__(entry, alarm_id, "enabled", "enabled")

    @property
    def is_on(self):
        return bool(self.record and self.record["config"]["enabled"])

    async def async_turn_on(self, **kwargs):
        await self._async_action("enable")

    async def async_turn_off(self, **kwargs):
        await self._async_action("disable")
