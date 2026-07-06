import datetime as dt
from zoneinfo import ZoneInfo

from fable.util import angle_in_ranges, csv_to_slug_set, deep_merge, dget, indices_in_window, slugify


def test_slugify_accents():
    assert slugify("Sidi Bou Saïd") == "sidi-bou-said"
    assert slugify("Kélibia") == "kelibia"
    assert slugify("El Haouaria") == "el-haouaria"
    assert slugify("Gammarth (port)") == "gammarth-port"
    assert slugify("Ras   Fartass!!") == "ras-fartass"


def test_dget():
    d = {"a": {"b": {"c": 3}}}
    assert dget(d, "a.b.c") == 3
    assert dget(d, "a.x", "def") == "def"
    assert dget(None, "a.b", 7) == 7


def test_deep_merge_nested():
    dst = {"a": {"x": 1, "y": 2}, "b": 1}
    deep_merge(dst, {"a": {"y": 99}, "c": 3})
    assert dst == {"a": {"x": 1, "y": 99}, "b": 1, "c": 3}


def test_csv_to_slug_set():
    assert csv_to_slug_set("Gammarth (port), Kélibia") == {"gammarth-port", "kelibia"}
    assert csv_to_slug_set("") is None


def test_angle_wraparound():
    assert angle_in_ranges(350, [(330, 360), (0, 70)])
    assert angle_in_ranges(20, [(330, 360), (0, 70)])
    assert not angle_in_ranges(180, [(330, 360), (0, 70)])
    # single wrap-range form
    assert angle_in_ranges(10, [(330, 70)])
    assert not angle_in_ranges(200, [(330, 70)])


def test_indices_in_window_tz():
    tz = ZoneInfo("Africa/Tunis")
    start = dt.datetime(2026, 7, 5, 10, 0, tzinfo=tz)
    end = start + dt.timedelta(hours=3)
    times = ["2026-07-05T09:00", "2026-07-05T10:00", "2026-07-05T11:00",
             "2026-07-05T12:00", "2026-07-05T13:00"]
    assert indices_in_window(times, start, end, tz) == [1, 2, 3]
