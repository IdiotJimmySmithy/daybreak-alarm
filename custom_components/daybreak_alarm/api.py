"""Authenticated WebSocket API and administrator-only automation actions."""

import logging
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from .const import DOMAIN
from .models import Conflict, InvalidAlarm, validate_config

_LOGGER = logging.getLogger(__name__)
COMMANDS = ("enable", "disable", "snooze", "dismiss", "skip", "test")


async def _dispatch(hass, connection, msg, operation):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Daybreak Alarms currently requires an administrator account")
        return
    port = hass.data.get(DOMAIN)
    if port is None:
        connection.send_error(msg["id"], "not_loaded", "Daybreak Alarms is not loaded")
        return
    if not port.ready:
        connection.send_error(msg["id"], "not_ready", "Home Assistant is still starting. Please try again shortly.")
        return
    try:
        result = await operation(port)
    except Conflict as err:
        connection.send_error(msg["id"], "conflict", str(err))
    except (InvalidAlarm, HomeAssistantError) as err:
        connection.send_error(msg["id"], "invalid_alarm", str(err))
    except Exception:
        _LOGGER.exception("Alarm request failed")
        connection.send_error(msg["id"], "operation_failed", "Could not save or update the alarm. Check Home Assistant logs.")
    else:
        connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get"})
@websocket_api.async_response
async def ws_get(hass, connection, msg):
    async def operation(port):
        return {**port.engine.snapshot(), "catalog": port.catalog()}
    await _dispatch(hass, connection, msg, operation)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/save", vol.Required("config"): dict,
                                 vol.Optional("alarm_id"): str, vol.Optional("revision"): int})
@websocket_api.async_response
async def ws_save(hass, connection, msg):
    async def operation(port):
        saved = await port.engine.save_alarm(msg["config"], msg.get("alarm_id"), msg.get("revision"))
        return {**port.engine.snapshot(), "saved_alarm_id": saved["id"]}
    await _dispatch(hass, connection, msg, operation)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/delete", vol.Required("alarm_id"): str})
@websocket_api.async_response
async def ws_delete(hass, connection, msg):
    async def operation(port):
        await port.engine.delete_alarm(msg["alarm_id"])
        return port.engine.snapshot()
    await _dispatch(hass, connection, msg, operation)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/action", vol.Required("alarm_id"): str,
                                 vol.Required("action"): vol.In(COMMANDS), vol.Optional("token"): str})
@websocket_api.async_response
async def ws_action(hass, connection, msg):
    async def operation(port):
        await port.engine.action(msg["alarm_id"], msg["action"], token=msg.get("token"))
        return port.engine.snapshot()
    await _dispatch(hass, connection, msg, operation)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/test_notification", vol.Required("notify"): dict})
@websocket_api.async_response
async def ws_test_notification(hass, connection, msg):
    async def operation(port):
        config = validate_config({"notify": msg["notify"]})
        if not config["notify"]["enabled"]:
            raise InvalidAlarm("Enable app notifications and select a phone before testing")
        return await port.runner.test_notifications(config)
    await _dispatch(hass, connection, msg, operation)


@callback
def async_register(hass):
    for handler in (ws_get, ws_save, ws_delete, ws_action, ws_test_notification):
        websocket_api.async_register_command(hass, handler)

    async def handle_service(call):
        if user_id := call.context.user_id:
            user = await hass.auth.async_get_user(user_id)
            if user is None or not user.is_admin:
                raise Unauthorized()
        port = hass.data.get(DOMAIN)
        if port is None:
            raise HomeAssistantError("Daybreak Alarms is not loaded")
        if not port.ready:
            raise HomeAssistantError("Daybreak Alarms is still starting")
        try:
            await port.engine.action(call.data["alarm_id"], call.service)
        except (InvalidAlarm, Conflict) as err:
            raise HomeAssistantError(str(err)) from err

    for command in COMMANDS:
        hass.services.async_register(DOMAIN, command, handle_service, schema=vol.Schema({vol.Required("alarm_id"): str}))
