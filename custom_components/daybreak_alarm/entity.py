"""Shared entity lifecycle for saved alarms, including alarms added after setup."""

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, EVENT_CHANGED, NAME, VERSION
from .models import Conflict, InvalidAlarm


@callback
def async_setup_alarm_entities(hass, entry, async_add_entities, platform, factory):
    """Register existing/new alarms and remove only this platform's deleted alarms."""
    port = entry.runtime_data
    registry = er.async_get(hass)
    seen = set()

    @callback
    def sync(_event=None):
        alarm_ids = set(port.engine.records)
        for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
            if registered.platform != DOMAIN or registered.domain != platform:
                continue
            alarm_id, separator, _key = registered.unique_id.partition(":")
            if separator and alarm_id not in alarm_ids:
                registry.async_remove(registered.entity_id)
        new_ids = alarm_ids - seen
        seen.intersection_update(alarm_ids)
        seen.update(new_ids)
        if new_ids:
            async_add_entities([
                entity for alarm_id in sorted(new_ids)
                for entity in factory(entry, alarm_id)
            ])

    entry.async_on_unload(hass.bus.async_listen(EVENT_CHANGED, sync))
    sync()


class DaybreakEntity(Entity):
    """An alarm entity with a stable ID, live state, and admin-only controls."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry, alarm_id, key, title):
        self.port = entry.runtime_data
        self.alarm_id = alarm_id
        self._title = title
        self._attr_unique_id = f"{alarm_id}:{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": "Daybreak",
            "model": "Alarm scheduler",
            "sw_version": VERSION,
        }

    @property
    def record(self):
        return self.port.engine.records.get(self.alarm_id)

    @property
    def name(self):
        label = self.record["config"]["label"] if self.record else "Alarm"
        return f"{label} {self._title}"

    @property
    def available(self):
        return self.port.ready and self.record is not None

    @property
    def extra_state_attributes(self):
        return {"alarm_id": self.alarm_id}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        @callback
        def changed(_event):
            self.async_write_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(EVENT_CHANGED, changed))

    async def _async_action(self, action):
        context = self._context
        if context and context.user_id:
            user = await self.hass.auth.async_get_user(context.user_id)
            if user is None or not user.is_admin:
                raise Unauthorized()
        if not self.available:
            raise HomeAssistantError("This alarm control is unavailable")
        try:
            await self.port.engine.action(self.alarm_id, action)
        except (InvalidAlarm, Conflict) as err:
            raise HomeAssistantError(str(err)) from err
