"""Persistent alarm state machine, independent of Home Assistant internals."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import timedelta
import logging
from uuid import uuid4

from .const import GRACE_SECONDS, MAX_ALARMS
from .models import Conflict, InvalidAlarm, iso, new_runtime, next_occurrence, utc, validate_config

_LOGGER = logging.getLogger(__name__)


class AlarmEngine:
    """Persist transitions before outputs; serialize edits and reject stale writes.

    port implements now, timezone, load/save, arm, changed, start/stop_outputs,
    and fired. External device calls run outside the state lock.
    """

    def __init__(self, port):
        self.port = port
        self.records: dict[str, dict] = {}
        self.lock = asyncio.Lock()
        self.jobs: dict[str, asyncio.Task] = {}
        self.closed = False

    async def initialize(self, run_due=True):
        data = await self.port.load()
        if data is not None:
            if not isinstance(data, dict) or not isinstance(data.get("alarms"), list):
                raise InvalidAlarm("Alarm storage is invalid; restore a backup before loading")
            for record in data["alarms"]:
                # Do not silently discard a damaged user's alarm.
                if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                    raise InvalidAlarm("Invalid stored alarm")
                if record["id"] in self.records:
                    raise InvalidAlarm("Duplicate stored alarm id")
                record = deepcopy(record)
                record["config"] = validate_config(record["config"])
                runtime = record["runtime"]
                runtime.setdefault("test_run", runtime.get("last_result") == "test")
                if runtime["status"] not in ("idle", "ringing", "snoozed"):
                    raise InvalidAlarm("Invalid alarm runtime state")
                for key in ("next_at", "started_at", "end_at", "snooze_until"):
                    if runtime.get(key):
                        utc(runtime[key])
                if runtime["status"] == "ringing":
                    runtime.update(status="idle", token=None, end_at=None, last_result="interrupted")
                self.records[record["id"]] = record
        await self._commit(deepcopy(self.records))
        if run_due:
            await self.tick()

    def snapshot(self):
        return {
            "alarms": deepcopy(list(self.records.values())),
            "timezone": self.port.timezone,
            "server_time": iso(self.port.now()),
        }

    def _arm(self):
        if self.closed:
            self.port.arm(None)
            return
        pending = []
        for record in self.records.values():
            r = record["runtime"]
            if record["config"]["enabled"] and r["next_at"]:
                pending.append(utc(r["next_at"]))
            for key in ("snooze_until", "end_at"):
                if r.get(key):
                    pending.append(utc(r[key]))
        self.port.arm(min(pending) if pending else None)

    async def _commit(self, records):
        # A failed disk write leaves the in-memory state and outputs untouched.
        await self.port.save({"alarms": deepcopy(list(records.values()))})
        self.records = records
        self._arm()
        self.port.changed()

    async def save_alarm(self, raw, alarm_id=None, revision=None):
        config = validate_config(raw)
        stopped = None
        async with self.lock:
            self._ensure_open()
            records = deepcopy(self.records)
            now = self.port.now()
            if alarm_id:
                old = records.get(alarm_id)
                if old is None:
                    raise InvalidAlarm("Alarm no longer exists")
                if type(revision) is not int or revision != old["revision"]:
                    raise Conflict("This alarm changed elsewhere. Reopen it before saving.")
                runtime = deepcopy(old["runtime"])
                keys = ("time", "days", "repeat_enabled", "enabled")
                if any(config[k] != old["config"][k] for k in keys):
                    runtime["next_at"] = iso(next_occurrence(config, now, self.port.timezone))
                    runtime["skipped_at"] = None
                if runtime["status"] in ("ringing", "snoozed"):
                    stopped = old
                    runtime.update(status="idle", token=None, snooze_until=None, end_at=None)
                record = {"id": alarm_id, "revision": old["revision"] + 1, "config": config, "runtime": runtime}
            else:
                if len(records) >= MAX_ALARMS:
                    raise InvalidAlarm(f"Maximum {MAX_ALARMS} alarms reached")
                alarm_id = uuid4().hex
                record = {"id": alarm_id, "revision": 1, "config": config,
                          "runtime": new_runtime(config, now, self.port.timezone)}
            records[alarm_id] = record
            await self._commit(records)
        if stopped:
            await self._stop(stopped)
        return deepcopy(record)

    async def delete_alarm(self, alarm_id):
        async with self.lock:
            self._ensure_open()
            records = deepcopy(self.records)
            old = records.pop(alarm_id, None)
            if old is None:
                raise InvalidAlarm("Alarm no longer exists")
            await self._commit(records)
        await self._stop(old)

    async def action(self, alarm_id, action, token=None):
        stopped = None
        started = None
        async with self.lock:
            self._ensure_open()
            records = deepcopy(self.records)
            record = records.get(alarm_id)
            if record is None:
                raise InvalidAlarm("Alarm no longer exists")
            c, r = record["config"], record["runtime"]
            now = self.port.now()
            if token is not None and (token != r["token"] or r["status"] != "ringing"):
                return False  # Ignore stale/duplicate notification buttons.
            if action in ("enable", "disable"):
                stopped = deepcopy(record)
                c["enabled"] = action == "enable"
                record["revision"] += 1
                r.update(status="idle", token=None, end_at=None, snooze_until=None, skipped_at=None)
                r["next_at"] = iso(next_occurrence(c, now, self.port.timezone))
            elif action == "snooze":
                if not c["snooze_enabled"] or r["status"] != "ringing":
                    raise InvalidAlarm("Snooze is unavailable for this alarm")
                stopped = deepcopy(record)
                r.update(status="snoozed", token=None, end_at=None,
                         snooze_until=iso(now + timedelta(minutes=c["snooze_minutes"])), last_result="snoozed")
            elif action == "dismiss":
                stopped = deepcopy(record)
                r.update(status="idle", token=None, end_at=None, snooze_until=None, last_result="dismissed")
            elif action == "skip":
                if not c["skip_enabled"] or not c["enabled"] or not r["next_at"]:
                    raise InvalidAlarm("There is no enabled occurrence to skip")
                r["skipped_at"] = r["next_at"]
                if c["repeat_enabled"]:
                    r["next_at"] = iso(next_occurrence(c, max(now, utc(r["next_at"])), self.port.timezone))
                else:
                    c["enabled"] = False
                    record["revision"] += 1
                    r["next_at"] = None
                r["last_result"] = "skipped"
            elif action == "test":
                if r["status"] != "idle":
                    raise InvalidAlarm("Dismiss this alarm before testing it")
                self._ring(record, now, test=True)
                started = deepcopy(record)
            else:
                raise InvalidAlarm("Unknown alarm action")
            await self._commit(records)
        if stopped:
            await self._stop(stopped)
        if started:
            self._launch(started)
        return True

    def _ring(self, record, now, test=False):
        c, r = record["config"], record["runtime"]
        duration = timedelta(seconds=10) if test else timedelta(minutes=c["ring_minutes"])
        r.update(status="ringing", token=uuid4().hex, started_at=iso(now),
                 test_run=test,
                 end_at=iso(now + duration) if test or c["auto_dismiss_enabled"] else None,
                 snooze_until=None, errors=[], last_result="test" if test else "fired")
        if not test:
            r["last_fired"] = iso(now)

    async def tick(self):
        if self.closed:
            return
        stops, starts = [], []
        async with self.lock:
            # close() may have acquired the lock while this tick was waiting.
            if self.closed:
                return
            records = deepcopy(self.records)
            now = self.port.now()
            changed = False
            for record in records.values():
                c, r = record["config"], record["runtime"]
                if r["end_at"] and utc(r["end_at"]) <= now:
                    stops.append(deepcopy(record))
                    r.update(status="idle", token=None, end_at=None, last_result="auto-dismissed")
                    changed = True
                if r["snooze_until"] and utc(r["snooze_until"]) <= now:
                    due = utc(r["snooze_until"])
                    r.update(snooze_until=None, status="idle")
                    if (now - due).total_seconds() <= GRACE_SECONDS:
                        self._ring(record, now, test=r.get("test_run", False))
                        starts.append(deepcopy(record))
                    else:
                        r["last_result"] = "missed"
                    changed = True
                if c["enabled"] and r["next_at"] and utc(r["next_at"]) <= now:
                    due = utc(r["next_at"])
                    # A preview must never consume the actual scheduled alarm.
                    if r["status"] in ("ringing", "snoozed") and r.get("test_run", False):
                        stops.append(deepcopy(record))
                        r.update(status="idle", token=None, end_at=None, snooze_until=None)
                    if c["repeat_enabled"]:
                        r["next_at"] = iso(next_occurrence(c, now, self.port.timezone))
                    else:
                        c["enabled"] = False
                        record["revision"] += 1
                        r["next_at"] = None
                    if r["status"] == "idle":
                        if (now - due).total_seconds() <= GRACE_SECONDS:
                            self._ring(record, now)
                            starts.append(deepcopy(record))
                        else:
                            r["last_result"] = "missed"
                    changed = True
            if changed:
                await self._commit(records)
            else:
                self._arm()
        for record in stops:
            await self._stop(record)
        for record in starts:
            self._launch(record)

    def is_current(self, alarm_id, token):
        record = self.records.get(alarm_id)
        return bool(not self.closed and record and record["runtime"]["token"] == token and record["runtime"]["status"] == "ringing")

    def _launch(self, record):
        alarm_id, token = record["id"], record["runtime"]["token"]
        if not self.is_current(alarm_id, token):
            return

        async def run():
            try:
                self.port.fired(record)
                errors = await self.port.start_outputs(record, lambda: self.is_current(alarm_id, token))
                async with self.lock:
                    if self.is_current(alarm_id, token):
                        records = deepcopy(self.records)
                        records[alarm_id]["runtime"]["errors"] = errors
                        await self._commit(records)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("Alarm output failed: %s", alarm_id)
            finally:
                self.jobs.pop(token, None)

        self.jobs[token] = asyncio.create_task(run(), name=f"daybreak:{token}")

    async def _stop(self, record):
        token = record["runtime"].get("token")
        if not token:
            return
        job = self.jobs.get(token)
        if job and job is not asyncio.current_task():
            job.cancel()
            await asyncio.gather(job, return_exceptions=True)
        try:
            await self.port.stop_outputs(record)
        except Exception:
            _LOGGER.exception("Could not stop alarm output: %s", record["id"])

    async def timezone_changed(self):
        async with self.lock:
            self._ensure_open()
            records = deepcopy(self.records)
            for record in records.values():
                record["runtime"]["next_at"] = iso(next_occurrence(record["config"], self.port.now(), self.port.timezone))
            await self._commit(records)

    async def close(self):
        async with self.lock:
            self.closed = True
            self.port.arm(None)
        for record in list(self.records.values()):
            await self._stop(record)

    def _ensure_open(self):
        if self.closed:
            raise InvalidAlarm("Daybreak Alarms has been unloaded")
