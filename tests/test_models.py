from datetime import datetime, timedelta
import unittest
from support import models


class ValidationTests(unittest.TestCase):
    def test_defaults_are_independent(self):
        first = models.default_config()
        first["sound"]["targets"].append("media_player.a")
        self.assertEqual(models.default_config()["sound"]["targets"], [])

    def test_all_optional_outputs_can_be_disabled(self):
        c = models.validate_config({"snooze_enabled":False,"repeat_enabled":False,"auto_dismiss_enabled":False,"skip_enabled":False})
        self.assertTrue(all(not c[k]["enabled"] for k in ("sound","lights","scripts","notify")))

    def test_invalid_values_rejected(self):
        bad = [
            {"time":"24:00"}, {"time":"7:00"}, {"time":"12:60"}, {"time":700},
            {"enabled":"false"}, {"enabled":1}, {"days":[True]}, {"days":[7]},
            {"days":"Monday"}, {"repeat_enabled":True,"days":[]}, {"label":" "},
            {"label":"x"*81}, {"snooze_minutes":0}, {"snooze_minutes":1.5},
            {"ring_minutes":121}, {"sound":{"volume":float("nan")}},
            {"sound":{"volume":float("inf")}}, {"sound":{"volume":True}},
            {"sound":{"enabled":True}}, {"lights":{"enabled":True}},
            {"notify":{"enabled":True}}, {"scripts":{"enabled":True}},
            {"notify":{"targets":["arbitrary_service"]}},
            {"scripts":{"targets":["light.fake"]}}, {"admin":True},
            {"sound":{"unknown":1}}, {"sound":[]},
            {"sound":{"targets":["media_player.a\n"]}},
            {"sound":{"media_id":"bad\nURL"}}, {"sound":{"media_type":"a b"}},
        ]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(models.InvalidAlarm):
                models.validate_config(raw)

    def test_days_are_sorted_and_deduplicated(self):
        self.assertEqual(models.validate_config({"days":[6,0,0,2]})["days"],[0,2,6])

    def test_disabled_features_preserve_targets(self):
        c=models.validate_config({"sound":{"enabled":False,"targets":["media_player.a"]}})
        self.assertEqual(c["sound"]["targets"],["media_player.a"])

    def test_sound_can_be_disabled_after_clearing_custom_media(self):
        c=models.validate_config({"sound":{"enabled":False,"media_id":"","media_type":""}})
        self.assertFalse(c["sound"]["enabled"])
        self.assertEqual(c["sound"]["media_id"],"builtin:daybreak")

    def test_no_mutation_of_input(self):
        raw={"label":"  Wake up  ","days":[1,1]}
        self.assertEqual(models.validate_config(raw)["label"],"Wake up")
        self.assertEqual(raw["label"],"  Wake up  ")


class CalendarTests(unittest.TestCase):
    def check(self, raw, after, expected, zone="America/New_York"):
        result=models.next_occurrence(models.validate_config(raw),datetime.fromisoformat(after),zone)
        self.assertEqual(models.iso(result),expected)

    def test_selected_weekdays(self):
        self.check({"time":"07:00","repeat_enabled":True,"days":[0,2,4]},"2026-10-16T11:00:00+00:00","2026-10-19T11:00:00+00:00")

    def test_one_time_ignores_days(self):
        self.check({"days":[],"time":"07:00"},"2026-10-17T10:00:00+00:00","2026-10-17T11:00:00+00:00")

    def test_past_time_schedules_tomorrow(self):
        self.check({},"2026-10-16T12:00:00+00:00","2026-10-17T11:00:00+00:00")

    def test_disabled_has_no_next(self):
        self.check({"enabled":False},"2026-10-16T12:00:00+00:00",None)

    def test_spring_nonexistent_wall_time_skipped(self):
        self.check({"time":"02:30"},"2026-03-08T05:00:00+00:00","2026-03-09T06:30:00+00:00")

    def test_spring_gap_selected_sunday_skips_week(self):
        self.check({"time":"02:30","repeat_enabled":True,"days":[6]},"2026-03-08T05:00:00+00:00","2026-03-15T06:30:00+00:00")

    def test_fall_back_uses_first_occurrence(self):
        self.check({"time":"01:30"},"2026-11-01T04:00:00+00:00","2026-11-01T05:30:00+00:00")

    def test_fall_back_does_not_ring_twice(self):
        self.check({"time":"01:30"},"2026-11-01T05:45:00+00:00","2026-11-02T06:30:00+00:00")

    def test_fractional_timezone(self):
        self.check({"time":"07:00"},"2026-10-16T00:00:00+00:00","2026-10-16T01:15:00+00:00","Asia/Kathmandu")

    def test_midnight(self):
        self.check({"time":"00:00"},"2026-10-16T23:59:00+00:00","2026-10-17T00:00:00+00:00","UTC")

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(models.InvalidAlarm): models.utc(datetime(2026,1,1))

    def test_all_weekdays_over_a_year(self):
        # Each weekday appears at the configured local wall time; UTC advances.
        for weekday in range(7):
            c=models.validate_config({"time":"07:45","repeat_enabled":True,"days":[weekday]})
            previous=datetime.fromisoformat("2026-01-01T00:00:00+00:00")
            from zoneinfo import ZoneInfo
            for _ in range(55):
                nxt=models.next_occurrence(c,previous,"America/New_York")
                local=nxt.astimezone(ZoneInfo("America/New_York"))
                self.assertEqual((local.weekday(),local.hour,local.minute),(weekday,7,45))
                self.assertGreater(nxt,previous)
                previous=nxt
