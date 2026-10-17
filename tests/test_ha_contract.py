"""Adapter contract tests with explicit HA doubles, NOT a real HA runtime."""

from dataclasses import dataclass
from datetime import datetime, UTC
from enum import IntFlag, StrEnum
import importlib
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
import sys
import unittest
from unittest.mock import AsyncMock

from support import PACKAGE, ROOT, models, ringing_record


def module(name, **members):
    mod=ModuleType(name);mod.__dict__.update(members);mod.__path__=[];sys.modules[name]=mod
    return mod


class Features(IntFlag):
    PAUSE=1
    VOLUME_SET=4
    PLAY_MEDIA=512
    STOP=4096
    REPEAT_SET=262144


class HAError(Exception): pass
class Unauthorized(HAError): pass


class Platform(StrEnum):
    SWITCH = "switch"
    BUTTON = "button"
    SENSOR = "sensor"


class Entity:
    _context = None
    async def async_added_to_hass(self): pass
    def async_on_remove(self, callback):
        if not hasattr(self, "remove_callbacks"): self.remove_callbacks = []
        self.remove_callbacks.append(callback)
    def async_write_ha_state(self):
        self.state_writes = getattr(self, "state_writes", 0) + 1


class Store:
    def __init__(self,hass,version,key):self.hass=hass;self.key=key
    async def async_load(self):return self.hass.storage.get(self.key)
    async def async_save(self,data):self.hass.storage[self.key]=data
    async def async_remove(self):self.hass.storage.pop(self.key,None)


@dataclass
class StaticPathConfig:
    url_path:str
    path:str
    cache_headers:bool


class ConfigFlow:
    def __init_subclass__(cls,domain=None):cls.domain=domain
    async def async_set_unique_id(self,value):self.unique_id=value
    def _abort_if_unique_id_configured(self):pass
    def async_show_form(self,**kwargs):return {"type":"form",**kwargs}
    def async_create_entry(self,**kwargs):return {"type":"create_entry",**kwargs}


def cancelable(hass, kind, value, cb):
    item={"kind":kind,"value":value,"cb":cb,"cancelled":False};hass.timers.append(item)
    def cancel():item["cancelled"]=True
    return cancel


module("voluptuous",Required=lambda key,**_:key,Optional=lambda key,**_:key,Schema=lambda x:x,In=lambda x:x)
module("homeassistant")
module("homeassistant.components")
module("homeassistant.helpers")
module("homeassistant.util")
module("homeassistant.util.dt",utcnow=lambda:datetime(2026,10,16,10,59,tzinfo=UTC))
module("homeassistant.const",EVENT_HOMEASSISTANT_STARTED="homeassistant_started",EVENT_HOMEASSISTANT_STOP="homeassistant_stop",Platform=Platform)
module("homeassistant.core",callback=lambda f:f)
module("homeassistant.config_entries",ConfigFlow=ConfigFlow)
module("homeassistant.exceptions",HomeAssistantError=HAError,Unauthorized=Unauthorized)
module("homeassistant.components.media_player",MediaPlayerEntityFeature=Features)
module("homeassistant.helpers.entity",Entity=Entity)
module("homeassistant.components.switch",SwitchEntity=type("SwitchEntity", (Entity,), {}))
module("homeassistant.components.button",ButtonEntity=type("ButtonEntity", (Entity,), {}))
module("homeassistant.components.sensor",SensorEntity=type("SensorEntity", (Entity,), {}),
       SensorDeviceClass=NS(ENUM="enum", TIMESTAMP="timestamp"))
module("homeassistant.components.http",StaticPathConfig=StaticPathConfig)
module("homeassistant.components.media_source",async_resolve_media=AsyncMock(return_value=NS(url="https://audio.test/a.mp3",mime_type="audio/mpeg")))
module("homeassistant.helpers.storage",Store=Store)
module("homeassistant.helpers.network",get_url=lambda hass,**kwargs:"http://homeassistant.local:8123")
module("homeassistant.helpers.event",async_track_point_in_utc_time=lambda hass,cb,when:cancelable(hass,"point",when,cb),async_track_time_interval=lambda hass,cb,delta:cancelable(hass,"interval",delta,cb))
for registry in ("area","device","entity"):
    module(f"homeassistant.helpers.{registry}_registry",async_get=lambda hass,r=registry:getattr(hass,r+"_registry"))
