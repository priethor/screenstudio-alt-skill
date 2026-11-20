#!/usr/bin/env python3
"""Copy the macOS cursor set from a local Screen Studio install into a folder that
`render.py --cursor-set` reads. The images belong to Screen Studio: this only reads
them from your own copy of the app, and nothing here ships them.

    python3 src/screenstudio-cursors.py ~/.cache/screenstudio-cursors
"""
import base64, io, json, os, re, struct, sys
from PIL import Image

APP = "/Applications/Screen Studio.app/Contents/Resources/app.asar"
SET = ("assets", "cursors", "sets", "macos")
# render.py kind -> Screen Studio file name prefix. The I-beam is a bare vector path in
# Screen Studio's set, so it stays the drawn one.
FILES = {"default": "pointer-", "pointer": "pointinghand-", "ew": "resizeleftright-",
         "ns": "resizeupdown-"}

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
            png = re.search(r"base64,([A-Za-z0-9+/=\s]+)", svg).group(1)
            img = Image.open(io.BytesIO(base64.b64decode(png))).convert("RGBA")
            img.save(os.path.join(out, kind + ".png"))
            px, py = (float(v) for v in re.search(r"__([\d.]+)-([\d.]+)\.svg$", name).groups())
            hotspots[kind] = [px / 100 * img.width, py / 100 * img.height]   # name carries %
    json.dump(hotspots, open(os.path.join(out, "hotspots.json"), "w"), indent=1)
    print(f"wrote {len(hotspots)} cursors to {out}")

if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(os.path.expanduser(sys.argv[1]))
