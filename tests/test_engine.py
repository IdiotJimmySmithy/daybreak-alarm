import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
import unittest
from support import FakePort, engine_module, models


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.port=FakePort()
        self.engine=engine_module.AlarmEngine(self.port)
        await self.engine.initialize()

    async def asyncTearDown(self):
        await self.engine.close()

    async def add(self, **config):
        return await self.engine.save_alarm(config)

    async def ring(self, record):
        self.port.clock=models.utc(record["runtime"]["next_at"])
        await self.engine.tick()
        await self.port.settle()
        return self.engine.records[record["id"]]

    async def test_creation_persisted_and_armed(self):
        a=await self.add()
        self.assertEqual(self.port.data["alarms"][0],a)
        self.assertEqual(self.port.due,models.utc(a["runtime"]["next_at"]))

    async def test_one_time_fires_once_and_disables(self):
        a=await self.add()
        fired=await self.ring(a)
        self.assertFalse(fired["config"]["enabled"])
        self.assertEqual(fired["runtime"]["status"],"ringing")
        await self.engine.tick()
        await self.port.settle()
        self.assertEqual(len(self.port.starts),1)

    async def test_persistence_precedes_device_actions(self):
        await self.ring(await self.add())
        _,saved=self.port.starts[0]
        self.assertEqual(saved["alarms"][0]["runtime"]["status"],"ringing")
        self.assertFalse(saved["alarms"][0]["config"]["enabled"])

    async def test_repeat_advances_to_next_selected_day(self):
        a=await self.add(repeat_enabled=True,days=[0,2,4])
        fired=await self.ring(a)
        self.assertEqual(fired["runtime"]["next_at"],"2026-10-19T11:00:00+00:00")

    async def test_snooze_one_time_alarm_even_after_auto_disable(self):
        a=await self.add(snooze_minutes=3)
        await self.ring(a)
        await self.engine.action(a["id"],"snooze")
        r=self.engine.records[a["id"]]["runtime"]
        self.assertEqual(r["status"],"snoozed")
        self.assertEqual(len(self.port.stops),1)
        self.port.clock += timedelta(minutes=3)
        await self.engine.tick(); await self.port.settle()
        self.assertEqual(len(self.port.starts),2)

    async def test_snooze_disabled_rejected(self):
        a=await self.add(snooze_enabled=False)
        await self.ring(a)
        with self.assertRaises(models.InvalidAlarm): await self.engine.action(a["id"],"snooze")

    async def test_dismiss_cancels_snooze(self):
        a=await self.add()
        await self.ring(a)
        await self.engine.action(a["id"],"snooze")
        await self.engine.action(a["id"],"dismiss")
        self.port.clock += timedelta(minutes=20)
        await self.engine.tick(); await self.port.settle()
        self.assertEqual(len(self.port.starts),1)

    async def test_disable_cancels_active_one_time_alarm(self):
        a=await self.add()
        await self.ring(a)
        await self.engine.action(a["id"],"disable")
        self.assertEqual(len(self.port.stops),1)
        self.assertIsNone(self.port.due)

    async def test_skip_repeat(self):
        a=await self.add(repeat_enabled=True,days=[0,1,2,3,4])
        await self.engine.action(a["id"],"skip")
        self.assertEqual(self.engine.records[a["id"]]["runtime"]["next_at"],"2026-10-19T11:00:00+00:00")

    async def test_skip_one_time_disables(self):
        a=await self.add()
        await self.engine.action(a["id"],"skip")
        self.assertFalse(self.engine.records[a["id"]]["config"]["enabled"])

    async def test_skip_can_be_disabled(self):
        a=await self.add(skip_enabled=False)
        with self.assertRaises(models.InvalidAlarm):await self.engine.action(a["id"],"skip")

    async def test_auto_dismiss(self):
        a=await self.add(ring_minutes=1)
        await self.ring(a)
        self.port.clock += timedelta(minutes=1)
        await self.engine.tick()
        self.assertEqual(self.engine.records[a["id"]]["runtime"]["last_result"],"auto-dismissed")
        self.assertEqual(len(self.port.stops),1)

    async def test_auto_dismiss_can_be_disabled(self):
        a=await self.add(auto_dismiss_enabled=False)
        await self.ring(a)
        self.port.clock += timedelta(hours=3)
        await self.engine.tick()
        self.assertEqual(self.engine.records[a["id"]]["runtime"]["status"],"ringing")

    async def test_stale_notification_does_nothing(self):
        a=await self.add()
        await self.ring(a)
        self.assertFalse(await self.engine.action(a["id"],"dismiss",token="old-token"))
        self.assertEqual(self.engine.records[a["id"]]["runtime"]["status"],"ringing")

    async def test_notification_token_is_single_use(self):
        a=await self.add()
        r=await self.ring(a)
        token=r["runtime"]["token"]
        self.assertTrue(await self.engine.action(a["id"],"snooze",token=token))
        self.assertFalse(await self.engine.action(a["id"],"dismiss",token=token))

    async def test_overdue_alarm_marked_missed(self):
        a=await self.add()
        self.port.clock += timedelta(hours=5)
        await self.engine.tick(); await self.port.settle()
        self.assertEqual(len(self.port.starts),0)
        self.assertEqual(self.engine.records[a["id"]]["runtime"]["last_result"],"missed")
        self.assertFalse(self.engine.records[a["id"]]["config"]["enabled"])

    async def test_grace_period_fires_once(self):
        a=await self.add()
        self.port.clock += timedelta(minutes=2)
        await self.engine.tick(); await self.port.settle()
        self.assertEqual(len(self.port.starts),1)

    async def test_restart_preserves_one_time_date(self):
        a=await self.add()
        self.port.clock += timedelta(days=2)
        replacement=engine_module.AlarmEngine(self.port)
        await replacement.initialize()
        self.assertIsNone(replacement.records[a["id"]]["runtime"]["next_at"])
        self.assertEqual(replacement.records[a["id"]]["runtime"]["last_result"],"missed")
        await replacement.close()

    async def test_restart_does_not_replay_ringing(self):
        a=await self.add()
        await self.ring(a)
        replacement=engine_module.AlarmEngine(self.port)
        await replacement.initialize(); await self.port.settle()
        self.assertEqual(len(self.port.starts),1)
        self.assertEqual(replacement.records[a["id"]]["runtime"]["last_result"],"interrupted")
        await replacement.close()

    async def test_restart_restores_snooze(self):
        a=await self.add()
        await self.ring(a)
        await self.engine.action(a["id"],"snooze")
        replacement=engine_module.AlarmEngine(self.port)
        await replacement.initialize()
        self.port.clock += timedelta(minutes=9)
        await replacement.tick(); await self.port.settle()
        self.assertEqual(len(self.port.starts),2)
        await replacement.close()

    async def test_concurrent_edits_conflict(self):
        a=await self.add()
        await self.engine.save_alarm({"label":"A"},a["id"],a["revision"])
        with self.assertRaises(models.Conflict):await self.engine.save_alarm({"label":"B"},a["id"],a["revision"])

    async def test_disk_failure_does_not_change_memory(self):
        a=await self.add()
        before=self.engine.snapshot()
        self.port.fail_save=True
        with self.assertRaises(OSError):await self.engine.action(a["id"],"disable")
        self.assertEqual(before,self.engine.snapshot())

    async def test_disk_failure_prevents_firing(self):
        a=await self.add()
        self.port.clock=models.utc(a["runtime"]["next_at"])
        self.port.fail_save=True
        with self.assertRaises(OSError):await self.engine.tick()
        await self.port.settle()
        self.assertEqual(self.port.starts,[])

    async def test_test_does_not_change_schedule(self):
        a=await self.add(auto_dismiss_enabled=False)
        await self.engine.action(a["id"],"test");await self.port.settle()
        record=self.engine.records[a["id"]]
        self.assertEqual(record["runtime"]["next_at"],a["runtime"]["next_at"])
        self.assertTrue(record["config"]["enabled"])
        self.port.clock += timedelta(seconds=10)
        await self.engine.tick()
        self.assertEqual(len(self.port.stops),1)

    async def test_delete_active_stops_and_removes(self):
        a=await self.add()
        await self.ring(a)
        await self.engine.delete_alarm(a["id"])
        self.assertNotIn(a["id"],self.engine.records)
        self.assertEqual(len(self.port.stops),1)

    async def test_save_label_preserves_one_time_date(self):
        a=await self.add()
        c=deepcopy(a["config"]);c["label"]="Changed"
        new=await self.engine.save_alarm(c,a["id"],a["revision"])
        self.assertEqual(a["runtime"]["next_at"],new["runtime"]["next_at"])

    async def test_save_during_ring_stops_old_output(self):
        a=await self.add()
        current=await self.ring(a)
        await self.engine.save_alarm(current["config"],a["id"],current["revision"])
        self.assertEqual(len(self.port.stops),1)
        self.assertEqual(self.engine.records[a["id"]]["runtime"]["status"],"idle")

    async def test_snapshot_cannot_mutate_engine(self):
        a=await self.add()
        self.engine.snapshot()["alarms"][0]["config"]["time"]="99:99"
        self.assertEqual(self.engine.records[a["id"]]["config"]["time"],"07:00")

    async def test_simultaneous_alarms_both_fire(self):
        await self.add(label="A")
        b=await self.add(label="B")
        await self.ring(b)
        self.assertEqual(len(self.port.starts),2)

    async def test_disable_cancels_pending_output_job(self):
        self.port.block_outputs=asyncio.Event()
        a=await self.add()
        await self.ring(a)
        await self.engine.action(a["id"],"disable")
        self.assertFalse(self.engine.jobs)

    async def test_timezone_change_recalculates_wall_time(self):
        a=await self.add()
        self.port.timezone="UTC"
        await self.engine.timezone_changed()
        self.assertEqual(self.engine.records[a["id"]]["runtime"]["next_at"],"2026-10-17T07:00:00+00:00")

    async def test_corrupt_storage_is_not_overwritten(self):
        port=FakePort(data={"alarms":"broken"})
        engine=engine_module.AlarmEngine(port)
        with self.assertRaises(models.InvalidAlarm):await engine.initialize()
        self.assertEqual(port.data,{"alarms":"broken"})

    async def test_close_cancels_timer(self):
        a=await self.add()
        await self.engine.close()
        self.assertIsNone(self.port.due)
        self.port.clock=models.utc(a["runtime"]["next_at"])
        await self.engine.tick()
        self.assertEqual(self.port.starts,[])

    async def test_closed_engine_rejects_edits(self):
        a=await self.add()
        await self.engine.close()
        with self.assertRaises(models.InvalidAlarm):await self.engine.save_alarm({})
        with self.assertRaises(models.InvalidAlarm):await self.engine.action(a["id"],"enable")
        with self.assertRaises(models.InvalidAlarm):await self.engine.delete_alarm(a["id"])
