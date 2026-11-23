#!/usr/bin/env python3
"""Checks for the cursor and backdrop options in render.py. No dependencies beyond the
renderer's own (numpy, Pillow); run with `python3 test/test_cursor.py`."""
import importlib.util, json, os, sys, tempfile
import numpy as np

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

def test_cursor_kind_track_ignores_brief_changes():
    # pointer, a 50ms arrow while crossing a gap, pointer again, then a long arrow
    kinds = [(0.0, "pointer"), (1.0, "default"), (1.05, "pointer"), (2.0, "default")]
    track = render.cursor_kind_track(kinds, 60, 3.0)
    assert track[int(1.02 * 60)] == "pointer"
    assert track[int(2.5 * 60)] == "default"

def test_cursor_kind_track_keeps_a_held_change():
    track = render.cursor_kind_track([(0.0, "default"), (1.0, "pointer")], 60, 2.0)
    assert track[int(1.1 * 60)] == "pointer"

def test_kind_sprites_have_hotspots_inside():
    for kind in ("default", "pointer", "text", "ew", "ns"):
        spr, hx, hy = render.kind_sprite(kind, 38)
        assert 0 <= hx < spr.width and 0 <= hy < spr.height, (kind, hx, hy, spr.size)
        assert spr.getbbox() is not None, kind

def test_cursor_set_replaces_drawn_sprites_and_keeps_the_rest():
    from PIL import Image
    folder = tempfile.mkdtemp()
    arrow = Image.new("RGBA", (200, 200), (0, 0, 0, 0)); arrow.paste((0, 0, 0, 255), (50, 50, 100, 150))
    hand = Image.new("RGBA", (200, 200), (0, 0, 0, 0)); hand.paste((255, 0, 0, 255), (60, 40, 140, 140))
    arrow.save(os.path.join(folder, "default.png")); hand.save(os.path.join(folder, "pointer.png"))
    json.dump({"default": [50, 50], "pointer": [100, 40]}, open(os.path.join(folder, "hotspots.json"), "w"))
    try:
        render.use_cursor_set(folder)
        spr, hx, hy = render.kind_sprite("default", 38)
        assert spr.height == 38 and abs(hx) < 1e-6 and abs(hy) < 1e-6   # arrow body sets the scale
        spr, hx, hy = render.kind_sprite("pointer", 38)
        assert spr.getpixel((spr.width // 2, spr.height // 2))[0] > 200   # the red hand image
        assert abs(hx - 40 * 0.38) < 0.5 and abs(hy) < 1e-6
        assert render.kind_sprite("text", 38)[0].getbbox() is not None    # falls back to drawn
    finally:
        render.use_cursor_set(None)

def test_screenstudio_extractor_reads_vector_paths():
    spec = importlib.util.spec_from_file_location("ssc", os.path.join(ROOT, "src", "screenstudio-cursors.py"))
    ssc = importlib.util.module_from_spec(spec); spec.loader.exec_module(ssc)
    pts = ssc._path_points("M 0 0 L 10 0 C 10 5 5 10 0 10 Z", steps=4)
    assert pts[0] == (0.0, 0.0) and pts[1] == (10.0, 0.0) and pts[-1] == (0.0, 10.0) and len(pts) == 6
    svg = '<svg viewBox="0 0 100 100"><path d="M 40 20 L 60 20 L 60 80 L 40 80 Z"/></svg>'
    img = ssc._vector_cursor(svg, ss=2)
    assert img.size == (100, 100)
    assert img.getpixel((50, 50))[:3] == (0, 0, 0) and img.getpixel((50, 50))[3] == 255   # black body
    assert min(img.getpixel((35, 50))[:3]) > 200                                          # white ring

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

def _cursor_height(path):
    """Height of the dark cursor outline in the first frame of a white render."""
    import subprocess
    from PIL import Image
    png = path + ".png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.0", "-i", path, "-frames:v", "1", png], check=True)
    im = Image.open(png).convert("L").point(lambda v: 255 if v < 100 else 0)
    box = im.getbbox()
    return box[3] - box[1]

def test_cursor_zoom_grows_the_cursor_with_the_camera():
    import subprocess
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=white:s=1280x720:d=2:r=10",
                    "-pix_fmt", "yuv420p", src], check=True)
    events = _events([HEADER] + [{"t": i / 10, "type": "move", "x": 640, "y": 360} for i in range(20)])
    regions = [{"t0": 0.0, "t1": 2.0, "z": 2.0, "cx": 640, "cy": 360}]
    sizes = {}
    for flag in (False, True):
        out = os.path.join(tmp, f"out{int(flag)}.mp4")
        render.render(src, regions, out, fps=10, events=events, cursor=True, cursor_zoom=flag)
        sizes[flag] = _cursor_height(out)
    assert sizes[True] > sizes[False] * 1.6, sizes

