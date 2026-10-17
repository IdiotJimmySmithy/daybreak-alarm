"""Entity lifecycle contract checks using explicit HA registry/platform doubles."""

import asyncio
from copy import deepcopy
import importlib
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from support import PACKAGE, models
from test_ha_contract import FakeBus, FakeHass, HAError, Unauthorized, bootstrap
from homeassistant.helpers import entity_registry as er

PLATFORMS = {name: importlib.import_module(f"{PACKAGE}.{name}")
             for name in ("switch", "button", "sensor")}


class Registry:
    def __init__(self):
        self.entries = {}
        self.removed = []

    def async_remove(self, entity_id):
        self.entries.pop(entity_id)
        self.removed.append(entity_id)


class EventBus(FakeBus):
    def async_fire(self, name, data=None):
        super().async_fire(name, data)
        for listener in list(self.listeners.get(name, [])):
            result = listener(NS(data=data or {}))
            if result is not None:
                asyncio.create_task(result)


class EntityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hass = FakeHass()
        self.hass.bus = EventBus()
        self.registry = self.hass.entity_registry = Registry()
        self.lookup = patch.object(er, "async_entries_for_config_entry", create=True,
            new=lambda registry, entry_id: [e for e in registry.entries.values()
                                           if e.config_entry_id == entry_id])
        self.lookup.start()
        self.entities = {}
        self.pending = []
        self.callbacks = []
        self.entry = NS(entry_id="daybreak-entry", async_on_unload=self.callbacks.append)
        self.hass.config_entries.async_forward_entry_setups.side_effect = self.forward
        self.hass.config_entries.async_unload_platforms.side_effect = self.unload
        await bootstrap.async_setup_entry(self.hass, self.entry)
        self.port = self.entry.runtime_data

    async def asyncTearDown(self):
        await self.flush()
        await bootstrap.async_unload_entry(self.hass, self.entry)
        for cancel in self.callbacks: cancel()
        self.lookup.stop()

    async def forward(self, entry, platforms):
        for platform in platforms:
            def add(entities, platform=platform):
                for entity in entities:
                    key = entity._attr_unique_id
                    entity.hass = self.hass
                    entity.entity_id = f"{platform}.{key.replace(':', '_')}"
                    self.entities[key] = entity
                    self.registry.entries.setdefault(entity.entity_id, NS(
                        entity_id=entity.entity_id, unique_id=key, domain=platform,
                        platform="daybreak_alarm", config_entry_id=entry.entry_id))
                    self.pending.append(entity.async_added_to_hass())
            await PLATFORMS[platform].async_setup_entry(self.hass, entry, add)

    async def unload(self, entry, platforms):
        for entity in self.entities.values():
            for cancel in getattr(entity, "remove_callbacks", []): cancel()
        self.entities.clear()
        return True

    async def flush(self):
        pending, self.pending = self.pending, []
        if pending: await asyncio.gather(*pending)
        for _ in range(3): await asyncio.sleep(0)

    async def save(self, config=None):
        alarm = await self.port.engine.save_alarm(config or {"label": "Weekday"})
        await self.flush()
        return alarm

    def entity(self, alarm, key):
        return self.entities[f'{alarm["id"]}:{key}']

    async def test_each_saved_alarm_creates_five_discoverable_entities(self):
        alarm = await self.save()
        self.assertEqual(len(self.registry.entries), 5)
        self.assertEqual(set(key.split(":")[1] for key in self.entities),
                         {"enabled", "snooze", "dismiss", "status", "next_alarm"})
        for entity in self.entities.values():
            self.assertEqual(entity._attr_device_info["identifiers"], {("daybreak_alarm", self.entry.entry_id)})
            self.assertEqual(entity.extra_state_attributes["alarm_id"], alarm["id"])
            self.assertFalse(entity._attr_should_poll)

    async def test_duplicate_labels_have_distinct_ids_and_renames_keep_ids(self):
        first = await self.save()
        await self.save()
        self.assertEqual(len(self.registry.entries), 10)
        before = set(self.registry.entries)
        renamed = dict(first["config"], label="New label")
        await self.port.engine.save_alarm(renamed, first["id"], first["revision"])
        self.assertEqual(set(self.registry.entries), before)
        self.assertEqual(self.entity(first, "enabled").name, "New label enabled")

    async def test_delete_removes_only_deleted_alarms_registry_entries(self):
        first, second = await self.save(), await self.save()
        unrelated = NS(entity_id="sensor.other", unique_id="old:status", domain="sensor",
                       platform="other", config_entry_id=self.entry.entry_id)
        self.registry.entries[unrelated.entity_id] = unrelated
        await self.port.engine.delete_alarm(first["id"])
        self.assertEqual(len(self.registry.removed), 5)
        self.assertEqual(len(self.registry.entries), 6)
        self.assertIn("sensor.other", self.registry.entries)
        self.assertTrue(self.entity(second, "enabled").available)
        self.assertFalse(self.entity(first, "enabled").available)

    async def test_upgrade_loads_existing_alarms_and_reload_keeps_unique_ids(self):
        alarm = await self.save()
        before_ids = set(self.registry.entries)
        before_config = deepcopy(alarm["config"])
        next_at = alarm["runtime"]["next_at"]
        await bootstrap.async_unload_entry(self.hass, self.entry)
        for cancel in self.callbacks: cancel()
        self.callbacks.clear()
        await bootstrap.async_setup_entry(self.hass, self.entry)
        self.port = self.entry.runtime_data
        await self.flush()
        self.assertEqual(set(self.registry.entries), before_ids)
        self.assertEqual(len(self.entities), 5)
        self.assertEqual(self.port.engine.records[alarm["id"]]["config"], before_config)
        self.assertEqual(self.port.engine.records[alarm["id"]]["runtime"]["next_at"], next_at)
        self.assertEqual(self.hass.extra_modules, {bootstrap.CARD_URL})

    async def test_switch_controls_persistent_alarm_and_updates_sensor(self):
        alarm = await self.save()
        switch = self.entity(alarm, "enabled")
        sensor = self.entity(alarm, "status")
        await switch.async_turn_off()
        self.assertFalse(switch.is_on)
        self.assertEqual(sensor.native_value, "disabled")
        self.assertIsNone(self.entity(alarm, "next_alarm").native_value)
        self.assertFalse(self.hass.storage["daybreak_alarm.alarms"]["alarms"][0]["config"]["enabled"])
        await switch.async_turn_on()
        self.assertTrue(switch.is_on)
        self.assertEqual(sensor.native_value, "idle")
        self.assertGreater(sensor.state_writes, 0)

    async def test_non_admin_entity_control_denied_admin_and_automation_allowed(self):
        alarm = await self.save()
        switch = self.entity(alarm, "enabled")
        switch._context = NS(user_id="ordinary")
        with self.assertRaises(Unauthorized): await switch.async_turn_off()
        self.assertTrue(switch.is_on)
        self.hass.auth.async_get_user.return_value = NS(is_admin=True)
        switch._context = NS(user_id="admin")
        await switch.async_turn_off()
        switch._context = NS(user_id=None)
        await switch.async_turn_on()
        self.assertTrue(switch.is_on)

    async def test_controls_unavailable_until_startup_ready(self):
        alarm = await self.save()
        self.port.ready = False
        switch = self.entity(alarm, "enabled")
        self.assertFalse(switch.available)
        with self.assertRaises(HAError): await switch.async_turn_off()
        self.port.ready = True
        self.port.changed()
        self.assertTrue(switch.available)
        self.assertGreater(switch.state_writes, 0)

    async def test_snooze_dismiss_buttons_and_timestamp_follow_active_alarm(self):
        alarm = await self.save()
        snooze, dismiss = self.entity(alarm, "snooze"), self.entity(alarm, "dismiss")
        self.assertFalse(snooze.available)
        self.assertFalse(dismiss.available)
        await self.port.engine.action(alarm["id"], "test")
        self.assertTrue(snooze.available)
        self.assertTrue(dismiss.available)
        self.assertEqual(self.entity(alarm, "status").native_value, "ringing")
        await snooze.async_press()
        self.assertFalse(snooze.available)
        self.assertTrue(dismiss.available)
        self.assertEqual(self.entity(alarm, "status").native_value, "snoozed")
        runtime = self.port.engine.records[alarm["id"]]["runtime"]
        # A schedule can preempt a snoozed test, so report whichever comes first.
        expected = min(models.utc(runtime["next_at"]), models.utc(runtime["snooze_until"]))
        self.assertEqual(self.entity(alarm, "next_alarm").native_value, expected)
        self.assertIsNotNone(expected.tzinfo)
        await dismiss.async_press()
        self.assertEqual(self.entity(alarm, "status").native_value, "idle")
        self.assertFalse(dismiss.available)

    async def test_disabled_snooze_cannot_be_pressed(self):
        alarm = await self.save({"snooze_enabled": False})
        await self.port.engine.action(alarm["id"], "test")
        self.assertFalse(self.entity(alarm, "snooze").available)
        with self.assertRaises(HAError): await self.entity(alarm, "snooze").async_press()
        self.assertTrue(self.entity(alarm, "dismiss").available)

    async def test_one_time_alarm_auto_disable_does_not_disable_snooze_or_dismiss(self):
        alarm = await self.save()
        self.port.now = lambda: models.utc(alarm["runtime"]["next_at"])
        await self.port.engine.tick()
        self.assertFalse(self.entity(alarm, "enabled").is_on)
        self.assertEqual(self.entity(alarm, "status").native_value, "ringing")
        self.assertTrue(self.entity(alarm, "snooze").available)
        await self.entity(alarm, "snooze").async_press()
        self.assertTrue(self.entity(alarm, "dismiss").available)
        await self.entity(alarm, "dismiss").async_press()
        self.assertEqual(self.entity(alarm, "status").native_value, "disabled")

    async def test_entity_listener_removed_on_platform_unload(self):
        alarm = await self.save()
        entity = self.entity(alarm, "enabled")
        before = getattr(entity, "state_writes", 0)
        await self.unload(self.entry, bootstrap.PLATFORMS)
        self.port.changed()
        self.assertEqual(getattr(entity, "state_writes", 0), before)
