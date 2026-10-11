"""Build a character/object turnaround sheet and drop it into Photoshop.

    python turnaround_sheet.py MODEL.ma
    python turnaround_sheet.py front.png three_quarter.png side.png
    python turnaround_sheet.py MODEL.mb --views 8 --dpi 300 --send

Inputs may be mixed:
  * images  (PNG / JPG / BMP / TGA / GIF) - each becomes one view;
  * 3D files (Maya ``.ma`` / ``.mb`` or ``.obj``) - rendered from the chosen
    rotation angles with a small software renderer, so no Maya render setup
    (lights, cameras, Arnold) is required - see ``model_import.py``.

A conventional turnaround is laid out left-to-right in rotation order on a
shared ground line: FRONT, 3/4, SIDE, 3/4 BACK, BACK. Every view is drawn at
one scale on a clean white background with a small caption under each pose and
an optional header, matching standard model-sheet practice.

The finished sheet is a single image placed as ONE layer in an 11x17in (or
11x17 portrait) Photoshop document. ``--send`` uses ``photoshop_bridge.py`` and
launches Photoshop if it is not already open (Windows via COM, macOS via
AppleScript). Everything else - building the sheet - is cross-platform.
"""

import argparse
import atexit
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import pygame

import model_import

HERE = Path(__file__).resolve().parent
OUT_DEFAULT = HERE / "turnaround_sheet.png"

SHEET_IN = {"landscape": (17.0, 11.0), "portrait": (11.0, 17.0)}
DEFAULT_DPI = 150
DEFAULT_TEXT_SIZE_IN = 0.20   # default height of a user text box, in inches

MARGIN_X_IN = 0.55          # left/right sheet margin
TOP_IN = 0.80               # header band
BOTTOM_IN = 1.00            # room below the ground line for captions
GAP_FRAC = 0.16             # gap between slots, as a fraction of slot width
FILL = 0.96                 # how much of the figure band a view may fill
SS = 2                      # supersample factor (anti-aliasing)

AMBIENT = 0.44              # flat shading, softened like a studio turnaround
DIFFUSE = 0.70
LIGHT_LOCAL = (-0.35, 0.55, -0.72)   # key light in (right, up, fwd) view space

# cross-platform sans list (pygame picks the first available)
FONT_CANDIDATES = ("Segoe UI,segoeui,Helvetica Neue,helvetica,Helvetica,"
                   "Arial,arial,DejaVu Sans,dejavusans,Liberation Sans,"
                   "liberation sans,Noto Sans,notosans,FreeSans,freesans")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".gif", ".webp"}
MODEL_EXTS = {".ma", ".mb", ".obj"}
PSD_EXTS = {".psd", ".psb"}          # flattened via Photoshop into temp PNGs
ALL_EXTS = IMAGE_EXTS | MODEL_EXTS | PSD_EXTS

# rotation order: full 360 turn, front first (azimuth 0 = camera on +Z)
ANGLE_SETS = {
    3: [("FRONT", 0), ("SIDE", 90), ("BACK", 180)],
    4: [("FRONT", 0), ("3/4", 45), ("SIDE", 90), ("BACK", 180)],
    5: [("FRONT", 0), ("3/4", 45), ("SIDE", 90), ("3/4 BACK", 135), ("BACK", 180)],
    8: [("FRONT", 0), ("45", 45), ("SIDE", 90), ("135", 135), ("BACK", 180),
        ("225", 225), ("270", 270), ("315", 315)],
}

DOC_NAME = "Turnaround Sheet"
LAYER_NAME = "Turnaround"


# --------------------------------------------------------------------------- #
# tiny vector helpers (plain tuples; no numpy here)
# --------------------------------------------------------------------------- #
def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    m = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / m, a[1] / m, a[2] / m)


