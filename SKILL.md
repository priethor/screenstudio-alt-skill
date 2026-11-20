---
name: screenstudio-alt
description: Screen-Studio-style post-production for screen recordings, headless — PR demo videos, release highlight reels and long product walkthroughs, auto speed-up of idle, auto-zoom on click clusters, keystroke overlay chips, smoothed synthetic cursor, and 9:16 vertical export that follows the action. Use when polishing a screen recording / demo video for sharing, when the user mentions Screen Studio, auto-zoom, idle speed-up, or vertical/social video from a screen capture, and for any social-facing demo (vertical output is the default for those).
author: Conner K Ward
---

# screenstudio-alt

The skill's code lives in this directory (`polish.py`, `render.py`, `studio.py`,
`events-log.swift`, test fixtures, etc.). Published publicly as
`connerkward/screenstudio-alternative-skill`.

Two components:

- `events-log` (Swift) — capture-side input logger (cursor 60Hz, clicks, keys;
  drops keys during macOS secure input). Runs ONLY while recording. Needs
  Accessibility/Input Monitoring for the terminal. **Auto-zoom/keys/cursor need
  this data at capture time — it cannot be recovered from pixels later.**
- `polish.py` (Python, ffmpeg + PIL) — the post-production pass:

```bash
python3 src/polish.py in.mp4 --events in.events.jsonl \
  --speedup            # compress idle (input-gap ∩ frozen-pixels; animations stay 1x)
  --zoom               # eased auto-zoom on click clusters (zoompan)
  --keys               # accumulating keystroke chips (PIL overlays, no drawtext dep)
  --smooth-cursor      # synthetic eased cursor (best with sck-record --no-cursor)
  --vertical           # ALSO emit 1080x1920 following the action
```

`--speedup` works WITHOUT events (freezedetect only) — usable on the whole
existing dailies corpus.

- `render.py` — **high-quality non-destructive renderer** (preferred): single-pass
  spring-physics camera over the original high-res frames, LANCZOS into a smaller
  target (crisp zoom, ~1.3× sharper than the ffmpeg upscale path), 60fps, H + 9:16 V.
  Tunable `--freq`/`--zeta` (spring), `--fps`, `--width`. Takes explicit
  `--regions [{t0,t1,z,cx,cy}]` — plus optional `cx1,cy1,z1` end-keyframe per region:
  when present the camera **pans** (eases start→end across the held span, `ease_traj`).
  `polish.py` is the older ffmpeg-filter fallback.
- `studio.py [recording.mp4]` — local web UI, **NLE-style fixed-ruler timeline** (bar =
  source duration, never rescales → upstream always planted): zoom regions are draggable
  blocks (move / retime edges / click to add / double-click delete). Selecting a zoom
  shows a **draggable crop-rect overlay on the preview** (reframe where the zoom looks:
  drag body = move cx/cy, corner handle = zoom level). **＋ pan** adds a second END
  keyframe → a two-keyframe camera move: start rect (solid) + end rect (dashed) + a path
  arrow on the preview, a `[ Start | End ]` toggle picks which the drag edits, and
  scrubbing interpolates the pan live (same `ease_traj` as the export). Idle spans are
  **speed blocks with rate-only editing** — source range locked, rate set via inspector
  slider on select or right-edge **rate-stretch** drag (FCP retime / Premiere Rate
  Stretch); rate changes ripple downstream only. Camera easing is **smootherstep
  ease-in-out by default** (full ease, no constant-velocity middle — cinematic
  slow-start/smooth-middle/gentle-stop on zoom AND pan); Advanced section exposes an
  **easing curve** selector (Smooth · Snappy · Linear) + smoothness/ramp slider
  (`--curve`/`--ramp`, persisted in session.json, preview == export). Tunable default zoom,
  aspect, frame styling. Always-smooth synthetic cursor + click ripple + real recorded
  click sound (CC0 #735771). Export uses render.py. Free port, local. (Keystroke overlay
  exists in the engine but is off by default.)

## Easy path

`screencast.sh --demo` (screencast skill) does the whole chain: starts the event
logger, records, then polishes + emits the 9:16 vertical automatically. Vertical
is the DEFAULT for social-facing demos.

## Demo modes and house style

Every demo, whatever the project, uses the same look, then one of two modes. Ask which mode
only when the request doesn't make it clear: a PR demo or "video de muestra" is a highlight,
a release summary is several highlights in a row, a tour of many features is a walkthrough.

### House style (always on)

Blurred macOS wallpaper behind the window with a thin margin, rounded corners, shadow, and a
macOS cursor with real cursor types that grows with the zoom, squashes on click, moves on a
spring and hides when it stops. No click ripple (`--clickfx` off), no click sound.

The wallpaper is Ventura Graphic unless the user asks for another: `--wallpaper` takes any
name from macOS's Wallpaper settings (`Sonoma`, `"Big Sur Coastline"`...), and a wrong one
lists what's available.

```bash
# once per machine, needs Screen Studio installed: its macOS cursor set (arrow, hand, I-beam, resize)
python3 src/screenstudio-cursors.py ~/.cache/screenstudio-cursors
```

