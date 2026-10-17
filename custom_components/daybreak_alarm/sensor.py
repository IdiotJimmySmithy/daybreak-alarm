"""Native alarm status and next-occurrence sensors."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .entity import DaybreakEntity, async_setup_alarm_entities
from .models import utc


async def async_setup_entry(hass, entry, async_add_entities):
    async_setup_alarm_entities(hass, entry, async_add_entities, "sensor",
        lambda entry, alarm_id: [AlarmStatusSensor(entry, alarm_id), AlarmNextSensor(entry, alarm_id)])


class AlarmStatusSensor(DaybreakEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["idle", "ringing", "snoozed", "disabled"]
    _attr_icon = "mdi:alarm"

    def __init__(self, entry, alarm_id):
        super().__init__(entry, alarm_id, "status", "status")

    @property
    def native_value(self):
        if not self.record:
            return None
        status = self.record["runtime"]["status"]
        if status == "idle" and not self.record["config"]["enabled"]:
            return "disabled"
        return status


class AlarmNextSensor(DaybreakEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:alarm"

    def __init__(self, entry, alarm_id):
        super().__init__(entry, alarm_id, "next_alarm", "next alarm")

    @property
    def native_value(self):
        if not self.record:
            return None
        runtime = self.record["runtime"]
        candidates = [runtime["next_at"]]
        if runtime["status"] == "snoozed":
            candidates.append(runtime["snooze_until"])
        return min((utc(when) for when in candidates if when), default=None)