def _view_basis(az_deg, el_deg):
    """Return (right, up, fwd, light) for an orbiting camera (orthographic)."""
    az, el = math.radians(az_deg), math.radians(el_deg)
    off = (math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))
    fwd = _mul(off, -1.0)                    # camera looks toward the model
    right = _norm(_cross(fwd, (0.0, 1.0, 0.0)))
    up = _cross(right, fwd)
    rl, ul, fl = LIGHT_LOCAL                 # key light fixed to the view
    light = _norm(_add(_add(_mul(right, rl), _mul(up, ul)), _mul(fwd, fl)))
    return right, up, fwd, light


# --------------------------------------------------------------------------- #
# model loading + rendering
# --------------------------------------------------------------------------- #
def load_model_faces(path):
    """A 3D file -> faces, centered on the floor and normalised to unit-ish."""
    faces, _summary = model_import.load_model(path)
    return model_import.fit_to_view(faces)


def _bounds(faces):
    xs, ys, zs = [], [], []
    for pts, _ in faces:
        for p in pts:
            xs.append(p[0])
            ys.append(p[1])
            zs.append(p[2])
    if not xs:
        raise ValueError("model has no faces")
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def model_center(faces):
    lo, hi = _bounds(faces)
    return ((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, (lo[2] + hi[2]) / 2.0)


def project_extents(faces, center, az, el):
    """(umin, umax, vmin, vmax) of the model's outlines at unit scale."""
    right, up, _fwd, _light = _view_basis(az, el)
    umin = vmin = 1e18
    umax = vmax = -1e18
    for pts, _ in faces:
        for p in pts:
            rel = _sub(p, center)
            u, v = _dot(rel, right), _dot(rel, up)
            umin, umax = min(umin, u), max(umax, u)
            vmin, vmax = min(vmin, v), max(vmax, v)
    return umin, umax, vmin, vmax


def render_model_view(faces, center, scale, az, el, pad=8, ss=SS):
    """Render one rotation of a model to a tightly-cropped RGBA surface."""
    right, up, fwd, light = _view_basis(az, el)
    polys = []
    minx = miny = 1e18
    maxx = maxy = -1e18
    for pts, color in faces:
        if len(pts) < 3:
            continue
        n = _norm(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])))
        lit = AMBIENT + DIFFUSE * abs(_dot(n, light))
        col = (min(255, int(color[0] * 255 * lit)),
               min(255, int(color[1] * 255 * lit)),
               min(255, int(color[2] * 255 * lit)))
        screen, depth = [], 0.0
        for p in pts:
            rel = _sub(p, center)
            x = _dot(rel, right) * scale
            y = -_dot(rel, up) * scale
            screen.append((x, y))
            depth += _dot(rel, fwd)
            minx, maxx = min(minx, x), max(maxx, x)
            miny, maxy = min(miny, y), max(maxy, y)
        polys.append((screen, depth / len(pts), col))

    if minx > maxx:                                   # nothing drawable
        return pygame.Surface((8, 8), pygame.SRCALPHA)

    w = max(2, int(math.ceil(maxx - minx)) + 2 * pad)
    h = max(2, int(math.ceil(maxy - miny)) + 2 * pad)
    surf = pygame.Surface((w * ss, h * ss), pygame.SRCALPHA)
    ox, oy = -minx + pad, -miny + pad
    for screen, _depth, col in sorted(polys, key=lambda t: -t[1]):
        pygame.draw.polygon(
            surf, col, [((x + ox) * ss, (y + oy) * ss) for x, y in screen])
    if ss > 1:
        surf = pygame.transform.smoothscale(surf, (w, h))
    return surf


def load_image(path):
    surf = pygame.image.load(str(path))
    if surf.get_alpha() is None and surf.get_flags() & pygame.SRCALPHA == 0:
        return surf
    return surf


# --------------------------------------------------------------------------- #
# sheet layout + compositing
# --------------------------------------------------------------------------- #
def _font(size, bold=False, face=None):
    pygame.font.init()
    return pygame.font.SysFont(face or FONT_CANDIDATES, size, bold=bold)


