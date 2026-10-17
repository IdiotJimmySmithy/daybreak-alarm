"""Small adapter between the tested alarm engine and Home Assistant."""

from datetime import timedelta
import logging

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.network import get_url
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .actions import ActionRunner
from .const import DOMAIN, EVENT_CHANGED, EVENT_FIRED, STATIC_PATH, STORAGE_KEY
from .models import default_config

_LOGGER = logging.getLogger(__name__)


class HomeAssistantPort:
    def __init__(self, hass):
        self.hass = hass
        self.store = Store(hass, 1, STORAGE_KEY)
        self.cancel_timer = None
        self.engine = None
        self.runner = ActionRunner(self)
        self.ready = False

    @property
    def timezone(self):
        return self.hass.config.time_zone

    def now(self):
        return dt_util.utcnow()

    async def load(self):
        return await self.store.async_load()

    async def save(self, data):
        await self.store.async_save(data)

    @callback
    def arm(self, when):
        if self.cancel_timer:
            self.cancel_timer()
            self.cancel_timer = None
        if when is None or not self.ready:
            return

        @callback
        def fire(_now):
            self.cancel_timer = None
            self.hass.async_create_task(self._tick())

        # Slightly overdue restored alarms are processed by initialize/tick.
        when = max(when, self.now() + timedelta(milliseconds=10))
        self.cancel_timer = async_track_point_in_utc_time(self.hass, fire, when)

    async def _tick(self):
        if not self.ready:
            return
        try:
            await self.engine.tick()
        except Exception:
            _LOGGER.exception("Alarm scheduler failed; retrying in 30 seconds")
            self.arm(self.now() + timedelta(seconds=30))

    @callback
    def changed(self):
        self.hass.bus.async_fire(EVENT_CHANGED)

    @callback
    def fired(self, record):
        self.hass.bus.async_fire(EVENT_FIRED, {
            "alarm_id": record["id"], "label": record["config"]["label"],
            "test": record["runtime"]["last_result"] == "test",
        })

    async def start_outputs(self, record, current):
        return await self.runner.start(record, current)

    async def stop_outputs(self, record):
        await self.runner.stop(record)

    def player(self, entity_id):
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        a = state.attributes
        features = a.get("supported_features", 0)
        return {
            "id": entity_id, "state": state.state,
            "can_play": bool(features & MediaPlayerEntityFeature.PLAY_MEDIA),
            "can_stop": bool(features & MediaPlayerEntityFeature.STOP),
            "can_pause": bool(features & MediaPlayerEntityFeature.PAUSE),
            "can_volume": bool(features & MediaPlayerEntityFeature.VOLUME_SET),
            "can_repeat": bool(features & MediaPlayerEntityFeature.REPEAT_SET),
            "volume": a.get("volume_level"), "repeat": a.get("repeat"),
            "members": [x for x in a.get("entity_id", []) if isinstance(x, str) and x.startswith("media_player.")] if isinstance(a.get("entity_id"), list) else [],
            "group_members": [x for x in a.get("group_members", []) if isinstance(x, str) and x.startswith("media_player.")] if isinstance(a.get("group_members"), list) else [],
        }

    @callback
    def catalog(self):
        areas, devices, entities = ar.async_get(self.hass), dr.async_get(self.hass), er.async_get(self.hass)
        speakers, lights, scripts = [], [], []
        for state in self.hass.states.async_all():
            domain = state.entity_id.split(".", 1)[0]
            if domain not in ("media_player", "light", "script"):
                continue
            entry = entities.async_get(state.entity_id)
            device = devices.async_get(entry.device_id) if entry and entry.device_id else None
            area_id = (entry.area_id if entry else None) or (device.area_id if device else None)
            item = {"id": state.entity_id, "name": state.name, "area_id": area_id, "state": state.state}
            if domain == "media_player":
                item.update(self.player(state.entity_id))
                item["is_speaker"] = state.attributes.get("device_class") not in ("tv", "projector")
                speakers.append(item)
            elif domain == "light":
                lights.append(item)
            else:
                scripts.append(item)
        notifications = [{"id": name, "name": name.removeprefix("mobile_app_").replace("_", " ").title()}
                         for name in self.hass.services.async_services().get("notify", {}) if name.startswith("mobile_app_")]
        return {
            "speakers": sorted(speakers, key=lambda x: x["name"].lower()),
            "areas": [{"id": a.id, "name": a.name} for a in areas.async_list_areas()],
            "lights": sorted(lights, key=lambda x: x["name"].lower()),
            "scripts": sorted(scripts, key=lambda x: x["name"].lower()),
            "notifications": sorted(notifications, key=lambda x: x["name"].lower()),
            "defaults": default_config(),
        }

    async def call(self, domain, service, data):
        if not self.hass.services.has_service(domain, service):
            raise ValueError(f"{domain}.{service} is not available. Refresh the alarm editor and select a currently registered target.")
        if entity_id := data.get("entity_id"):
            state = self.hass.states.get(entity_id)
            if state is None or state.state == "unavailable":
                raise ValueError(f"Target unavailable: {entity_id}")
        await self.hass.services.async_call(domain, service, data, blocking=True)

    async def resolve_media(self, media_id, media_type):
        if media_id.startswith("builtin:"):
            name = media_id.split(":", 1)[1]
            if name not in ("daybreak", "soft", "pulse"):
                raise ValueError("Unknown built-in sound")
            media_id = f"{STATIC_PATH}/sounds/{name}.wav"
            media_type = "audio/wav"
        if media_id.startswith("media-source://"):
            from homeassistant.components import media_source
            resolved = await media_source.async_resolve_media(self.hass, media_id, None)
            media_id, media_type = resolved.url, resolved.mime_type
        if media_id.startswith("/") and not media_id.startswith("//"):
            media_id = get_url(self.hass, prefer_external=False).rstrip("/") + media_id
        return media_id, media_type

    async def notification_action(self, event):
        action = event.data.get("action", "")
        if not isinstance(action, str) or not action.startswith("DAYBREAK:"):
            return
        parts = action.split(":")
        if len(parts) != 4 or parts[1] not in ("snooze", "dismiss"):
            return
        _, command, alarm_id, token = parts
        if not token:
            return
        record = self.engine.records.get(alarm_id)
        if not record or not record["config"]["notify"]["enabled"] or not record["config"]["notify"]["actions_enabled"]:
            return
        try:
            await self.engine.action(alarm_id, command, token=token)
        except ValueError:
            _LOGGER.debug("Ignored inactive alarm notification action")
