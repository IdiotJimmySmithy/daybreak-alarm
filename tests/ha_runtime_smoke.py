"""Real HA/HTTP/WebSocket lifecycle smoke test; no real devices are contacted.

Run in a separate Python 3.14 environment with requirements-ha-test.txt installed.
The dependency-free unittest suite deliberately uses HA doubles; NEVER import it
into this process. --simulate-network replaces only OS adapter discovery where
restricted containers deny it; device actions below are recorded test services.
"""
import argparse
import asyncio
from contextlib import nullcontext
from datetime import timedelta
import json
import logging
from pathlib import Path
import shutil
import socket
import tempfile
from unittest.mock import AsyncMock, patch

from aiohttp import ClientSession
from homeassistant import loader
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
from homeassistant.bootstrap import async_from_config_dict
from homeassistant.config_entries import ConfigEntryState, SOURCE_USER
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant

ROOT = Path(__file__).resolve().parents[1]


async def main():
    with tempfile.TemporaryDirectory(prefix='daybreak-ha-') as directory:
        shutil.copytree(ROOT/'custom_components', Path(directory)/'custom_components',
                        ignore=shutil.ignore_patterns('__pycache__'))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port_number = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port_number}'
        hass = HomeAssistant(directory)
        loader.async_setup(hass)
        try:
            result = await async_from_config_dict({
                'homeassistant': {'name': 'Daybreak test', 'latitude': 0, 'longitude': 0,
                    'elevation': 0, 'unit_system': 'metric', 'time_zone': 'America/New_York',
                    'internal_url': base},
                'http': {'server_host': '127.0.0.1', 'server_port': port_number},
                'frontend': {},
            }, hass)
            assert result is hass
            await hass.async_start()
            flow = await hass.config_entries.flow.async_init('daybreak_alarm', context={'source': SOURCE_USER})
            assert flow['type'] == 'form'
            flow = await hass.config_entries.flow.async_configure(flow['flow_id'], {})
            assert flow['type'] == 'create_entry'
            await hass.async_block_till_done()
            entry = flow['result']
            assert entry.state is ConfigEntryState.LOADED
            port = hass.data['daybreak_alarm']
            assert port.ready
            duplicate = await hass.config_entries.flow.async_init('daybreak_alarm', context={'source': SOURCE_USER})
            assert duplicate['type'] == 'abort'
            print('PASS: real config flow, setup, startup readiness, duplicate prevention')

            user = await hass.auth.async_create_user('Test admin', group_ids=[GROUP_ID_ADMIN])
            refresh = await hass.auth.async_create_refresh_token(user, client_id="http://localhost/")
            access = hass.auth.async_create_access_token(refresh)
            ordinary = await hass.auth.async_create_user('Test user', group_ids=[GROUP_ID_USER])
            user_refresh = await hass.auth.async_create_refresh_token(ordinary, client_id="http://localhost/")
            user_access = hass.auth.async_create_access_token(user_refresh)
            calls = []
            async def output(call):
                calls.append((call.domain, call.service, dict(call.data)))
            for domain, name in [('media_player', 'play_media'), ('media_player', 'media_stop'),
                                 ('light', 'turn_on'), ('notify', 'mobile_app_test')]:
                hass.services.async_register(domain, name, output)
            hass.states.async_set('media_player.daybreak_test', 'idle', {'friendly_name': 'Test speaker',
                'supported_features': int(MediaPlayerEntityFeature.PLAY_MEDIA | MediaPlayerEntityFeature.STOP)})
            hass.states.async_set('light.daybreak_test', 'off')

            async with ClientSession() as http:
                for filename in ('panel.js', 'card.js', 'sounds/daybreak.wav', 'sounds/soft.wav', 'sounds/pulse.wav'):
                    async with http.get(f'{base}/daybreak_alarm/static/{filename}') as response:
                        assert response.status == 200, (filename, response.status)
                        content = await response.read()
                        assert len(content) > 100
                        if filename.endswith('.wav'):
                            assert content[:4] == b'RIFF'
                print('PASS: real HTTP static panel and all bundled audio files')
                async with http.ws_connect(base+'/api/websocket') as ws:
                    assert (await ws.receive_json())['type'] == 'auth_required'
                    await ws.send_json({'type': 'auth', 'access_token': access})
                    assert (await ws.receive_json())['type'] == 'auth_ok'
                    message_id = 0
                    async def command(kind, **data):
                        nonlocal message_id
                        message_id += 1
                        await ws.send_json({'id': message_id, 'type': kind, **data})
                        result = await asyncio.wait_for(ws.receive_json(), 10)
                        assert result['id'] == message_id
                        return result
                    panels = await command('get_panels')
                    panel = panels['result']['daybreak-alarms']
                    assert panel['require_admin']
                    version = json.loads((ROOT/'custom_components/daybreak_alarm/manifest.json').read_text())['version']
                    assert panel['config']['_panel_custom']['module_url'].endswith(f'/panel.js?v={version}')
                    catalog = await command('daybreak_alarm/get')
                    assert catalog['success']
                    assert 'mobile_app_test' in [n['id'] for n in catalog['result']['catalog']['notifications']]
                    before_test = port.engine.snapshot()['alarms']
                    phone_test = await command('daybreak_alarm/test_notification', notify={
                        'enabled': True, 'targets': ['mobile_app_test'], 'prompt_delivery': True})
                    assert phone_test['success'], phone_test
                    assert phone_test['result']['results'][0]['accepted']
                    assert not phone_test['result']['delivery_confirmed']
                    assert port.engine.snapshot()['alarms'] == before_test
                    assert calls[-1][2]['data']['ttl'] == 0
                    assert calls[-1][2]['data']['priority'] == 'high'
                    calls.clear()
                    saved = await command('daybreak_alarm/save', config={'label': 'Runtime test',
                        'sound': {'enabled': True, 'targets': ['media_player.daybreak_test'], 'loop': False},
                        'lights': {'enabled': True, 'targets': ['light.daybreak_test']},
                        'notify': {'enabled': True, 'targets': ['mobile_app_test']}})
                    assert saved['success'], saved
                    alarm = saved['result']['alarms'][0]
                    alarm_id = alarm['id']
                    edited = await command('daybreak_alarm/save', alarm_id=alarm_id,
                                           revision=alarm['revision'], config=alarm['config'])
                    assert edited['success']
                    extra = await command('daybreak_alarm/save', config={'label': 'Delete me'})
                    extra_id = next(a['id'] for a in extra['result']['alarms'] if a['config']['label'] == 'Delete me')
                    deleted = await command('daybreak_alarm/delete', alarm_id=extra_id)
                    assert deleted['success'] and all(a['id'] != extra_id for a in deleted['result']['alarms'])
                    stale = await command('daybreak_alarm/save', alarm_id=alarm_id, revision=0, config={})
                    assert not stale['success'] and stale['error']['code'] == 'conflict'
                    invalid = await command('daybreak_alarm/action', alarm_id=alarm_id, action='invalid')
                    assert not invalid['success']
                    print('PASS: authenticated WebSocket CRUD, real schema rejection, stale revision protection')

                    async with http.post(base+'/api/services/daybreak_alarm/test',
                            headers={'Authorization': f'Bearer {access}'}, json={'alarm_id': alarm_id}) as response:
                        assert response.status == 200, await response.text()
                    await asyncio.gather(*list(port.engine.jobs.values()))
                    assert port.engine.records[alarm_id]['runtime']['status'] == 'ringing'
                    assert port.engine.records[alarm_id]['runtime']['next_at'] == alarm['runtime']['next_at']
                    assert any(c[:2] == ('media_player', 'play_media') for c in calls)
                    assert any(c[:2] == ('light', 'turn_on') for c in calls)
                    assert any(c[:2] == ('notify', 'mobile_app_test') for c in calls)
                    play = next(c for c in calls if c[:2] == ('media_player', 'play_media'))
                    assert play[2]['media_content_id'] == base+'/daybreak_alarm/static/sounds/daybreak.wav'
                    assert (await command('daybreak_alarm/action', alarm_id=alarm_id, action='dismiss'))['success']
                    assert any(c[:2] == ('media_player', 'media_stop') for c in calls)
                    assert not any(c[2].get('message') == 'clear_notification' for c in calls)
                    print('PASS: real HA service dispatch, device-output calls, media URL, test/dismiss')

                    from custom_components.daybreak_alarm.models import utc
                    clock = utc(alarm['runtime']['next_at'])
                    port.now = lambda: clock
                    await port.engine.tick()
                    await asyncio.gather(*list(port.engine.jobs.values()))
                    assert not port.engine.records[alarm_id]['config']['enabled']
                    assert port.engine.records[alarm_id]['runtime']['status'] == 'ringing'
                    old_token = port.engine.records[alarm_id]['runtime']['token']
                    hass.bus.async_fire('mobile_app_notification_action', {'action': f'DAYBREAK:snooze:{alarm_id}:{old_token}'})
                    await hass.async_block_till_done()
                    assert port.engine.records[alarm_id]['runtime']['status'] == 'snoozed'
                    clock += timedelta(minutes=9)
                    await port.engine.tick()
                    await asyncio.gather(*list(port.engine.jobs.values()))
                    hass.bus.async_fire('mobile_app_notification_action', {'action': f'DAYBREAK:dismiss:{alarm_id}:{old_token}'})
                    await hass.async_block_till_done()
                    assert port.engine.records[alarm_id]['runtime']['status'] == 'ringing'
                    stale_popup = await command('daybreak_alarm/action', alarm_id=alarm_id, action='dismiss', token=old_token)
                    assert stale_popup['success']
                    assert port.engine.records[alarm_id]['runtime']['status'] == 'ringing'
                    assert (await command('daybreak_alarm/action', alarm_id=alarm_id, action='dismiss'))['success']
                    print('PASS: scheduled one-time alarm, auto-disable, notification snooze, stale action rejection')

                async with http.ws_connect(base+'/api/websocket') as ws:
                    await ws.receive_json()
                    await ws.send_json({'type': 'auth', 'access_token': user_access})
                    assert (await ws.receive_json())['type'] == 'auth_ok'
                    await ws.send_json({'id': 1, 'type': 'daybreak_alarm/get'})
                    denied = await ws.receive_json()
                    assert not denied['success'] and denied['error']['code'] == 'unauthorized'
                    await ws.send_json({'id': 2, 'type': 'daybreak_alarm/test_notification',
                                        'notify': {'enabled': True, 'targets': ['mobile_app_test']}})
                    denied = await ws.receive_json()
                    assert not denied['success'] and denied['error']['code'] == 'unauthorized'
                async with http.post(base+'/api/services/daybreak_alarm/test',
                        headers={'Authorization': f'Bearer {user_access}'}, json={'alarm_id': alarm_id}) as response:
                    assert response.status in (401, 403)
                print('PASS: non-admin WebSocket and service denial')

            stored = Path(directory)/'.storage/daybreak_alarm.alarms'
            assert stored.exists()
            await hass.config_entries.async_unload(entry.entry_id)
            assert 'daybreak_alarm' not in hass.data
            await hass.config_entries.async_setup(entry.entry_id)
            assert entry.state is ConfigEntryState.LOADED
            restored = hass.data['daybreak_alarm'].engine.records[alarm_id]
            assert restored['config']['label'] == 'Runtime test'
            assert restored['runtime']['status'] == 'idle'
            assert not restored['config']['enabled']
            await hass.config_entries.async_remove(entry.entry_id)
            assert not stored.exists()
            print('PASS: real storage, unload/reload without duplicate static routes, explicit removal')
            print('Real Home Assistant 2026.10.2 smoke test PASSED.')
        finally:
            await hass.async_stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulate-network', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    adapters = [{'name': 'lo', 'index': 1, 'enabled': True, 'auto': True, 'default': True,
                 'ipv4': [{'address': '127.0.0.1', 'network_prefix': 8}], 'ipv6': []}]
    context = patch('homeassistant.components.network.network.async_load_adapters',
                    AsyncMock(return_value=adapters)) if args.simulate_network else nullcontext()
    with context:
        asyncio.run(main())