def text_font_for(size_in, px_per_inch, bold=False, face=None):
    """The font a text box of ``size_in`` inches tall would use on a surface."""
    return _font(max(8, int(round(size_in * px_per_inch))), bool(bold), face)


def draw_texts(surface, texts, px_per_inch):
    """Stamp free-floating text boxes onto ``surface``.

    Each item is a dict: ``{"text", "x", "y", "size_in", "bold", "color",
    "font"}`` where ``x``/``y`` are fractions (0..1) of the surface and mark the
    centre of the line, and ``font`` is an optional SysFont name list. Used by
    both the finished sheet (px_per_inch = dpi) and the GUI preview
    (px_per_inch = dpi * preview scale), so they always match.
    """
    if not texts:
        return surface
    w, h = surface.get_size()
    for item in texts:
        text = str(item.get("text", ""))
        if not text:
            continue
        f = text_font_for(item.get("size_in", DEFAULT_TEXT_SIZE_IN),
                          px_per_inch, item.get("bold"), item.get("font"))
        img = f.render(text, True, tuple(item.get("color", (33, 35, 40))))
        surface.blit(img, img.get_rect(
            center=(int(item.get("x", 0.5) * w), int(item.get("y", 0.5) * h))))
    return surface


PS_PSD_JSX = """
app.displayDialogs = DialogModes.NO;
var inFile = new File(%s);
var outFile = new File(%s);
outFile.encoding = "BINARY";
var doc = app.open(inFile);
__result__ = "";
try {
    try { if (doc.mode !== DocumentMode.RGB) doc.changeMode(ChangeMode.RGB); } catch (e0) {}
    try {
        if (doc.bitsPerChannel !== BitsPerChannelType.EIGHT)
            doc.bitsPerChannel = BitsPerChannelType.EIGHT;
    } catch (e1) {}
    var opts = new PNGSaveOptions();
    opts.interlaced = false;
    doc.saveAs(outFile, opts, true, Extension.LOWERCASE);
    __result__ = "ok";
} catch (e) {
    __result__ = "ERROR " + e;
} finally {
    try { doc.close(SaveOptions.DONOTSAVECHANGES); } catch (e2) {}
}
"""

_PSD_TMPDIR = None
_PSD_CACHE = {}


def _psd_tmpdir():
    global _PSD_TMPDIR
    if _PSD_TMPDIR is None:
        _PSD_TMPDIR = Path(tempfile.mkdtemp(prefix="turnaround_psd_"))
        atexit.register(lambda: shutil.rmtree(str(_PSD_TMPDIR),
                                              ignore_errors=True))
    return _PSD_TMPDIR


def flatten_psd(path):
    """Export a .psd/.psb composite to a cached temp PNG via Photoshop.

    Opening a PSD needs Photoshop, so this reuses ``photoshop_bridge`` (which
    attaches to a running Photoshop or launches one). The flattened PNG is
    cached by path+mtime+size so repeat builds do not re-open the file.
    """
    p = Path(path).resolve()
    st = p.stat()
    key = (str(p), int(st.st_mtime), st.st_size)
    hit = _PSD_CACHE.get(key)
    if hit is not None and hit.exists():
        return hit
    try:
        import photoshop_bridge
    except Exception as exc:                                   # noqa: BLE001
        raise ValueError("Photoshop bridge unavailable: %s" % exc)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in p.stem)[:40]
    out = _psd_tmpdir() / ("%s_%d.png" % (safe, abs(hash(key)) % 100000000))
    payload = PS_PSD_JSX % (json.dumps(str(p).replace("\\", "/")),
                            json.dumps(str(out).replace("\\", "/")))
    text = photoshop_bridge.run(payload)
    if not out.exists():
        msg = next((ln for ln in text.splitlines() if "__result__" in ln), "")
        raise ValueError("could not open %s in Photoshop: %s"
                         % (p.name, (msg or text).strip()[:200]))
    _PSD_CACHE[key] = out
    return out