module("homeassistant.components.websocket_api",websocket_command=lambda schema:lambda f:f,async_response=lambda f:f,async_register_command=lambda hass,handler:hass.ws.append(handler))


async def register_panel(hass,**kwargs):hass.panels[kwargs["frontend_url_path"]]=kwargs
module("homeassistant.components.panel_custom",async_register_panel=register_panel)
module("homeassistant.components.frontend",async_remove_panel=lambda hass,path:hass.panels.pop(path,None),
       add_extra_js_url=lambda hass,url:hass.extra_modules.add(url),
       remove_extra_js_url=lambda hass,url:hass.extra_modules.remove(url))

ha=importlib.import_module(f"{PACKAGE}.ha")
api=importlib.import_module(f"{PACKAGE}.api")
flow=importlib.import_module(f"{PACKAGE}.config_flow")
spec=importlib.util.spec_from_file_location(f"{PACKAGE}.bootstrap",ROOT/"custom_components/daybreak_alarm/__init__.py")
bootstrap=importlib.util.module_from_spec(spec)
bootstrap.__package__=PACKAGE
spec.loader.exec_module(bootstrap)


class FakeBus:
    def __init__(self):self.listeners={};self.events=[]
    def async_fire(self,name,data=None):self.events.append((name,data))
    def async_listen(self,name,callback):
        self.listeners.setdefault(name,[]).append(callback)
        return lambda:self.listeners[name].remove(callback)
    def async_listen_once(self,name,callback):return self.async_listen(name,callback)


class FakeServices:
    def __init__(self):self.registered={};self.calls=[]
    def async_services(self):return {"notify":{"mobile_app_iphone":{},"persistent_notification":{}}}
    def has_service(self,domain,service):return service != "nonexistent"
    def async_register(self,domain,service,handler,schema):self.registered[service]=handler
    async def async_call(self,domain,service,data,blocking):self.calls.append((domain,service,data,blocking))


class FakeHass:
    def __init__(self,running=True):
        self.data={};self.storage={};self.timers=[];self.panels={};self.ws=[]
        self.extra_modules=set()
        self.config_entries=NS(async_forward_entry_setups=AsyncMock(),
                               async_unload_platforms=AsyncMock(return_value=True))
        self.config=NS(time_zone="America/New_York");self.is_running=running
        self.http=NS(async_register_static_paths=AsyncMock());self.bus=FakeBus();self.services=FakeServices()
        self.auth=NS(async_get_user=AsyncMock(return_value=NS(is_admin=False)))
        state=NS(entity_id="media_player.bedroom",name="Bedroom",state="idle",attributes={"supported_features":int(Features.PLAY_MEDIA|Features.STOP|Features.VOLUME_SET),"device_class":"speaker","volume_level":.3})
        self.states=NS(async_all=lambda:[state],get=lambda entity_id:state if entity_id==state.entity_id else None)
        self.entity_registry=NS(async_get=lambda _:NS(device_id="d1",area_id=None))
        self.device_registry=NS(async_get=lambda _:NS(area_id="bedroom"))
        self.area_registry=NS(async_list_areas=lambda:[NS(id="bedroom",name="Bedroom")])
    def async_create_task(self,coro):
        import asyncio
        return asyncio.create_task(coro)


class Connection:
    def __init__(self,admin=True):self.user=NS(is_admin=admin);self.result=None;self.error=None
    def send_result(self,id,result):self.result=result
    def send_error(self,id,code,message):self.error=(code,message)


class ContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hass=FakeHass()
        self.callbacks=[]
        self.entry=NS(async_on_unload=self.callbacks.append)
        await bootstrap.async_setup(self.hass,{})
        await bootstrap.async_setup_entry(self.hass,self.entry)
        self.port=self.hass.data["daybreak_alarm"]

    async def asyncTearDown(self):
        await bootstrap.async_unload_entry(self.hass,self.entry)

    async def test_setup_registers_panel_static_path_and_services(self):
        self.assertEqual(len(self.hass.ws),5)
        self.assertEqual(set(self.hass.services.registered),set(api.COMMANDS))
        panel=self.hass.panels["daybreak-alarms"]
        self.assertTrue(panel["require_admin"])
        self.assertEqual(panel["webcomponent_name"],"daybreak-alarm-panel")
        static=self.hass.http.async_register_static_paths.call_args.args[0][0]
        self.assertEqual(static.url_path,"/daybreak_alarm/static")
        self.assertTrue(Path(static.path,"panel.js").exists())
        self.assertEqual(self.hass.extra_modules, {bootstrap.CARD_URL})
        self.hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(self.entry, bootstrap.PLATFORMS)

    async def test_failed_platform_unload_preserves_scheduler_and_card(self):
        self.hass.config_entries.async_unload_platforms.return_value = False
        self.assertFalse(await bootstrap.async_unload_entry(self.hass, self.entry))
        self.assertIs(self.hass.data["daybreak_alarm"], self.port)
        self.assertTrue(self.port.ready)
        self.assertIn(bootstrap.CARD_URL, self.hass.extra_modules)
        self.hass.config_entries.async_unload_platforms.return_value = True

    async def test_failed_platform_setup_cleans_up_and_can_retry(self):
        hass = FakeHass()
        entry = NS(async_on_unload=lambda _: None)
        hass.config_entries.async_forward_entry_setups.side_effect = RuntimeError("platform failed")
        with self.assertRaisesRegex(RuntimeError, "platform failed"):
            await bootstrap.async_setup_entry(hass, entry)
        self.assertNotIn("daybreak_alarm", hass.data)
        self.assertFalse(hass.panels)
        self.assertFalse(hass.extra_modules)
        hass.config_entries.async_unload_platforms.assert_awaited_once()
        hass.config_entries.async_forward_entry_setups.side_effect = None
        await bootstrap.async_setup_entry(hass, entry)
        self.assertEqual(hass.extra_modules, {bootstrap.CARD_URL})
        await bootstrap.async_unload_entry(hass, entry)
        self.assertFalse(hass.extra_modules)

    async def test_websocket_denies_non_admin(self):
        connection=Connection(False)
        await api.ws_save(self.hass,connection,{"id":1,"config":{}})
        self.assertEqual(connection.error[0],"unauthorized")
        self.assertFalse(self.port.engine.records)

    async def test_websocket_create_get_action_delete_roundtrip(self):
        conn=Connection()
        await api.ws_save(self.hass,conn,{"id":1,"config":{"label":"Wake"}})
        alarm_id=conn.result["alarms"][0]["id"]
        await api.ws_get(self.hass,conn,{"id":2})
        self.assertIn("catalog",conn.result)
        await api.ws_action(self.hass,conn,{"id":3,"alarm_id":alarm_id,"action":"disable"})
        self.assertFalse(conn.result["alarms"][0]["config"]["enabled"])
        await api.ws_delete(self.hass,conn,{"id":4,"alarm_id":alarm_id})
        self.assertEqual(conn.result["alarms"],[])

    async def test_websocket_validation_error_is_returned(self):
        conn=Connection()
        await api.ws_save(self.hass,conn,{"id":1,"config":{"time":"25:00"}})
        self.assertEqual(conn.error[0],"invalid_alarm")

    async def test_websocket_stale_edit_conflict_is_returned(self):
        a=await self.port.engine.save_alarm({})
        conn=Connection()
        await api.ws_save(self.hass,conn,{"id":1,"config":{},"alarm_id":a["id"],"revision":0})
        self.assertEqual(conn.error[0],"conflict")

    async def test_catalog_inherits_device_area_and_lists_only_mobile_notify(self):
        catalog=self.port.catalog()
        self.assertEqual(catalog["speakers"][0]["area_id"],"bedroom")
        self.assertTrue(catalog["speakers"][0]["can_play"])
        self.assertEqual([n["id"] for n in catalog["notifications"]],["mobile_app_iphone"])

    async def test_builtin_audio_is_an_absolute_reachable_url(self):
        media,mime=await self.port.resolve_media("builtin:daybreak","music")
        self.assertEqual(media,"http://homeassistant.local:8123/daybreak_alarm/static/sounds/daybreak.wav")
        self.assertEqual(mime,"audio/wav")

    async def test_unknown_builtin_sound_rejected(self):
        with self.assertRaises(ValueError):await self.port.resolve_media("builtin:../../secret","music")

    async def test_custom_media_identifier_preserved(self):
        self.assertEqual(await self.port.resolve_media("spotify:playlist:example","music"),("spotify:playlist:example","music"))

    async def test_media_source_is_resolved(self):
        self.assertEqual(await self.port.resolve_media("media-source://media_source/local/chime.mp3","music"),("https://audio.test/a.mp3","audio/mpeg"))

    async def test_native_service_denies_non_admin(self):
        call=NS(context=NS(user_id="nonadmin"),data={"alarm_id":"x"},service="dismiss")
        with self.assertRaises(Unauthorized):await self.hass.services.registered["dismiss"](call)

    async def test_system_automation_service_allowed(self):
        a=await self.port.engine.save_alarm({})
        call=NS(context=NS(user_id=None),data={"alarm_id":a["id"]},service="disable")
        await self.hass.services.registered["disable"](call)
        self.assertFalse(self.port.engine.records[a["id"]]["config"]["enabled"])

    async def test_notification_action_token_forwarded(self):
        r=ringing_record({"notify":{"enabled":True,"targets":["mobile_app_iphone"]}})
        self.port.engine.records[r["id"]]=r
        self.port.engine.action=AsyncMock()
        await self.port.notification_action(NS(data={"action":"DAYBREAK:dismiss:alarm1:token1"}))
        self.port.engine.action.assert_awaited_once_with("alarm1","dismiss",token="token1")

    async def test_disabled_notification_controls_ignore_button(self):
        r=ringing_record({"notify":{"enabled":True,"targets":["mobile_app_iphone"],"actions_enabled":False}})
        self.port.engine.records[r["id"]]=r
        self.port.engine.action=AsyncMock()
        await self.port.notification_action(NS(data={"action":"DAYBREAK:dismiss:alarm1:token1"}))
        self.port.engine.action.assert_not_awaited()

    async def test_unload_then_reload_does_not_register_static_twice(self):
        await bootstrap.async_unload_entry(self.hass,self.entry)
        for callback in self.callbacks:callback()
        self.callbacks.clear()
        await bootstrap.async_setup_entry(self.hass,self.entry)
        self.hass.http.async_register_static_paths.assert_awaited_once()

    async def test_boot_defers_actions_and_disallows_early_edits(self):
        hass=FakeHass(running=False)
        callbacks=[];entry=NS(async_on_unload=callbacks.append)
        await bootstrap.async_setup_entry(hass,entry)
        port=hass.data["daybreak_alarm"]
        self.assertFalse(port.ready)
        conn=Connection()
        await api.ws_save(hass,conn,{"id":1,"config":{}})
        self.assertEqual(conn.error[0],"not_ready")
        self.assertFalse(port.engine.records)
        for cb in hass.bus.listeners["homeassistant_started"]:await cb(NS(data={}))
        self.assertTrue(port.ready)
        await bootstrap.async_unload_entry(hass,entry)

    async def test_corrupt_storage_aborts_setup_without_overwrite(self):
        hass=FakeHass(running=False)
        hass.storage["daybreak_alarm.alarms"]={"alarms":"broken"}
        with self.assertRaises(models.InvalidAlarm):await bootstrap.async_setup_entry(hass,NS(async_on_unload=lambda _:None))
        self.assertNotIn("daybreak_alarm",hass.data)
        self.assertNotIn("daybreak-alarms",hass.panels)
        self.assertEqual(hass.storage["daybreak_alarm.alarms"],{"alarms":"broken"})

    async def test_config_flow_form_and_creation(self):
        config_flow=flow.DaybreakConfigFlow()
        self.assertEqual((await config_flow.async_step_user())["type"],"form")
        result=await config_flow.async_step_user({})
        self.assertEqual(result["type"],"create_entry")
        self.assertEqual(result["title"],"Daybreak Alarms")
