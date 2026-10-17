"""Validated alarm configuration and timezone-aware calendar calculations.

This module deliberately has no Home Assistant imports, so the calendar and
validation rules can be tested against a controlled clock.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import math
import re
from zoneinfo import ZoneInfo


class InvalidAlarm(ValueError):
    """Configuration is invalid."""


class Conflict(ValueError):
    """The alarm changed in another client."""


def default_config() -> dict:
    return {
        "label": "Alarm", "time": "07:00", "enabled": True,
        "repeat_enabled": False, "days": [0, 1, 2, 3, 4],
        "snooze_enabled": True, "snooze_minutes": 9,
        "skip_enabled": True,
        "auto_dismiss_enabled": True, "ring_minutes": 5,
        "sound": {
            "enabled": False, "targets": [], "areas": [],
            "media_id": "builtin:daybreak", "media_type": "music",
            "loop": True, "volume_enabled": False, "volume": 0.35,
            "restore_volume": True,
        },
        "lights": {
            "enabled": False, "targets": [],
            "brightness_enabled": False, "brightness": 50,
        },
        "scripts": {"enabled": False, "targets": []},
        "notify": {"enabled": False, "targets": [], "actions_enabled": True,
                   "prompt_delivery": False},
    }


def _merge(default: dict, raw: dict, path: str = "alarm") -> dict:
    if not isinstance(raw, dict):
        raise InvalidAlarm(f"{path} must be an object")
    if unknown := set(raw) - set(default):
        raise InvalidAlarm(f"Unknown {path} field: {sorted(unknown)[0]}")
    out = deepcopy(default)
    for key, value in raw.items():
        out[key] = _merge(default[key], value, f"{path}.{key}") if isinstance(default[key], dict) else deepcopy(value)
    return out


def _bool(value, name):
    if type(value) is not bool:
        raise InvalidAlarm(f"{name} must be on or off")


def _number(value, name, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InvalidAlarm(f"{name} must be a number")
    if (integer and type(value) is not int) or not low <= value <= high:
        raise InvalidAlarm(f"{name} must be between {low} and {high}")


def _ids(value, name, prefix=None):
    if not isinstance(value, list) or len(value) > 100:
        raise InvalidAlarm(f"{name} must be a list of at most 100 targets")
    for item in value:
        if not isinstance(item, str) or not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,199}", item):
            raise InvalidAlarm(f"Invalid target in {name}")
        if prefix and not item.startswith(prefix):
            raise InvalidAlarm(f"{name} requires {prefix} targets")
    return list(dict.fromkeys(value))


def validate_config(raw: dict) -> dict:
    c = _merge(default_config(), raw)
    for key in ("enabled", "repeat_enabled", "snooze_enabled", "skip_enabled", "auto_dismiss_enabled"):
        _bool(c[key], key)
    if not isinstance(c["label"], str) or not 1 <= len(c["label"].strip()) <= 80:
        raise InvalidAlarm("Label must contain 1–80 characters")
    c["label"] = c["label"].strip()
    if not isinstance(c["time"], str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", c["time"]):
        raise InvalidAlarm("Time must be HH:MM in 24-hour format")
    if not isinstance(c["days"], list) or any(type(d) is not int or not 0 <= d <= 6 for d in c["days"]):
        raise InvalidAlarm("Days must be numbers 0 (Monday) through 6 (Sunday)")
    c["days"] = sorted(set(c["days"]))
    if c["repeat_enabled"] and not c["days"]:
        raise InvalidAlarm("Select at least one repeat day")
    _number(c["snooze_minutes"], "Snooze duration", 1, 120, True)
    _number(c["ring_minutes"], "Auto-dismiss duration", 1, 120, True)
    for section in ("sound", "lights", "scripts", "notify"):
        _bool(c[section]["enabled"], f"{section}.enabled")
    sound = c["sound"]
    for key in ("loop", "volume_enabled", "restore_volume"):
        _bool(sound[key], f"sound.{key}")
    _number(sound["volume"], "Volume", 0, 1)
    sound["targets"] = _ids(sound["targets"], "Speakers", "media_player.")
    sound["areas"] = _ids(sound["areas"], "Rooms")
    # Turning a feature off must work even after clearing its optional editor.
    if not sound["enabled"] and sound["media_id"] == "":
        sound["media_id"] = "builtin:daybreak"
    if not sound["enabled"] and sound["media_type"] == "":
        sound["media_type"] = "music"
    if not isinstance(sound["media_id"], str) or not 1 <= len(sound["media_id"]) <= 2048:
        raise InvalidAlarm("Choose an alarm sound or media URL")
    if any(ch in sound["media_id"] for ch in ("\n", "\r", "\x00")):
        raise InvalidAlarm("Invalid media identifier")
    if not isinstance(sound["media_type"], str) or not re.fullmatch(r"[a-zA-Z0-9_./+-]{1,80}", sound["media_type"]):
        raise InvalidAlarm("Invalid media type")
    if sound["enabled"] and not (sound["targets"] or sound["areas"]):
        raise InvalidAlarm("Select a speaker, group, or room")
    light = c["lights"]
    _bool(light["brightness_enabled"], "lights.brightness_enabled")
    _number(light["brightness"], "Brightness", 1, 100, True)
    light["targets"] = _ids(light["targets"], "Lights", "light.")
    c["scripts"]["targets"] = _ids(c["scripts"]["targets"], "Scripts", "script.")
    c["notify"]["targets"] = _ids(c["notify"]["targets"], "App notifications", "mobile_app_")
    _bool(c["notify"]["actions_enabled"], "notify.actions_enabled")
    _bool(c["notify"]["prompt_delivery"], "notify.prompt_delivery")
    for section in ("lights", "scripts", "notify"):
        if c[section]["enabled"] and not c[section]["targets"]:
            raise InvalidAlarm(f"Select a target for {section}")
    return c


def utc(value: str | datetime) -> datetime:
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    if result.tzinfo is None:
        raise InvalidAlarm("Stored time must include a timezone")
    return result.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def next_occurrence(config: dict, after: datetime, timezone: str) -> datetime | None:
    """Find the next wall-clock occurrence, strictly after an aware timestamp.

    Spring gaps are skipped. A fall-back repeated time uses the FIRST occurrence
    only, even when called between the two folds. Weekdays refer to the HA zone.
    """
    if not config["enabled"]:
        return None
    after = utc(after)
    zone = ZoneInfo(timezone)
    local_date = after.astimezone(zone).date()
    hour, minute = map(int, config["time"].split(":"))
    for offset in range(15):
        date = local_date + timedelta(days=offset)
        if config["repeat_enabled"] and date.weekday() not in config["days"]:
            continue
        wall = datetime(date.year, date.month, date.day, hour, minute)
        valid = []
        for fold in (0, 1):
            candidate = wall.replace(tzinfo=zone, fold=fold).astimezone(UTC)
            if candidate.astimezone(zone).replace(tzinfo=None) == wall:
                valid.append(candidate)
        if valid and (first := min(valid)) > after:
            return first
    raise InvalidAlarm("Could not find the next occurrence")


def new_runtime(config: dict, now: datetime, timezone: str) -> dict:
    return {
        "next_at": iso(next_occurrence(config, now, timezone)),
        "status": "idle", "token": None, "started_at": None, "test_run": False,
        "snooze_until": None, "end_at": None, "last_fired": None,
        "last_result": None, "errors": [], "skipped_at": None,
    }