def _expand(inputs, angle_set):
    """Flatten the inputs into ordered slots: (kind, payload, label)."""
    slots = []
    for path in inputs:
        p = Path(path)
        ext = p.suffix.lower()
        if ext in IMAGE_EXTS:
            slots.append(("image", load_image(p), p.stem))
        elif ext in PSD_EXTS:
            slots.append(("image", load_image(flatten_psd(p)), p.stem))
        elif ext in MODEL_EXTS:
            faces = load_model_faces(p)
            center = model_center(faces)
            for label, az in angle_set:
                slots.append(("model", (faces, center, az), label))
        else:
            raise ValueError("unsupported input: %s" % p.name)
    return slots


def build_sheet(inputs, views=5, orientation="landscape", dpi=DEFAULT_DPI,
                title="", elevation=8.0, bg=(255, 255, 255), texts=None):
    """Compose every view onto one sheet. Returns (surface, info-dict)."""
    if views not in ANGLE_SETS:
        raise ValueError("views must be one of %s" % sorted(ANGLE_SETS))
    win, hin = SHEET_IN[orientation]
    W, H = int(round(win * dpi)), int(round(hin * dpi))
    margin_x = int(MARGIN_X_IN * dpi)
    baseline_y = H - int(BOTTOM_IN * dpi)
    fig_h = baseline_y - int(TOP_IN * dpi)
    target_fig_h = int(fig_h * FILL)

    slots = _expand(inputs, ANGLE_SETS[views])
    n = len(slots)
    if n == 0:
        raise ValueError("no inputs produced any views")
    slot_w = (W - 2 * margin_x) / float(n)
    avail_w = slot_w * (1.0 - GAP_FRAC)

    # one shared scale for every 3D view (turnarounds are same-scale)
    model_extents = [project_extents(s[1][0], s[1][1], s[1][2], elevation)
                     for s in slots if s[0] == "model"]
    model_scale = None
    if model_extents:
        base_h = max(e[3] - e[2] for e in model_extents) or 1.0
        max_w = max(e[1] - e[0] for e in model_extents) or 1.0
        model_scale = min(target_fig_h / base_h, avail_w / max_w)

    sheet = pygame.Surface((W, H))
    sheet.fill(bg)

    if title:
        tfont = _font(max(14, int(0.30 * dpi)), bold=True)
        label = tfont.render(title, True, (38, 40, 46))
        sheet.blit(label, label.get_rect(center=(W // 2, int(0.36 * dpi))))

    pygame.draw.line(sheet, (206, 208, 213),
                     (margin_x, baseline_y), (W - margin_x, baseline_y),
                     max(1, int(0.012 * dpi)))

    cap_font = _font(max(11, int(0.15 * dpi)), bold=False)
    for i, (kind, payload, text) in enumerate(slots):
        cx = margin_x + slot_w * (i + 0.5)
        if kind == "model":
            faces, center, az = payload
            view = render_model_view(faces, center, model_scale, az, elevation)
        else:
            img = payload
            sc = min(target_fig_h / img.get_height(), avail_w / img.get_width())
            view = pygame.transform.smoothscale(
                img, (max(1, int(round(img.get_width() * sc))),
                      max(1, int(round(img.get_height() * sc)))))
        sheet.blit(view, (int(cx - view.get_width() / 2.0),
                          baseline_y - view.get_height()))
        if text:
            cap = cap_font.render(text.upper(), True, (90, 92, 99))
            sheet.blit(cap, cap.get_rect(
                center=(int(cx), baseline_y + int(0.17 * dpi))))

    draw_texts(sheet, texts, dpi)

    info = {"size": (W, H), "dpi": dpi, "views": n, "orientation": orientation,
            "sheet_in": (win, hin)}
    return sheet, info


# --------------------------------------------------------------------------- #
# Photoshop hand-off
# --------------------------------------------------------------------------- #
PS_JSX = """app.displayDialogs = DialogModes.NO;
var docName = "%s";
var layerName = "%s";
var path = "%s";
var oldUnits = app.preferences.rulerUnits;
app.preferences.rulerUnits = Units.PIXELS;
for (var i = app.documents.length - 1; i >= 0; i--) {
    if (app.documents[i].name === docName) {
        app.documents[i].close(SaveOptions.DONOTSAVECHANGES);
    }
}
var doc = app.documents.add(%d, %d, %s, docName,
    NewDocumentMode.RGB, DocumentFill.WHITE);
app.preferences.rulerUnits = oldUnits;
var src = app.open(File(path));
app.activeDocument = src;
var placed = src.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
app.activeDocument = doc;
placed.name = layerName;
try {                                      // one layer only (sheet has white bg)
    if (doc.layers.length > 1) doc.layers.getByName("Background").remove();
} catch (e) {}
app.activeDocument = src;
src.close(SaveOptions.DONOTSAVECHANGES);
app.activeDocument = doc;
__result__ = "turnaround: " + doc.name + " | " + doc.width.value + "x" +
    doc.height.value + " px @ " + doc.resolution + " ppi | layer: " + placed.name;
"""


def send_to_photoshop(png, info, doc_name=DOC_NAME, layer_name=LAYER_NAME):
    """Place the sheet PNG as a single layer in an 11x17in Photoshop doc."""
    W, H = info["size"]
    payload = PS_JSX % (doc_name, layer_name,
                        str(png).replace("\\", "/"), W, H, info["dpi"])
    try:
        import photoshop_bridge
        text = photoshop_bridge.run(payload).strip()
    except Exception as exc:                                  # noqa: BLE001
        return False, "Photoshop error: %s" % exc
    line = next((ln for ln in text.splitlines() if ln.startswith("__result__")),
                text)
    return "BRIDGE ERROR" not in text, line


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build a turnaround sheet and place it in Photoshop.")
    ap.add_argument("inputs", nargs="+",
                    help="images (png/jpg/bmp/tga/gif/webp), Photoshop "
                         "(psd/psb) and/or 3D files (ma/mb/obj)")
    ap.add_argument("--views", type=int, default=5, choices=sorted(ANGLE_SETS),
                    help="rotation angles rendered per 3D input (default 5)")
    ap.add_argument("--orientation", choices=sorted(SHEET_IN),
                    default="landscape", help="11x17 landscape or portrait")
    ap.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    ap.add_argument("--title", default="", help="header text on the sheet")
    ap.add_argument("--elevation", type=float, default=8.0,
                    help="camera elevation in degrees (default 8)")
    ap.add_argument("--out", default=str(OUT_DEFAULT), help="output PNG path")
    ap.add_argument("--send", action="store_true",
                    help="also place the sheet in Photoshop (one layer)")
    ap.add_argument("--doc-name", default=DOC_NAME)
    ap.add_argument("--layer-name", default=LAYER_NAME)
    a = ap.parse_args(argv)

    for raw in a.inputs:
        if Path(raw).suffix.lower() not in ALL_EXTS:
            ap.error("unsupported input: %s" % raw)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    sheet, info = build_sheet(a.inputs, a.views, a.orientation, a.dpi,
                              a.title, a.elevation)
    out = Path(a.out)
    pygame.image.save(sheet, str(out))
    print("wrote %s  (%dx%d px @ %d ppi, %d views, %dx%d in)"
          % (out, info["size"][0], info["size"][1], info["dpi"],
             info["views"], info["sheet_in"][0], info["sheet_in"][1]))

    if a.send:
        ok, msg = send_to_photoshop(out, info, a.doc_name, a.layer_name)
        print("[photoshop] %s" % msg)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
