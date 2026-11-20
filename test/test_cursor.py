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

def _still_then_move(fps, still_s, move_at):
    n = int((move_at + 1.0) * fps)
    xs = [100.0 if i < move_at*fps else 100.0 + (i - move_at*fps) * 5 for i in range(n)]
    return xs, [50.0] * n

def test_idle_alpha_fades_after_the_threshold():
    fps = 60
    xs, ys = _still_then_move(fps, 0, 6.0)
    alpha = render.idle_alphas(xs, ys, [], fps, after=2.5)
    assert alpha[int(2.0*fps)] == 1.0
    assert alpha[int(3.5*fps)] == 0.0

def test_idle_alpha_comes_back_on_movement():
    fps = 60
    xs, ys = _still_then_move(fps, 0, 6.0)
    alpha = render.idle_alphas(xs, ys, [], fps, after=2.5)
    back = alpha[int(6.0*fps)+1:int(6.5*fps)]
    assert back[0] < 1.0 and back[-1] == 1.0   # quick fade-in, not a pop

def test_idle_alpha_treats_a_click_as_activity():
    fps = 60
    xs, ys = [100.0] * (5*fps), [50.0] * (5*fps)
    alpha = render.idle_alphas(xs, ys, [(2.0, 100, 50)], fps, after=2.5)
    assert alpha[int(4.0*fps)] == 1.0

def test_faded_sprite_hides_at_zero():
    sprite = render.kind_sprite("default", 38)
    assert render.faded_sprite(sprite, 0.0) is None
    assert render.faded_sprite(sprite, 1.0) is sprite

def _ramp_moves():
    """Rest at x=0, travel to x=500 between 1.0s and 1.5s, then rest (30Hz samples)."""
    moves = []
    for i in range(int(3.0 * 30)):
        t = i / 30
        x = 0.0 if t < 1.0 else (500.0 if t >= 1.5 else (t - 1.0) / 0.5 * 500.0)
        moves.append((t, x, 0.0))
    return moves

def test_spring_positions_land_on_time_for_the_click():
    fps = 60
    xs, _ = polish.spring_positions(_ramp_moves(), fps, 3.0, 470, 70, 3)
    assert abs(xs[int(1.5 * fps)] - 500.0) < 40, xs[int(1.5 * fps)]   # arrives with the click
    assert max(xs) < 520, max(xs)                                       # settles, no big overshoot
    assert abs(xs[-1] - 500.0) < 1.0

def test_spring_positions_ease_instead_of_jumping():
    fps = 60
    xs, _ = polish.spring_positions(_ramp_moves(), fps, 3.0, 470, 70, 3)
    steps = [abs(xs[i+1] - xs[i]) for i in range(len(xs)-1)]
    raw, _ = polish.frame_positions(_ramp_moves(), fps, 3.0)
    raw_steps = [abs(raw[i+1] - raw[i]) for i in range(len(raw)-1)]
    assert max(steps) < max(raw_steps) * 1.2   # no faster than the path itself, roughly
    assert steps[int(0.95 * fps)] > 0          # starts easing before the path moves (lead)

def test_smooth_positions_unchanged_by_the_refactor():
    xs, ys = polish.smooth_positions(_ramp_moves(), 30, 3.0)
    assert len(xs) == 91 and abs(xs[-1] - 500.0) < 1.0 and xs[0] == 0.0

def _stripes(w, h):
    """Left half red, right half blue, saved to a temp PNG."""
    from PIL import Image
    img = Image.new("RGB", (w, h), (255, 0, 0))
    img.paste((0, 0, 255), (w // 2, 0, w, h))
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False); f.close()
    img.save(f.name)
    return f.name

def test_image_backdrop_covers_the_canvas():
    bd = render.image_backdrop(_stripes(400, 400), 1280, 720)   # square into 16:9
    assert bd.size == (1280, 720)
    assert bd.getpixel((10, 360))[0] > 200 and bd.getpixel((1270, 360))[2] > 200

def test_image_backdrop_blur_softens_edges():
    sharp = render.image_backdrop(_stripes(1280, 720), 1280, 720)
    soft = render.image_backdrop(_stripes(1280, 720), 1280, 720, blur=40)
    mid = (640, 360)
    assert sharp.getpixel((636, 360))[2] < 10            # hard edge without blur
    assert 40 < soft.getpixel(mid)[0] < 215 and 40 < soft.getpixel(mid)[2] < 215

def test_render_uses_the_image_behind_the_padded_frame():
    import subprocess
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src.mp4"); out = os.path.join(tmp, "out.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=white:s=320x180:d=0.5:r=10",
                    "-pix_fmt", "yuv420p", src], check=True)
    render.render(src, [], out, fps=10, bg_image=_stripes(320, 180), pad=0.1, radius=0, shadow=False)
    frame = os.path.join(tmp, "f.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-frames:v", "1", frame], check=True)
    from PIL import Image
    im = Image.open(frame).convert("RGB")
    w, h = im.size
    assert im.getpixel((3, h // 2))[0] > 180 and im.getpixel((3, h // 2))[2] < 80    # red margin left
    assert im.getpixel((w - 4, h // 2))[2] > 180                                      # blue margin right
    assert min(im.getpixel((w // 2, h // 2))) > 220                                   # white content

def test_render_width_sets_the_output_size():
    import subprocess
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src.mp4"); out = os.path.join(tmp, "out.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=white:s=320x180:d=0.3:r=10",
                    "-pix_fmt", "yuv420p", src], check=True)
    render.render(src, [], out, fps=10, width=1920)
    size = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                           "stream=width,height", "-of", "csv=p=0", out],
                          capture_output=True, text=True, check=True).stdout.strip()
    assert size == "1920,1080", size

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
