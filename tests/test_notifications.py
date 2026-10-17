"""Regressions for notification timing, diagnostics, and the dashboard API."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest

from support import FakeGateway, FakePort, actions_module, engine_module, models, ringing_record
from test_ha_contract import FakeHass, Connection, api, bootstrap


class NotificationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gateway = FakeGateway()
        self.runner = actions_module.ActionRunner(self.gateway)
        self.record = ringing_record({
            "sound": {"enabled": True, "targets": ["media_player.bedroom"], "loop": False},
            "notify": {"enabled": True, "targets": ["mobile_app_phone"]},
        })

    async def asyncTearDown(self):
        await self.runner.stop(self.record)

    async def test_phone_sends_while_media_resolution_is_still_blocked(self):
        entered, release, sent = asyncio.Event(), asyncio.Event(), asyncio.Event()
        original = self.gateway.call
        async def resolve(*_):
            entered.set()
            await release.wait()
            return "sound", "music"
        async def call(domain, service, data):
            await original(domain, service, data)
            if domain == "notify": sent.set()
        self.gateway.resolve_media, self.gateway.call = resolve, call
        task = asyncio.create_task(self.runner.start(self.record, lambda: True))
        try:
            await asyncio.wait_for(entered.wait(), .5)
            await asyncio.wait_for(sent.wait(), .5)
            self.assertFalse(task.done())
        finally:
            release.set()
            await task

    async def test_slow_phone_does_not_delay_audio(self):
        played, release = asyncio.Event(), asyncio.Event()
        original = self.gateway.call
        async def call(domain, service, data):
            if domain == "notify": await release.wait()
            await original(domain, service, data)
            if service == "play_media": played.set()
        self.gateway.call = call
        task = asyncio.create_task(self.runner.start(self.record, lambda: True))
        try:
            await asyncio.wait_for(played.wait(), .5)
            self.assertFalse(task.done())
        finally:
            release.set()
            await task

    async def test_cancel_joins_notification_lane_before_cleanup(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()
        original = self.gateway.call
        async def call(domain, service, data):
            if domain == "notify" and data.get("message") != "clear_notification":
                entered.set()
                try: await asyncio.Event().wait()
                finally: cancelled.set()
            await original(domain, service, data)
        self.gateway.call = call
        task = asyncio.create_task(self.runner.start(self.record, lambda: True))
        await asyncio.wait_for(entered.wait(), .5)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertTrue(cancelled.is_set())
        await self.runner.stop(self.record)
        self.assertTrue(any(c[1] == "media_stop" for c in self.gateway.calls))
        self.assertFalse(self.runner.sessions)

    async def test_full_test_notification_survives_audio_cleanup(self):
        self.record["runtime"]["test_run"] = True
        await self.runner.start(self.record, lambda: True)
        await self.runner.stop(self.record)
        self.assertFalse(any(c[2].get("message") == "clear_notification" for c in self.gateway.calls))
        self.assertTrue(any(c[1] == "media_stop" for c in self.gateway.calls))

    async def test_real_alarm_notification_still_clears_on_dismiss(self):
        await self.runner.start(self.record, lambda: True)
        await self.runner.stop(self.record)
        notices = [c[2] for c in self.gateway.calls if c[0] == "notify"]
        self.assertEqual(notices[-1]["message"], "clear_notification")
        self.assertEqual(notices[0]["data"]["tag"], notices[-1]["data"]["tag"])

    async def test_phone_only_reports_each_target_and_no_delivery_claim(self):
        c = models.validate_config({"notify": {"enabled": True,
            "targets": ["mobile_app_good", "mobile_app_bad"], "prompt_delivery": True}})
        self.gateway.fail.add(("notify", "mobile_app_bad"))
        result = await self.runner.test_notifications(c)
        self.assertEqual([r["accepted"] for r in result["results"]], [True, False])
        self.assertIn("simulated device error", result["results"][1]["error"])
        self.assertFalse(result["delivery_confirmed"])
        self.assertTrue(all(c[0] == "notify" for c in self.gateway.calls))
        self.assertFalse(self.runner.sessions)
        self.assertEqual(self.gateway.calls[0][2]["data"]["ttl"], 0)
        self.assertEqual(self.gateway.calls[0][2]["data"]["priority"], "high")
        self.assertNotIn("actions", self.gateway.calls[0][2]["data"])

    async def test_prompt_delivery_can_be_disabled(self):
        await self.runner.start(self.record, lambda: True)
        notice = next(c[2] for c in self.gateway.calls if c[0] == "notify")
        self.assertNotIn("priority", notice["data"])
        self.assertNotIn("ttl", notice["data"])

    async def test_saved_v011_alarms_load_with_notification_defaults(self):
        old = deepcopy(self.record)
        old["config"]["notify"].pop("prompt_delivery")
        old["runtime"].update(status="idle", token=None)
        port = FakePort(data={"alarms": [old]})
        engine = engine_module.AlarmEngine(port)
        await engine.initialize()
        self.assertFalse(engine.records[old["id"]]["config"]["notify"]["prompt_delivery"])
        self.assertEqual(engine.records[old["id"]]["runtime"]["next_at"], old["runtime"]["next_at"])
        await engine.close()


class NotificationApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hass = FakeHass()
        self.entry = NS(async_on_unload=lambda _: None)
        await bootstrap.async_setup_entry(self.hass, self.entry)
        self.port = self.hass.data["daybreak_alarm"]
        self.message = {"id": 1, "notify": {"enabled": True, "targets": ["mobile_app_iphone"]}}

    async def asyncTearDown(self):
        await bootstrap.async_unload_entry(self.hass, self.entry)

    async def test_unsaved_phone_test_never_changes_alarm_storage(self):
        before = deepcopy(self.hass.storage)
        connection = Connection()
        await api.ws_test_notification(self.hass, connection, self.message)
        self.assertIsNone(connection.error)
        self.assertTrue(connection.result["results"][0]["accepted"])
        self.assertEqual(self.hass.storage, before)
        self.assertTrue(all(c[0] == "notify" for c in self.hass.services.calls))

    async def test_non_admin_cannot_send_test_notification(self):
        connection = Connection(False)
        await api.ws_test_notification(self.hass, connection, self.message)
        self.assertEqual(connection.error[0], "unauthorized")
        self.assertEqual(self.hass.services.calls, [])

    async def test_disabled_or_empty_or_non_phone_targets_rejected(self):
        for notify in ({"enabled": False}, {"enabled": True, "targets": []},
                       {"enabled": True, "targets": ["persistent_notification"]},
                       {"enabled": True, "targets": ["mobile_app_iphone"], "prompt_delivery": "yes"}):
            connection = Connection()
            await api.ws_test_notification(self.hass, connection, {"id": 1, "notify": notify})
            self.assertEqual(connection.error[0], "invalid_alarm")
        self.assertEqual(self.hass.services.calls, [])

    async def test_startup_blocks_phone_test(self):
        self.port.ready = False
        connection = Connection()
        await api.ws_test_notification(self.hass, connection, self.message)
        self.assertEqual(connection.error[0], "not_ready")

    async def test_old_dashboard_popup_cannot_dismiss_new_ring(self):
        saved = await self.port.engine.save_alarm({})
        await self.port.engine.action(saved["id"], "test")
        old_token = self.port.engine.records[saved["id"]]["runtime"]["token"]
        await self.port.engine.action(saved["id"], "dismiss")
        await self.port.engine.action(saved["id"], "test")
        new_token = self.port.engine.records[saved["id"]]["runtime"]["token"]
        connection = Connection()
        await api.ws_action(self.hass, connection, {"id": 1, "alarm_id": saved["id"], "action": "dismiss", "token": old_token})
        self.assertEqual(self.port.engine.records[saved["id"]]["runtime"]["token"], new_token)
        self.assertEqual(self.port.engine.records[saved["id"]]["runtime"]["status"], "ringing")
