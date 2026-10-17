"""Controlled clocks and output gateways; never contacts a real HA instance."""

import asyncio
from copy import deepcopy
from datetime import datetime
import importlib
from pathlib import Path
import sys
import types

PACKAGE = "daybreak_under_test"
ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "custom_components/daybreak_alarm")]
sys.modules[PACKAGE] = package
models = importlib.import_module(f"{PACKAGE}.models")
engine_module = importlib.import_module(f"{PACKAGE}.engine")
actions_module = importlib.import_module(f"{PACKAGE}.actions")


class FakePort:
    timezone = "America/New_York"

    def __init__(self, now="2026-10-16T10:59:00+00:00", data=None):
        self.clock = datetime.fromisoformat(now)
        self.data = deepcopy(data)
        self.due = None
        self.starts = []
        self.stops = []
        self.events = []
        self.saves = []
        self.fail_save = False
        self.block_outputs = None

    def now(self): return self.clock
    async def load(self): return deepcopy(self.data)
    async def save(self, data):
        if self.fail_save: raise OSError("Simulated disk full")
        self.data = deepcopy(data)
        self.saves.append(deepcopy(data))
    def arm(self, when): self.due = when
    def changed(self): self.events.append("changed")
    def fired(self, record): self.events.append(("fired", record["id"]))
    async def start_outputs(self, record, current):
        self.starts.append((deepcopy(record), deepcopy(self.data)))
        if self.block_outputs:
            await self.block_outputs.wait()
        return []
    async def stop_outputs(self, record): self.stops.append(deepcopy(record))
    async def settle(self):
        for _ in range(5): await asyncio.sleep(0)


def player(entity_id, **extra):
    return {"id": entity_id, "state": "idle", "can_play": True, "can_stop": True,
            "can_pause": True, "can_volume": True, "can_repeat": False,
            "volume": 0.2, "repeat": "off", "members": [], "group_members": [],
            "is_speaker": True, "area_id": "bedroom", **extra}


class FakeGateway:
    def __init__(self):
        self.players = {"media_player.bedroom": player("media_player.bedroom")}
        self.calls = []
        self.fail = set()

    def catalog(self): return {"speakers": list(self.players.values())}
    def player(self, entity_id): return deepcopy(self.players.get(entity_id))
    async def call(self, domain, action, data):
        self.calls.append((domain, action, deepcopy(data)))
        if (domain, action) in self.fail: raise ValueError("simulated device error")
    async def resolve_media(self, media_id, media_type): return media_id, media_type


def ringing_record(config=None, alarm_id="alarm1", token="token1"):
    c = models.validate_config(config or {})
    r = models.new_runtime(c, datetime.fromisoformat("2026-10-16T10:00:00+00:00"), "America/New_York")
    r.update(status="ringing", token=token)
    return {"id": alarm_id, "revision": 1, "config": c, "runtime": r}