def test_cursor_moves_on_every_output_frame_of_a_low_fps_source():
    import subprocess
    from PIL import Image
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src.mp4"); out = os.path.join(tmp, "out.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=white:s=1280x720:d=2:r=25",
                    "-pix_fmt", "yuv420p", src], check=True)
    events = _events([HEADER] + [{"t": i / 100, "type": "move", "x": 100 + i * 5, "y": 360}
                                 for i in range(200)])
    render.render(src, [], out, fps=60, events=events, cursor=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.0", "-i", out, "-frames:v", "12",
                    os.path.join(tmp, "f%02d.png")], check=True)
    xs = []
    for i in range(1, 13):
        im = Image.open(os.path.join(tmp, f"f{i:02d}.png")).convert("L").point(lambda v: 255 if v < 100 else 0)
        xs.append(im.getbbox()[0])
    steps = [b - a for a, b in zip(xs, xs[1:])]
    assert all(st > 0 for st in steps), xs   # tied to 25fps source frames, some steps were 0

def test_load_events_reads_captions():
    path = _events([HEADER,
                    {"t": 1.0, "type": "caption", "text": "Open the menu"},
                    {"t": 4.0, "type": "caption", "text": "Pick Text", "dur": 2, "anchor": "bottom"}])
    ev = polish.load_events(path, VID)
    assert ev["captions"] == [(1.0, "Open the menu", None, None), (4.0, "Pick Text", 2, "bottom")]

def test_captions_hold_and_never_overlap():
    same = lambda t: t
    out = render.caption_callouts([(1.0, "a", None, None), (2.5, "b", None, None), (8.0, "c", 1.0, "top")],
                                  same, 20.0)
    assert [(c["t0"], round(c["t1"], 2), c["anchor"]) for c in out] == \
        [(1.0, 2.2, "bottom"), (2.5, 5.5, "bottom"), (8.0, 9.0, "top")]

def test_captions_follow_the_output_clock_and_stay_readable():
    double = lambda t: t / 2          # whole recording at 2x
    out = render.caption_callouts([(4.0, "fast", 1.0, None)], double, 20.0)
    assert out[0]["t0"] == 2.0 and out[0]["t1"] == 3.0   # 0.5s of output, stretched to 1s

def test_unknown_wallpaper_suggests_names():
    if not render.wallpaper_names(): return          # not macOS
    try:
        render.wallpaper_image("Ventura Graphik")
    except ValueError as e:
        assert "Ventura Graphic" in str(e), e
    else:
        raise AssertionError("expected a ValueError")

def test_render_draws_caption_events():
    import subprocess
    from PIL import Image
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src.mp4"); out = os.path.join(tmp, "out.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=white:s=1280x720:d=3:r=10",
                    "-pix_fmt", "yuv420p", src], check=True)
    events = _events([HEADER, {"t": 1.0, "type": "caption", "text": "Change the type"}])
    render.render(src, [], out, fps=10, events=events)
    def bottom_dark(t):
        png = os.path.join(tmp, f"f{t}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", out, "-frames:v", "1", png], check=True)
        band = Image.open(png).convert("L").crop((0, 600, 1280, 720))
        return int((np.asarray(band) < 100).sum())
    assert bottom_dark(0.5) == 0 and bottom_dark(2.0) > 500

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

def test_accent_spans_split_on_stars():
    assert render.accent_spans("Spot something odd? *Ask why*") == [("Spot something odd? ", False), ("Ask why", True)]
    assert render.accent_spans("No markup") == [("No markup", False)]
    assert render.plain_text("Cortext *0.4*") == "Cortext 0.4"

def test_cards_add_their_length_and_show_the_card():
    import subprocess
    from PIL import Image
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src.mp4"); out = os.path.join(tmp, "out.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=640x360:d=1:r=10",
                    "-pix_fmt", "yuv420p", src], check=True)
    card = {"title": "Cortext *0.4*", "subtitle": "Lock, archive, trash", "url": "cortext.digital",
            "dur": 1.0, "bg": "#ffffff"}
    r = render.render(src, [], out, fps=10, intro=card, outro=card, metadata=False)
    assert abs(r["dur"] - 3.0) < 0.05, r
    def mean(t):
        png = os.path.join(tmp, f"c{t}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", out, "-frames:v", "1", png], check=True)
        return float(np.asarray(Image.open(png).convert("L")).mean())
    assert mean(0.1) > 200 and mean(1.5) < 30 and mean(2.9) > 200   # card, demo, card

def test_accent_paints_the_starred_run():
    from PIL import Image
    W, H, font, bb, padx, pady = render._callout_measure("ab *cd*", 40, True)
    img = render._callout_render("ab *cd*", 255, font, bb, padx, pady, W, H, (255, 0, 0))
    px = np.asarray(img.convert("RGB")).reshape(-1, 3)
    assert ((px[:, 0] > 200) & (px[:, 1] < 80)).sum() > 20                # red text present

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
