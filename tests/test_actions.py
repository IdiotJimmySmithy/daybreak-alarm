import asyncio
from copy import deepcopy
import unittest
from support import FakeGateway, actions_module, player, ringing_record


class ActionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gateway=FakeGateway()
        self.runner=actions_module.ActionRunner(self.gateway)
        self.records=[]

    async def asyncTearDown(self):
        for record in self.records: await self.runner.stop(record)

    async def start(self, raw, token="token1", current=lambda:True):
        record=ringing_record(raw,token=token)
        self.records.append(record)
        errors=await self.runner.start(record,current)
        return record,errors

    def sound(self, **extra):
        return {"sound":{"enabled":True,"targets":["media_player.bedroom"],"loop":False,**extra}}

    async def test_disabled_outputs_make_no_calls(self):
        await self.start({})
        self.assertEqual(self.gateway.calls,[])

    async def test_single_speaker_target_is_exact(self):
        self.gateway.players["media_player.living"]=player("media_player.living",area_id="living")
        _,errors=await self.start(self.sound())
        self.assertEqual(errors,[])
        self.assertEqual([call[2]["entity_id"] for call in self.gateway.calls],["media_player.bedroom"])

    async def test_room_excludes_tv_and_other_rooms(self):
        self.gateway.players.update({"media_player.tv":player("media_player.tv",is_speaker=False),"media_player.kitchen":player("media_player.kitchen",area_id="kitchen")})
        _,errors=await self.start(self.sound(targets=[],areas=["bedroom"]))
        self.assertFalse(errors)
        self.assertEqual([call[2]["entity_id"] for call in self.gateway.calls],["media_player.bedroom"])

    async def test_room_and_explicit_target_deduplicated(self):
        await self.start(self.sound(areas=["bedroom"]))
        self.assertEqual(len(self.gateway.calls),1)

    async def test_unselected_native_group_member_is_blocked(self):
        self.gateway.players["media_player.bedroom"]["group_members"]=["media_player.bedroom","media_player.kitchen"]
        _,errors=await self.start(self.sound())
        self.assertIn("unselected",errors[0])
        self.assertEqual(self.gateway.calls,[])

    async def test_whole_native_group_plays_only_once(self):
        members=["media_player.bedroom","media_player.kitchen"]
        self.gateway.players["media_player.bedroom"]["group_members"]=members
        self.gateway.players["media_player.kitchen"]=player("media_player.kitchen",group_members=members)
        _,errors=await self.start(self.sound(targets=members))
        self.assertFalse(errors)
        self.assertEqual(len(self.gateway.calls),1)

    async def test_helper_group_expands_members(self):
        self.gateway.players["media_player.kitchen"]=player("media_player.kitchen")
        self.gateway.players["media_player.group"]=player("media_player.group",members=["media_player.bedroom","media_player.kitchen"])
        _,errors=await self.start(self.sound(targets=["media_player.group"]))
        self.assertFalse(errors)
        self.assertEqual(len(self.gateway.calls),2)

    async def test_cyclic_group_does_not_recurse_forever(self):
        self.gateway.players["media_player.bedroom"]["members"]=["media_player.bedroom"]
        _,errors=await self.start(self.sound())
        self.assertIn("Cyclic",errors[0])
        self.assertEqual(self.gateway.calls,[])

    async def test_unavailable_speaker_does_not_block_notification(self):
        self.gateway.players["media_player.bedroom"]["state"]="unavailable"
        c=self.sound();c["notify"]={"enabled":True,"targets":["mobile_app_phone"]}
        _,errors=await self.start(c)
        self.assertIn("unavailable",errors[0])
        self.assertEqual(self.gateway.calls[0][0],"notify")

    async def test_playback_failure_does_not_block_lights(self):
        self.gateway.fail.add(("media_player","play_media"))
        c=self.sound();c["lights"]={"enabled":True,"targets":["light.bedroom"]}
        _,errors=await self.start(c)
        self.assertIn("device error",errors[0])
        self.assertEqual(self.gateway.calls[-1][0],"light")

    async def test_unsupported_controls_are_not_called(self):
        self.gateway.players["media_player.bedroom"]["can_volume"]=False
        _,errors=await self.start(self.sound(volume_enabled=True))
        self.assertIn("Volume control unsupported",errors[0])
        self.assertNotIn("volume_set",[call[1] for call in self.gateway.calls])

    async def test_playback_without_stop_or_pause_rejected(self):
        self.gateway.players["media_player.bedroom"].update(can_stop=False,can_pause=False)
        _,errors=await self.start(self.sound())
        self.assertIn("neither Stop nor Pause",errors[0])
        self.assertEqual(self.gateway.calls,[])

    async def test_stop_uses_pause_when_stop_unsupported(self):
        self.gateway.players["media_player.bedroom"]["can_stop"]=False
        record,_=await self.start(self.sound())
        await self.runner.stop(record)
        self.assertEqual(self.gateway.calls[-1][1],"media_pause")

    async def test_volume_set_and_restored(self):
        record,_=await self.start(self.sound(volume_enabled=True,volume=0.5))
        await self.runner.stop(record)
        self.assertEqual(self.gateway.calls[0][2]["volume_level"],0.5)
        self.assertEqual(self.gateway.calls[-1][2]["volume_level"],0.2)

    async def test_restore_volume_can_be_disabled(self):
        record,_=await self.start(self.sound(volume_enabled=True,restore_volume=False))
        await self.runner.stop(record)
        self.assertEqual(len([x for x in self.gateway.calls if x[1]=="volume_set"]),1)

    async def test_native_repeat_restored(self):
        self.gateway.players["media_player.bedroom"]["can_repeat"]=True
        record,_=await self.start(self.sound(loop=True))
        await self.runner.stop(record)
        repeats=[x[2]["repeat"] for x in self.gateway.calls if x[1]=="repeat_set"]
        self.assertEqual(repeats,["one","off"])

    async def test_loop_off_overrides_inherited_native_repeat(self):
        self.gateway.players["media_player.bedroom"].update(can_repeat=True,repeat="one")
        record,_=await self.start(self.sound(loop=False))
        await self.runner.stop(record)
        repeats=[x[2]["repeat"] for x in self.gateway.calls if x[1]=="repeat_set"]
        self.assertEqual(repeats,["off","one"])

    async def test_background_repeat_cancelled_on_stop(self):
        record,_=await self.start(self.sound(loop=True))
        self.assertIn("token1",self.runner.loops)
        await self.runner.stop(record)
        self.assertFalse(self.runner.loops)

    async def test_overlapping_alarm_cannot_steal_or_stop_speaker(self):
        first,_=await self.start(self.sound(),token="first")
        second,errors=await self.start(self.sound(),token="second")
        self.assertIn("already used",errors[0])
        await self.runner.stop(second)
        self.assertNotIn("media_stop",[x[1] for x in self.gateway.calls])
        await self.runner.stop(first)
        self.assertEqual(self.gateway.calls[-1][1],"media_stop")

    async def test_each_output_independently_enabled(self):
        for section,config,expected in [
            ("lights",{"enabled":True,"targets":["light.bedroom"]},("light","turn_on")),
            ("scripts",{"enabled":True,"targets":["script.wake"]},("script","turn_on")),
            ("notify",{"enabled":True,"targets":["mobile_app_phone"]},("notify","mobile_app_phone")),
        ]:
            self.gateway.calls.clear()
            await self.start({section:config},token=section)
            self.assertEqual(self.gateway.calls[0][:2],expected)

    async def test_notifications_have_run_specific_action_tokens(self):
        _,errors=await self.start({"notify":{"enabled":True,"targets":["mobile_app_phone"]}})
        self.assertFalse(errors)
        buttons=self.gateway.calls[0][2]["data"]["actions"]
        self.assertEqual([b["action"] for b in buttons],["DAYBREAK:snooze:alarm1:token1","DAYBREAK:dismiss:alarm1:token1"])

    async def test_notification_actions_can_be_disabled(self):
        await self.start({"notify":{"enabled":True,"targets":["mobile_app_phone"],"actions_enabled":False}})
        self.assertEqual(self.gateway.calls[0][2]["data"]["actions"],[])

    async def test_disabled_snooze_omits_notification_button(self):
        await self.start({"snooze_enabled":False,"notify":{"enabled":True,"targets":["mobile_app_phone"]}})
        buttons=self.gateway.calls[0][2]["data"]["actions"]
        self.assertEqual(len(buttons),1)
        self.assertEqual(buttons[0]["title"],"Dismiss")

    async def test_stale_run_performs_no_actions(self):
        await self.start(self.sound(),current=lambda:False)
        self.assertEqual(self.gateway.calls,[])

    async def test_stop_does_not_undo_lights_or_scripts(self):
        record,_=await self.start({"lights":{"enabled":True,"targets":["light.a"]},"scripts":{"enabled":True,"targets":["script.a"]}})
        before=deepcopy(self.gateway.calls)
        await self.runner.stop(record)
        self.assertEqual(self.gateway.calls,before)

    async def test_notification_tags_differ_between_runs(self):
        c={"notify":{"enabled":True,"targets":["mobile_app_phone"]}}
        await self.start(c,token="old");await self.start(c,token="new")
        tags=[x[2]["data"]["tag"] for x in self.gateway.calls]
        self.assertNotEqual(tags[0],tags[1])

    async def test_cancelled_play_attempt_is_stopped(self):
        entered=asyncio.Event()
        original=self.gateway.call
        async def blocking(domain, action, data):
            await original(domain,action,data)
            if action=="play_media":
                entered.set()
                await asyncio.Event().wait()
        self.gateway.call=blocking
        record=ringing_record(self.sound())
        self.records.append(record)
        task=asyncio.create_task(self.runner.start(record,lambda:True))
        await entered.wait()
        task.cancel();await asyncio.gather(task,return_exceptions=True)
        await self.runner.stop(record)
        self.assertIn("media_stop",[x[1] for x in self.gateway.calls])
