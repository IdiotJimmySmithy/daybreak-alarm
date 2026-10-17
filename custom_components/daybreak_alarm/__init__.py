"""Daybreak Alarms: persistent wake-up alarms with a dedicated sidebar panel."""

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.event import async_track_time_interval

from .api import async_register
from .const import DOMAIN, PANEL_PATH, STATIC_PATH, VERSION
from .engine import AlarmEngine
from .ha import HomeAssistantPort


async def async_setup(hass, config):
    async_register(hass)
    return True


async def async_setup_entry(hass, entry):
    if DOMAIN in hass.data:
        return False
    port = HomeAssistantPort(hass)
    port.engine = AlarmEngine(port)
    static_key = f"{DOMAIN}_static_registered"
    if not hass.data.get(static_key):
        await hass.http.async_register_static_paths([
            StaticPathConfig(STATIC_PATH, str(Path(__file__).parent / "frontend"), False),
        ])
        hass.data[static_key] = True
    await panel_custom.async_register_panel(
        hass, webcomponent_name="daybreak-alarm-panel", frontend_url_path=PANEL_PATH,
        sidebar_title="Alarms", sidebar_icon="mdi:alarm", require_admin=True,
        module_url=f"{STATIC_PATH}/panel.js?v={VERSION}", config={},
    )
    hass.data[DOMAIN] = port
    entry.runtime_data = port
    try:
        # Validate/load storage during setup. Outputs wait until HA has started.
        await port.engine.initialize(run_due=False)
        if hass.is_running:
            port.ready = True
            await port.engine.tick()
        else:
            async def started(_event):
                port.ready = True
                await port._tick()
            entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, started))
        entry.async_on_unload(hass.bus.async_listen("mobile_app_notification_action", port.notification_action))

        async def shutdown(_event):
            await port.engine.close()
        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown))

        async def config_changed(event):
            if port.ready and "time_zone" in event.data:
                await port.engine.timezone_changed()
        entry.async_on_unload(hass.bus.async_listen("core_config_updated", config_changed))

        # Re-check after system clock corrections; normal delivery uses an exact timer.
        from datetime import timedelta
        async def check_clock(_now):
            await port._tick()
        entry.async_on_unload(async_track_time_interval(hass, check_clock, timedelta(seconds=30)))
    except Exception:
        await port.engine.close()
        hass.data.pop(DOMAIN, None)
        frontend.async_remove_panel(hass, PANEL_PATH)
        raise
    return True


async def async_unload_entry(hass, entry):
    port = hass.data.pop(DOMAIN, None)
    if port:
        await port.engine.close()
    frontend.async_remove_panel(hass, PANEL_PATH)
    return True


async def async_remove_entry(hass, entry):
    # Removing the integration explicitly removes its stored alarm collection.
    from homeassistant.helpers.storage import Store
    from .const import STORAGE_KEY
    await Store(hass, 1, STORAGE_KEY).async_remove()