Style flags, used in every render below:

```bash
--fps 60 --cursor --cursor-scale 1.0 --cursor-zoom \
  --cursor-set "$HOME/.cache/screenstudio-cursors" --click-press --cursor-idle-fade 2.5 \
  --cursor-spring 470,70,3 --wallpaper "Ventura Graphic" --bg-blur 40 \
  --pad 0.025 --radius 12 --width 1920
```

The pointer must be visible with its clicks; a recording without them gets redone.

### Highlight (PR demos, release highlights)

Slow enough to follow one idea at a time.

- Real speed, no `--speedup`: pauses stay so the viewer sees things load and update. Cut dead
  time only at the ends (`--trim-in`/`--trim-out`) or by keeping the script tight.
- One action per step, then hold ~1-1.5 s on the result before the next move.
- Moderate zoom, hand-written regions at ~1.4-1.8x on the area being changed (auto-zoom tends
  to land at 2.6x and on sidebar clicks). Pull back out between unrelated steps.
- `--keys` only when the typed text matters (a formula, a name the viewer must read).
- A short caption per step when the action alone doesn't explain itself ("The sum can't run
  on text anymore"), written as a `caption` event at the step (see below). A few words,
  sentence case, no trailing period on fragments.
- 15-45 s per clip. For a release summary, render each highlight separately with the same
  style and concatenate them.

```bash
python3 src/render.py src.mp4 --regions regions.json --events events.jsonl --out demo.mp4 \
  --fps 60 --cursor --cursor-scale 1.0 --cursor-zoom \
  --cursor-set "$HOME/.cache/screenstudio-cursors" --click-press --cursor-idle-fade 2.5 \
  --cursor-spring 470,70,3 --wallpaper "Ventura Graphic" --bg-blur 40 \
  --pad 0.025 --radius 12 --width 1920
```

### Walkthrough (long tours of many features)

Fast and dense, closer to a product video.

- The whole timeline at 2x: `--speed-segments '[{"t0":0,"t1":DUR,"speed":2}]'` with the
  source duration as `DUR`.
- Camera zoomed most of the time (~1.5-2x), following groups of clicks; short holds. Open on a
  zoomed hero shot, then pull out.
- No `--keys`: the chips overwhelm at this pace. Captions only to name each feature as it
  starts, with a longer `dur` so they're readable at 2x.

```bash
python3 src/render.py src.mp4 --regions regions.json --events events.jsonl --out walkthrough.mp4 \
  --speed-segments '[{"t0":0,"t1":DUR,"speed":2}]' \
  --fps 60 --cursor --cursor-scale 1.0 --cursor-zoom \
  --cursor-set "$HOME/.cache/screenstudio-cursors" --click-press --cursor-idle-fade 2.5 \
  --cursor-spring 470,70,3 --wallpaper "Ventura Graphic" --bg-blur 40 \
  --pad 0.025 --radius 12 --width 1920
```

### Scripted browser demos

`events-log` reads OS input, so a browser driven by an agent leaves it empty. Instead, drive
the flow with a throwaway Playwright script (`video: { mode: 'on', size }`, 1920x1080) and
write `events.jsonl` from the same script: header `{type:'header',display:{w,h},scale:1}`,
eased `move` events at ~60 Hz with `cursor` set from `getComputedStyle(el).cursor` of the
hovered element, `down`/`up` with the element's `bbox`, `key` events while typing, and a
`{type:'caption', text}` event at each step that needs an explanation (optional `dur` in
seconds, `anchor`). The renderer shows captions at the right moment after trims and
speed-ups, one at a time.
Timestamps relative to the start of the test line up with the video. Convert the webm to
mp4 (`ffmpeg -i in.webm -r 25 src.mp4`) before rendering, and trim the page load with
`--trim-in`.

What made the difference in practice:

- **Helpers.** Three small ones carry the whole script: `travel(x, y, ms)` moves the mouse
  along an eased path and logs a `move` per step; `clickOn(locator, action)` travels to the
  element's center, pauses briefly, logs `down` with its `bbox`, runs the action and logs
  `up`; `rest(ms)` holds so loading stays visible. Log each `move` *after*
  `page.mouse.move`, so the cursor type read for it is the one under the pointer.
- **Cursor type.** Resolve it with `page.evaluate` + `document.elementFromPoint`, and descend
  into same-origin iframes (editor canvases live in one) by subtracting the iframe's rect.
  `auto` means the browser decides: report `text` over inputs, textareas and
  contenteditable, `default` elsewhere. Read it again ~120 ms after each click, so a menu or
  popover opening under the pointer updates the type.
- **Seed through the API, not the UI.** Create the data the demo needs before recording
  starts, so the video opens on the interesting state.
- **Mark the start.** Write the time the first real frame is ready (after the page settles)
  and pass it as `--trim-in`.
- **Regions use recording time.** Read click times from `events.jsonl` and write regions
  around each group of clicks. Merge groups less than ~2 s apart into one region; zooming
  out and back in between them reads as a jolt.
