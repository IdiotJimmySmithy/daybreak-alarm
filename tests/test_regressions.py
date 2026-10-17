"""Regressions discovered during the HACS readiness review."""
import asyncio
from datetime import timedelta
import unittest
from unittest.mock import patch
from support import FakePort, FakeGateway, engine_module, actions_module, models, ringing_record


class SchedulerRegressions(unittest.IsolatedAsyncioTestCase):
    async def test_scheduled_alarm_preempts_test(self):
        port = FakePort()
        engine = engine_module.AlarmEngine(port)
        try:
            await engine.initialize()
            alarm = await engine.save_alarm({})
            port.clock = models.utc(alarm['runtime']['next_at']) - timedelta(seconds=5)
            await engine.action(alarm['id'], 'test')
            await port.settle()
            test_token = engine.records[alarm['id']]['runtime']['token']
            port.clock += timedelta(seconds=5)
            await engine.tick()
            await port.settle()
            self.assertEqual(len(port.starts), 2)
            runtime = engine.records[alarm['id']]['runtime']
            self.assertEqual(runtime['last_result'], 'fired')
            self.assertNotEqual(runtime['token'], test_token)
            self.assertEqual(port.stops[0]['runtime']['token'], test_token)
            self.assertEqual(models.utc(runtime['end_at']), port.clock + timedelta(minutes=5))
        finally:
            await engine.close()

    async def test_scheduled_alarm_preempts_snoozed_test(self):
        port = FakePort()
        engine = engine_module.AlarmEngine(port)
        try:
            await engine.initialize()
            alarm = await engine.save_alarm({})
            await engine.action(alarm['id'], 'test')
            await port.settle()
            await engine.action(alarm['id'], 'snooze')
            port.clock = models.utc(alarm['runtime']['next_at'])
            await engine.tick()
            await port.settle()
            runtime = engine.records[alarm['id']]['runtime']
            self.assertEqual(runtime['last_result'], 'fired')
            self.assertIsNone(runtime['snooze_until'])
            self.assertFalse(runtime['test_run'])
            self.assertEqual(len(port.starts), 2)
        finally:
            await engine.close()

    async def test_tick_queued_behind_close_does_not_change_storage(self):
        port = FakePort()
        engine = engine_module.AlarmEngine(port)
        await engine.initialize()
        alarm = await engine.save_alarm({})
        port.clock = models.utc(alarm['runtime']['next_at'])
        await engine.lock.acquire()
        close = asyncio.create_task(engine.close())
        tick = asyncio.create_task(engine.tick())
        await asyncio.sleep(0)
        saves = len(port.saves)
        engine.lock.release()
        await asyncio.gather(close, tick)
        self.assertEqual(len(port.saves), saves)
        self.assertTrue(engine.records[alarm['id']]['config']['enabled'])


class OutputRegressions(unittest.IsolatedAsyncioTestCase):
    async def test_media_resolution_timeout_still_sends_notification(self):
        gateway = FakeGateway()
        async def hung_resolver(*_):
            await asyncio.Event().wait()
        gateway.resolve_media = hung_resolver
        runner = actions_module.ActionRunner(gateway)
        record = ringing_record({'sound': {'enabled': True, 'targets': ['media_player.bedroom']},
                                 'notify': {'enabled': True, 'targets': ['mobile_app_phone']}})
        # Use a real timeout with a short deadline, keeping the test quick.
        real_timeout = asyncio.timeout
        try:
            with patch.object(actions_module.asyncio, 'timeout', side_effect=lambda _: real_timeout(.02)):
                errors = await asyncio.wait_for(runner.start(record, lambda: True), .2)
            self.assertTrue(errors)
            self.assertTrue(any(call[0] == 'notify' for call in gateway.calls))
        finally:
            await runner.stop(record)

    async def test_concurrent_cleanup_does_not_restore_over_new_run(self):
        gateway = FakeGateway()
        runner = actions_module.ActionRunner(gateway)
        record = ringing_record({'sound': {'enabled': True, 'targets': ['media_player.bedroom'], 'loop': False}})
        await runner.start(record, lambda: True)
        first_stop = asyncio.Event()
        release = asyncio.Event()
        original = gateway.call
        async def blocked_call(domain, action, data):
            if action == 'media_stop':
                first_stop.set()
                await release.wait()
            await original(domain, action, data)
        gateway.call = blocked_call
        task1 = asyncio.create_task(runner.stop(record))
        await first_stop.wait()
        task2 = asyncio.create_task(runner.stop(record))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(task1, task2)
        self.assertEqual(sum(c[1] == 'media_stop' for c in gateway.calls), 1)
        self.assertFalse(runner.sessions)
        self.assertFalse(runner.owners)
