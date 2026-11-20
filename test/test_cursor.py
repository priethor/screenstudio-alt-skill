#!/usr/bin/env python3
"""Checks for the cursor and backdrop options in render.py. No dependencies beyond the
renderer's own (numpy, Pillow); run with `python3 test/test_cursor.py`."""
import importlib.util, json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "src", name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

render = _load("render")
polish = render.polish

def _events(lines):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for e in lines: f.write(json.dumps(e) + "\n")
    f.close()
    return f.name

VID = {"w": 1280, "h": 720, "fps": 30.0, "dur": 4.0}
HEADER = {"type": "header", "display": {"w": 1280, "h": 720}, "scale": 1.0}

def test_load_events_reads_cursor_kinds():
    path = _events([HEADER,
                    {"t": 0.0, "type": "move", "x": 10, "y": 10},
                    {"t": 1.0, "type": "move", "x": 20, "y": 20, "cursor": "pointer"},
                    {"t": 2.0, "type": "move", "x": 30, "y": 30, "cursor": "text"}])
    ev = polish.load_events(path, VID)
    assert ev["cursor_kinds"] == [(1.0, "pointer"), (2.0, "text")], ev["cursor_kinds"]

def test_cursor_kind_maps_css_names():
    assert render.cursor_kind("pointer") == "pointer"
    assert render.cursor_kind("col-resize") == "ew"
    assert render.cursor_kind("ns-resize") == "ns"
    assert render.cursor_kind("text") == "text"
    assert render.cursor_kind("wait") == "default"
    assert render.cursor_kind(None) == "default"

def test_cursor_kind_track_holds_latest_sample():
    track = render.cursor_kind_track([(1.0, "pointer"), (2.0, "col-resize")], 10, 3.0)
    assert track[0] == "default" and track[9] == "default"
    assert track[10] == "pointer" and track[19] == "pointer"
    assert track[20] == "ew" and track[-1] == "ew"

def test_kind_sprites_have_hotspots_inside():
    for kind in ("default", "pointer", "text", "ew", "ns"):
        spr, hx, hy = render.kind_sprite(kind, 38)
        assert 0 <= hx < spr.width and 0 <= hy < spr.height, (kind, hx, hy, spr.size)
        assert spr.getbbox() is not None, kind

def test_cursor_scale_grows_the_sprite():
    small = render.kind_sprite("pointer", 38)[0]
    big = render.kind_sprite("pointer", 57)[0]
    assert big.height > small.height * 1.4

def test_load_events_reads_mouse_ups():
    path = _events([HEADER,
                    {"t": 1.0, "type": "down", "x": 5, "y": 5, "button": "left"},
                    {"t": 1.1, "type": "up", "x": 5, "y": 5, "button": "left"}])
    ev = polish.load_events(path, VID)
    assert ev["ups"] == [(1.1, 5.0, 5.0)], ev["ups"]

def test_spring_follow_settles_on_the_target():
    track = polish.spring_follow([0.0] + [100.0] * 119, 60, 470, 70, 3)
    assert abs(track[-1] - 100.0) < 0.5, track[-1]
    assert track[3] < 50.0   # eases out of rest instead of jumping

def test_press_scale_dips_while_held_and_springs_back():
    fps = 60
    scales = render.press_scales([(1.0, 0, 0)], [(1.2, 0, 0)], fps, 3.0)
    assert scales[int(0.9*fps)] == 1.0
    assert min(scales[int(1.0*fps):int(1.3*fps)]) < 0.88
    assert abs(scales[int(2.5*fps)] - 1.0) < 0.01

def test_press_scale_holds_a_quick_click():
    fps = 60
    scales = render.press_scales([(1.0, 0, 0)], [(1.005, 0, 0)], fps, 2.0)
    assert min(scales[int(1.0*fps):int(1.2*fps)]) < 0.92

def test_scaled_sprite_keeps_the_hotspot_in_place():
    spr, hx, hy = render.kind_sprite("pointer", 38)
    s2, hx2, hy2 = render.scaled_sprite((spr, hx, hy), 0.8)
    assert abs(hx2 - hx * 0.8) < 1e-6 and abs(hy2 - hy * 0.8) < 1e-6
    assert s2.width < spr.width

TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t(); print("ok   ", t.__name__)
        except AssertionError as e:
            failed += 1; print("FAIL ", t.__name__, e)
    print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
    sys.exit(1 if failed else 0)
