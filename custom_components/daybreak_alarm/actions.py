"""Capability-aware output routing with bounded, independent device calls."""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

_LOGGER = logging.getLogger(__name__)


class ActionRunner:
    """The gateway supplies catalog, player, call, and media URL resolution."""

    def __init__(self, gateway):
        self.gateway = gateway
        self.sessions = {}
        self.owners = {}
        self.loops = {}
        self.cleanups = {}

    async def _call(self, errors, domain, action, data):
        try:
            async with asyncio.timeout(8):
                await self.gateway.call(domain, action, data)
            return True
        except asyncio.CancelledError:
            raise
        except Exception as err:
            errors.append(f"{domain}.{action}: {err}")
            return False

    def resolve_speakers(self, sound):
        catalog = self.gateway.catalog()
        explicit = set(sound["targets"])
        selected = set(explicit)
        for speaker in catalog["speakers"]:
            if speaker.get("area_id") in sound["areas"] and speaker.get("is_speaker"):
                selected.add(speaker["id"])
        errors = []

        def expand(entity_id, trail):
            if entity_id in trail:
                errors.append(f"Cyclic speaker group: {entity_id}")
                return set()
            state = self.gateway.player(entity_id)
            if state and state.get("members"):
                result = set()
                for member in state["members"]:
                    result.update(expand(member, trail | {entity_id}))
                return result
            return {entity_id}

        leaves = set()
        for entity_id in sorted(selected):
            leaves.update(expand(entity_id, set()))
        groups, processed = [], set()
        for entity_id in sorted(leaves):
            if entity_id in processed:
                continue
            state = self.gateway.player(entity_id)
            if not state or state["state"] in ("unavailable", "unknown"):
                errors.append(f"Speaker unavailable: {entity_id}")
                continue
            members = set(state.get("group_members") or [entity_id]) | {entity_id}
            if members - leaves:
                errors.append(f"{entity_id} is grouped with unselected speakers. Select the whole group or ungroup it first.")
                continue
            leader = (state.get("group_members") or [entity_id])[0]
            leader_state = self.gateway.player(leader)
            if not leader_state or not leader_state.get("can_play"):
                errors.append(f"Playback unsupported: {leader}")
                continue
            # Stopping is essential to snooze/dismiss an alarm predictably.
            if not leader_state.get("can_stop") and not leader_state.get("can_pause"):
                errors.append(f"{leader} exposes neither Stop nor Pause; use a script for this device.")
                continue
            groups.append((leader, members))
            processed.update(members)
        if not groups and not errors:
            errors.append("No speakers found in the selected rooms or targets")
        return groups, errors

    async def start(self, record, current):
        token = record["runtime"]["token"]
        session = self.sessions[token] = {
            "speakers": {}, "claims": set(), "notify": [],
            # APNs collapse IDs are limited to 64 UTF-8 bytes. The ring UUID is
            # already unique: including the alarm UUID made this 74 bytes.
            "tag": f"daybreak_{token}",
            # A ten-second test must remain visible long enough to check a phone.
            "clear_notifications": not record["runtime"].get("test_run", False),
        }
        # Neither slow media resolution nor a phone service may delay the other.
        # TaskGroup also cancels and joins both lanes before engine cleanup.
        async with asyncio.TaskGroup() as group:
            devices = group.create_task(self._start_devices(record, current, session))
            phones = group.create_task(self._start_notifications(record, current, session))
        return devices.result() + phones.result()

    async def _start_devices(self, record, current, session):
        c = record["config"]
        token = record["runtime"]["token"]
        errors = []
        sound = c["sound"]
        if sound["enabled"]:
            groups, resolve_errors = self.resolve_speakers(sound)
            errors.extend(resolve_errors)
            try:
                async with asyncio.timeout(8):
                    media_id, media_type = await self.gateway.resolve_media(sound["media_id"], sound["media_type"])
            except TimeoutError:
                errors.append("Sound: media resolution timed out")
                groups = []
            except Exception as err:
                errors.append(f"Sound: {err}")
                groups = []
            for leader, members in groups:
                if not current():
                    return errors
                if any(member in self.owners for member in members):
                    errors.append(f"{leader} is already used by another ringing alarm")
                    continue
                for member in members:
                    self.owners[member] = token
                session["claims"].update(members)
                state = self.gateway.player(leader)
                session["speakers"][leader] = {
                    "volume": state.get("volume"), "volume_changed": False,
                    "repeat": state.get("repeat"), "repeat_changed": False,
                    "played": False, "play_attempted": False, "can_stop": state["can_stop"],
                    "media_id": media_id, "media_type": media_type,
                }
                saved = session["speakers"][leader]
                if sound["volume_enabled"]:
                    if state.get("can_volume"):
                        saved["volume_changed"] = True
                        await self._call(errors, "media_player", "volume_set", {"entity_id": leader, "volume_level": sound["volume"]})
                    else:
                        errors.append(f"Volume control unsupported: {leader}; using its current volume")
                if not current():
                    return errors
                # A cancelled or timed-out call may already have reached the device.
                saved["play_attempted"] = True
                saved["played"] = await self._call(errors, "media_player", "play_media", {"entity_id": leader, "media_content_id": media_id, "media_content_type": media_type})
                if saved["played"] and state.get("can_repeat") and state.get("repeat") is not None:
                    saved["repeat_changed"] = True
                    if not await self._call(errors, "media_player", "repeat_set", {"entity_id": leader, "repeat": "one" if sound["loop"] else "off"}):
                        # Keep cleanup responsibility, but use software looping.
                        saved["repeat_fallback"] = True
        if c["lights"]["enabled"]:
            for target in c["lights"]["targets"]:
                if not current():
                    return errors
                data = {"entity_id": target}
                if c["lights"]["brightness_enabled"]:
                    data["brightness_pct"] = c["lights"]["brightness"]
                await self._call(errors, "light", "turn_on", data)
        if c["scripts"]["enabled"]:
            for target in c["scripts"]["targets"]:
                if not current():
                    return errors
                await self._call(errors, "script", "turn_on", {"entity_id": target})
        if sound["enabled"] and sound["loop"] and any(v["played"] and (not v["repeat_changed"] or v.get("repeat_fallback")) for v in session["speakers"].values()) and current():
            self.loops[token] = asyncio.create_task(self._loop(token, current, sound["media_id"].startswith("builtin:")))
        return errors

    async def _start_notifications(self, record, current, session):
        c, token = record["config"], record["runtime"]["token"]
        errors = []
        if c["notify"]["enabled"]:
            buttons = []
            if c["notify"]["actions_enabled"]:
                if c["snooze_enabled"]:
                    buttons.append({"action": f"DAYBREAK:snooze:{record['id']}:{token}", "title": f"Snooze {c['snooze_minutes']} min"})
                buttons.append({"action": f"DAYBREAK:dismiss:{record['id']}:{token}", "title": "Dismiss"})
            for service in c["notify"]["targets"]:
                if not current():
                    return errors
                data = {"title": c["label"], "message": f"Your {c['time']} alarm is ringing.", "data": {
                    "tag": session["tag"], "url": "/daybreak-alarms", "clickAction": "/daybreak-alarms", "actions": buttons,
                }}
                if record["runtime"].get("test_run"):
                    data["message"] = "Test alarm. Audio stops after 10 seconds; this notification stays until you clear it. Controls work only while the test is active."
                if c["notify"].get("prompt_delivery"):
                    data["data"].update(priority="high", ttl=0)
                session["notify"].append(service)
                await self._call(errors, "notify", service, data)
        return errors

    async def test_notifications(self, config):
        """Test only selected phone services; do not save or start an alarm."""
        results = []
        tag = f"daybreak_phone_test_{uuid4().hex}"
        for service in config["notify"]["targets"]:
            errors = []
            data = {"title": "Daybreak · notification test",
                    "message": "Your Home Assistant notification test arrived. No alarm or other device was started.",
                    "data": {"tag": tag, "url": "/daybreak-alarms", "clickAction": "/daybreak-alarms"}}
            if config["notify"].get("prompt_delivery"):
                data["data"].update(priority="high", ttl=0)
            ok = await self._call(errors, "notify", service, data)
            results.append({"target": service, "accepted": ok, "error": "; ".join(errors)})
        return {"results": results, "delivery_confirmed": False}

    async def _loop(self, token, current, builtin):
        try:
            while current():
                await asyncio.sleep(8 if builtin else 3)
                for entity_id, info in list(self.sessions.get(token, {}).get("speakers", {}).items()):
                    if not current() or self.owners.get(entity_id) != token:
                        return
                    if not info["played"] or (info["repeat_changed"] and not info.get("repeat_fallback")):
                        continue
                    state = self.gateway.player(entity_id)
                    if state and (builtin or state["state"] == "idle"):
                        errors = []
                        await self._call(errors, "media_player", "play_media", {"entity_id": entity_id, "media_content_id": info["media_id"], "media_content_type": info["media_type"]})
                        for error in errors:
                            _LOGGER.warning("Alarm repeat: %s", error)
        except asyncio.CancelledError:
            raise

    async def stop(self, record):
        token = record["runtime"].get("token")
        if not token:
            return
        # Dismiss, unload and shutdown can overlap. Keep one cleanup per run,
        # and keep its speaker claims until ALL stop/restore calls have ended.
        task = self.cleanups.get(token)
        if task is None:
            task = asyncio.create_task(self._stop(record))
            self.cleanups[token] = task
            task.add_done_callback(lambda _: self.cleanups.pop(token, None))
        await asyncio.shield(task)

    async def _stop(self, record):
        token = record["runtime"].get("token")
        task = self.loops.pop(token, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        session = self.sessions.get(token)
        if not session:
            return
        errors = []
        for entity_id, info in session["speakers"].items():
            if self.owners.get(entity_id) != token:
                continue
            if info["play_attempted"]:
                await self._call(errors, "media_player", "media_stop" if info["can_stop"] else "media_pause", {"entity_id": entity_id})
            if info["repeat_changed"]:
                await self._call(errors, "media_player", "repeat_set", {"entity_id": entity_id, "repeat": info["repeat"]})
            if info["volume_changed"] and record["config"]["sound"]["restore_volume"] and info["volume"] is not None:
                await self._call(errors, "media_player", "volume_set", {"entity_id": entity_id, "volume_level": info["volume"]})
        for service in session["notify"] if session["clear_notifications"] else []:
            await self._call(errors, "notify", service, {"message": "clear_notification", "data": {"tag": session["tag"]}})
        for entity_id in session["claims"]:
            if self.owners.get(entity_id) == token:
                self.owners.pop(entity_id, None)
        self.sessions.pop(token, None)
        for error in errors:
            _LOGGER.warning("Alarm cleanup: %s", error)