- **Review.** Before showing it, pull 4-8 frames at the key moments into a contact sheet
  and check framing, cursor type and captions. Stills don't show motion, so still ask for
  the video-model critique below; when no video model is available, say it was skipped.
- **Clean up.** The spec, its artifacts and any test environment started for it are
  throwaway; remove them once the video is rendered.

## Changing this skill

- Checks for the render options: `python3 test/test_cursor.py` (no extra dependencies).
  Validate visual changes on the fixture (`test/make-fixture.py`) before real footage.
- Commit straight to `main`. The installed plugin only updates when
  `.claude-plugin/plugin.json`'s `version` changes: bump it, push, then
  `claude plugin marketplace update screenstudio-alt` and
  `claude plugin update screenstudio-alt@screenstudio-alt` (takes effect in new sessions).
- Commands in this file run in zsh, which doesn't split `$VARS` into words: write flags out
  in full instead of collecting them in a variable.
- Never commit Screen Studio's or Apple's artwork; read it from the local apps at render
  time (as `src/screenstudio-cursors.py` and `--wallpaper` do).

## Gotchas (learned the hard way, kept here so they're not relearned)

- ffmpeg CANNOT do animated `scale=eval=frame` → `crop` (link reinit wedges crop's
  per-frame exprs). That's why zoom uses `zoompan` (no `t` var there — use `on/FPS`).
- This machine's ffmpeg lacks `drawtext`; all text/cursor overlays are PIL-rendered
  PNGs + `overlay`.
- Test rig: `make-fixture.py` synthesizes a fake screen recording + ground-truth
  events.jsonl — validate any change against it before trusting real footage.
- Do NOT use Playwright `recordVideo` to capture the studio demo — its VFR→CFR
  conversion judders on the auto-zoom (a frozen frame wedged mid-motion); use
  `test/record-demo.js` instead. This is about
  capturing the studio's own animated zoom. Recording an app with Playwright's video for a
  scripted demo is fine: that footage has no camera moves, and `render.py` adds them later
  on a steady clock.

## Recording the demo

- `test/record-demo.js` is the canonical smooth demo recorder: it steps the studio's
  logical timeline frame-by-frame against the live page (not `recordVideo`), so every
  output frame is captured exactly once → perfect CFR, no judder. See
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for mechanism + usage.

## Text callouts / keystroke chips — NEVER overlap or crowd

Callouts are read one at a time. **Two text callouts must never overlap in output time, and
must not be closely spaced** — only one on screen at a time, with a clear gap (~0.3s+) between
them so each is legible before the next appears. Rules:

- **Anchor callouts CLEAR of the content they describe** — don't park them on top of the search
  bar, nav, or the result/image being shown. A callout covering the thing it points at is worse
  than none.
- **On long enough to read** — ≥~1s of *output* time at the playback rate. Over a sped-up span,
  **extend the callout's window** so it survives the compression (a callout inside a 5× block is
  gone in a blink otherwise).
- Time the callout to **lead or coincide with** the moment it labels, never trail it.

(Burn 2026-06-18: five callouts set with overlapping windows, sitting on top of the results, too
brief over a sped-up idle — read as clutter; the features didn't register.)

## Get an objective critique — send the rendered demo to a VIDEO model (don't iterate blind)

Before handing a demo over, **stop judging it from stills — send the actual rendered mp4 to a
video-understanding model and act on its critique.** Repeatedly, demos shipped with broken
framing/pacing/loop because they were judged frame-by-frame, not as motion. Standing practice:

1. Render the cut (`render.py`).
2. **Pick the model dynamically — do NOT hardcode one.** At this moment, list the current
   video-understanding (video-to-text) models with `fal search_models category="video-to-text"`
   (use this, NOT `recommend_model` — that one is popularity-ranked and returns video *generators*
   for a "video" task), look at what's actually available right now, and choose the
   strongest one for *this* job (a critique needs temporal/motion reasoning, so prefer a
   reasoning-capable VLM; e.g. `openrouter/router/video` pointed at the latest Gemini, or a
   native reasoning VLM like `nvidia/nemotron-3-nano-omni/video`). The right model changes over
   time — decide from the live list, not from a name written here. **Bias slightly toward SOTA:**
   when options are close, prefer the newest-generation / most-capable model (cost here is pennies,
   so favor capability over the cheap/older pick).
3. Upload the mp4 and run the chosen model with a **harsh-critique `prompt`** that states the
   demo's PURPOSE + the 4 features + the region/speed/callout spec and asks for a **blunt,
   timestamped, prioritized fix list** covering: each zoom's framing (on the right thing? on dead
   UI?), pan smoothness (eased vs hard-cut), speed-up legibility (feature vs glitch), callout
   placement/timing/overlap, overall pacing, and **clean loop (last frame ≈ first)**. A stills-only
   fallback (image VQA on a labeled contact sheet) **cannot judge motion**, so it's a weak
   substitute, not the check.

This loop catches what self-review misses (e.g. Gemini flagged a broken loop + a hard-cut "pan" +
a zoom landing on the Search button, all of which had passed self-inspection). Don't skip it for a
demo that's going public.
