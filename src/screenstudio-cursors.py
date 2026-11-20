#!/usr/bin/env python3
"""Copy the macOS cursor set from a local Screen Studio install into a folder that
`render.py --cursor-set` reads. The images belong to Screen Studio: this only reads
them from your own copy of the app, and nothing here ships them.

    python3 src/screenstudio-cursors.py ~/.cache/screenstudio-cursors
"""
import base64, io, json, os, re, struct, sys
from PIL import Image, ImageDraw, ImageFilter

APP = "/Applications/Screen Studio.app/Contents/Resources/app.asar"
SET = ("assets", "cursors", "sets", "macos")
# render.py kind -> Screen Studio file name prefix
FILES = {"default": "pointer-", "pointer": "pointinghand-", "text": "ibeam-",
         "ew": "resizeleftright-", "ns": "resizeupdown-"}

def _path_points(d, steps=24):
    """Outline of an SVG path made of absolute M/L/C/Z commands, with curves flattened."""
    tokens = re.findall(r"[MLCZ]|-?[\d.]+", d)
    pts, i, cmd = [], 0, None
    while i < len(tokens):
        if tokens[i] in "MLCZ":
            cmd = tokens[i]; i += 1
            if cmd == "Z": continue
        nums = [float(v) for v in tokens[i:i + (6 if cmd == "C" else 2)]]
        i += len(nums)
        if cmd == "C":
            (x0, y0), (x1, y1, x2, y2, x3, y3) = pts[-1], nums
            for k in range(1, steps + 1):
                t = k / steps; u = 1 - t
                pts.append((u**3*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3,
                            u**3*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3))
        else:
            pts.append(tuple(nums))
    return pts

def _vector_cursor(svg, ss=4):
    """Screen Studio keeps a few cursors as a bare black path and adds the outline and
    shadow itself; draw them with the same white ring and soft shadow as the bitmaps."""
    w, h = (int(float(v)) for v in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups())
    body = Image.new("L", (w*ss, h*ss), 0)
    for d in re.findall(r' d="([^"]+)"', svg):
        ImageDraw.Draw(body).polygon([(x*ss, y*ss) for x, y in _path_points(d)], fill=255)
    ring = body.filter(ImageFilter.MaxFilter(2*(20*ss//2)+1))      # ~20px white outline at 768
    ring = ring.resize((w, h), Image.LANCZOS); body = body.resize((w, h), Image.LANCZOS)
    shadow = Image.new("L", (w, h), 0); shadow.paste(ring, (0, 8))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.45))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.paste((0, 0, 0, 255), (0, 0), shadow)
    img.paste((255, 255, 255, 255), (0, 0), ring)
    img.paste((0, 0, 0, 255), (0, 0), body)
    return img

def main(out, app=APP):
    with open(app, "rb") as f:
        head = f.read(16)
        pickle, size = struct.unpack("<I", head[4:8])[0], struct.unpack("<I", head[12:16])[0]
        index = json.loads(f.read(size))
        node = index
        for part in SET: node = node["files"][part]
        os.makedirs(out, exist_ok=True)
        hotspots = {}
        for kind, prefix in FILES.items():
            name = next(n for n in node["files"] if n.startswith(prefix))
            entry = node["files"][name]
            f.seek(8 + pickle + int(entry["offset"]))
            svg = f.read(entry["size"]).decode()
            png = re.search(r"base64,([A-Za-z0-9+/=\s]+)", svg)
            img = (Image.open(io.BytesIO(base64.b64decode(png.group(1)))).convert("RGBA")
                   if png else _vector_cursor(svg))
            img.save(os.path.join(out, kind + ".png"))
            px, py = (float(v) for v in re.search(r"__([\d.]+)-([\d.]+)\.svg$", name).groups())
            hotspots[kind] = [px / 100 * img.width, py / 100 * img.height]   # name carries %
    json.dump(hotspots, open(os.path.join(out, "hotspots.json"), "w"), indent=1)
    print(f"wrote {len(hotspots)} cursors to {out}")

if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(os.path.expanduser(sys.argv[1]))
