"""Turnaround Studio - a Frutiger Aero GUI for turnaround_sheet.py.

    python turnaround_gui.py

Pick one or more source files (images and/or Maya .ma/.mb / .obj), choose how
many rotation views, orientation, DPI and a title, then build a preview and drop
the finished 11x17in sheet into Photoshop as a single layer.

The look is "Frutiger Aero": glossy glass panels, an aqua sky-to-water gradient
and soft highlights. It reuses ``turnaround_sheet`` for all the actual work, so
the GUI and the command line stay in sync.

Cross-platform: Windows, macOS and Linux all run the GUI and build sheets (fonts
and the Maya lookup adapt per OS). Sending to Photoshop needs Windows or macOS.
"""

from pathlib import Path

import pygame

import turnaround_sheet as ts

HERE = Path(__file__).resolve().parent
OUT = ts.OUT_DEFAULT
WINDOW = (1120, 820)

# --------------------------------------------------------------------------- #
# palette
# --------------------------------------------------------------------------- #
SKY_TOP = (150, 214, 255)
WATER = (128, 226, 205)
INK = (28, 46, 66)
INK_SOFT = (58, 82, 108)
WHITE = (255, 255, 255)
AQUA = (0, 158, 214)
AQUA_DEEP = (0, 120, 178)
GREEN = (46, 190, 150)
VIOLET = (120, 90, 210)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".gif", ".webp"}
MODEL_EXTS = {".ma", ".mb", ".obj"}
PSD_EXTS = {".psd", ".psb"}          # opened/flattened through Photoshop

# cross-platform sans list (pygame picks the first available)
FONT_CANDIDATES = ("Segoe UI,segoeui,Helvetica Neue,helvetica,Helvetica,"
                   "Arial,arial,DejaVu Sans,dejavusans,Liberation Sans,"
                   "liberation sans,Noto Sans,notosans,FreeSans,freesans")

# selectable text-box faces (pygame picks the first available in each list)
FONT_FACES = {
    "Sans": FONT_CANDIDATES,
    "Serif": ("Georgia,Times New Roman,Times,DejaVu Serif,liberation serif,"
              "Noto Serif,FreeSerif,serif"),
    "Mono": ("Consolas,Courier New,Courier,DejaVu Sans Mono,liberation mono,"
             "Noto Sans Mono,FreeMono,monospace"),
}
FONT_ORDER = ["Sans", "Serif", "Mono"]

TEXT_MIN_IN = 0.08            # smallest text-box height (inches)
TEXT_MAX_IN = 0.60            # largest text-box height (inches)

IMAGE_SCALE_MIN = 0.25        # image-scale slider range (25%..500%)
IMAGE_SCALE_MAX = 5.0

_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    f = _fonts.get(key)
    if f is None:
        f = pygame.font.SysFont(FONT_CANDIDATES, size, bold=bold)
        _fonts[key] = f
    return f


def _tk_dialog():
    """Return the tkinter filedialog module, or None if tk is unavailable."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:                                  # noqa: BLE001
        return None
    return tk, filedialog


# --------------------------------------------------------------------------- #
# drawing helpers
# --------------------------------------------------------------------------- #
def lerp(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def brighten(c, k):
    return lerp(c, (255, 255, 255), k)


def darken(c, k):
    return lerp(c, (0, 0, 0), k)


def vgrad(surf, rect, top, bottom):
    rect = pygame.Rect(rect)
    for y in range(rect.height):
        k = y / max(1, rect.height - 1)
        pygame.draw.line(surf, lerp(top, bottom, k),
                         (rect.x, rect.y + y), (rect.right, rect.y + y))


def rounded(size, radius, color):
    s = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(s, color, s.get_rect(), border_radius=radius)
    return s


def glass_panel(size, radius=18, tint=(255, 255, 255, 64)):
    """A frosted glass panel with a glossy top and a bright rim."""
    w, h = size
    s = pygame.Surface(size, pygame.SRCALPHA)
    shadow = pygame.Surface((w + 24, h + 24), pygame.SRCALPHA)
    for i in range(12, 0, -1):
        a = int(46 * (1 - i / 12.0))
        pygame.draw.rect(shadow, (18, 54, 78, a),
                         (12 - i, 12 - i, w + 2 * i, h + 2 * i),
                         border_radius=radius + i)
    s.blit(shadow, (-12, -12))
    pygame.draw.rect(s, tint, (0, 0, w, h), border_radius=radius)
    gloss = pygame.Surface((w - 10, max(6, h // 2)), pygame.SRCALPHA)
    pygame.draw.rect(gloss, (255, 255, 255, 66),
                     gloss.get_rect(), border_radius=radius)
    s.blit(gloss, (5, 4))
    pygame.draw.rect(s, (255, 255, 255, 175), (0, 0, w, h), width=2,
                     border_radius=radius)
    return s


def glossy_button(size, radius, base, hover=False, selected=False):
    """A pill-shaped, jelly-like button with a glass highlight."""
    w, h = size
    s = pygame.Surface(size, pygame.SRCALPHA)
    top = brighten(base, 0.55 if not hover else 0.72)
    bot = darken(base, 0.18)
    grad = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        pygame.draw.line(grad, lerp(top, bot, y / max(1, h - 1)),
                         (0, y), (w, y))
    grad.blit(rounded((w, h), radius, (255, 255, 255, 255)),
              (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(grad, (0, 0))
    hl = pygame.Surface((w - 8, max(4, h // 2 - 2)), pygame.SRCALPHA)
    pygame.draw.rect(hl, (255, 255, 255, 105 if hover else 85),
                     hl.get_rect(), border_radius=radius)
    s.blit(hl, (4, 4))
    rim = (255, 255, 255, 220) if (hover or selected) else (255, 255, 255, 150)
    pygame.draw.rect(s, rim, (0, 0, w, h), width=2, border_radius=radius)
    if selected:
        pygame.draw.rect(s, (255, 255, 255, 130), (2, 2, w - 4, h - 4),
                         width=1, border_radius=radius)
    return s


def text_shadow(surf, txt, f, color, pos, center=False, sh=(10, 30, 50),
                shadow=True):
    img = f.render(txt, True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    if shadow:
        surf.blit(f.render(txt, True, sh), (rect.x + 1, rect.y + 2))
    surf.blit(img, rect)
    return rect


# --------------------------------------------------------------------------- #
# widgets
# --------------------------------------------------------------------------- #
class Button:
    def __init__(self, rect, label, callback, base=AQUA, tfont=None,
                 selected=None, radius=13):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.base = base
        self.tfont = tfont or font(17, True)
        self.selected = selected          # callable -> bool
        self.radius = radius
        self.hover = False
        self.pressed = False

    def draw(self, surf):
        sel = bool(self.selected and self.selected())
        surf.blit(glossy_button(self.rect.size, self.radius, self.base,
                                hover=self.hover, selected=sel), self.rect)
        text_shadow(surf, self.label, self.tfont, WHITE, self.rect.center,
                    center=True)

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.pressed and self.rect.collidepoint(event.pos):
                self.callback()
            self.pressed = False


class Slider:
    """A flat horizontal slider for a numeric value (value_fn/set_fn can be
    disabled by having value_fn() return None)."""

    def __init__(self, rect, value_fn, set_fn, lo, hi):
        self.rect = pygame.Rect(rect)
        self.value_fn = value_fn
        self.set_fn = set_fn
        self.lo, self.hi = lo, hi
        self.dragging = False

    def _value(self):
        return self.value_fn()

    def _knob_x(self):
        v = self._value()
        if v is None:
            return None
        t = (v - self.lo) / float(self.hi - self.lo)
        t = min(1.0, max(0.0, t))
        return int(self.rect.x + 8 + t * (self.rect.width - 16))

    def _set_from_x(self, x):
        t = (x - (self.rect.x + 8)) / float(max(1, self.rect.width - 16))
        t = min(1.0, max(0.0, t))
        self.set_fn(self.lo + t * (self.hi - self.lo))

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.inflate(0, 16).collidepoint(event.pos):
                if self._value() is None:
                    return
                self.dragging = True
                self._set_from_x(event.pos[0])
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from_x(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False

    def draw(self, surf):
        r = self.rect
        tr = pygame.Rect(r.x, r.centery - 3, r.width, 6)
        pygame.draw.rect(surf, (255, 255, 255, 170), tr, border_radius=3)
        kx = self._knob_x()
        if kx is None:
            pygame.draw.rect(surf, (176, 186, 196, 190), tr, border_radius=3)
            return
        pygame.draw.rect(surf, (0, 150, 205, 255),
                         (tr.x, tr.y, kx - tr.x, tr.height), border_radius=3)
        pygame.draw.circle(surf, (255, 255, 255, 255), (kx, r.centery), 9)
        pygame.draw.circle(surf, (0, 120, 178, 255), (kx, r.centery), 9, 2)


# --------------------------------------------------------------------------- #
# app
# --------------------------------------------------------------------------- #
class App:
    FILE_PANEL = pygame.Rect(36, 100, 448, 356)
    OPT_PANEL = pygame.Rect(36, 472, 448, 300)
    PREV_PANEL = pygame.Rect(512, 100, 572, 366)
    LIST_AREA = pygame.Rect(52, 156, 416, 232)
    TITLE_FIELD = pygame.Rect(56, 506, 408, 32)
    SCALE_SLIDER = pygame.Rect(56, 748, 380, 14)
    PREVIEW_FRAME = pygame.Rect(530, 148, 536, 300)
    TEXT_PANEL = pygame.Rect(512, 476, 572, 112)
    STATUS_PANEL = pygame.Rect(512, 704, 572, 68)

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Turnaround Studio")
        self.screen = pygame.display.set_mode(WINDOW)
        self.clock = pygame.time.Clock()
        self.t = 0.0

        self.inputs = []
        self.selected = None
        self.views = 5
        self.orientation = "landscape"
        self.dpi = 150
        self.image_scale = 1.0
        self.flatten_psd = True
        self.title_text = ""
        self.title_focus = False

        self.texts = []                # free-floating text boxes on the sheet
        self.selected_text = None
        self.text_focus = False
        self.text_drag = None
        self.pan = (0.0, 0.0)          # preview pan offset from the frame centre
        self.panning = None
        self.font_key = FONT_ORDER[0]  # face new boxes use until one is selected

        self.sheet = None              # output sheet (at the canvas scale)
        self.info = None
        self.base_sheet = None         # 100% sheet used for the preview
        self.base_info = None
        self.preview = None
        self.status = "Add a source file to begin."
        self.status_ok = True
        self.busy = False
        self.running = True

        self._build_widgets()

    # ------------------------------------------------------------------ #
    def _build_widgets(self):
        self.buttons = [
            Button((52, 402, 150, 34), "Add file...", self.pick_files,
                   base=AQUA, tfont=font(15, True)),
            Button((212, 402, 130, 34), "Remove", self.remove_selected,
                   base=(110, 140, 170), tfont=font(15, True)),
            Button((350, 402, 130, 34), "Clear all", self.clear_all,
                   base=(150, 155, 165), tfont=font(15, True)),
            Button((512, 596, 210, 44), "Save PNG As...", self.save_as,
                   base=GREEN, tfont=font(16, True)),
            Button((734, 596, 188, 44), "Build preview", self.build,
                   base=AQUA, tfont=font(16, True)),
            Button((512, 648, 572, 46), "Send to Photoshop", self.send,
                   base=VIOLET, tfont=font(19, True)),
        ]
        self.buttons += [
            Button((60 + i * 56, 568, 48, 30), str(v),
                   (lambda v=v: self.set_views(v)),
                   selected=(lambda v=v: self.views == v), tfont=font(16, True))
            for i, v in enumerate((3, 4, 5, 8))
        ]
        self.buttons += [
            Button((60, 628, 118, 30), "Landscape",
                   lambda: self.set_orientation("landscape"),
                   selected=lambda: self.orientation == "landscape",
                   tfont=font(15, True)),
            Button((186, 628, 118, 30), "Portrait",
                   lambda: self.set_orientation("portrait"),
                   selected=lambda: self.orientation == "portrait",
                   tfont=font(15, True)),
        ]
        self.buttons += [
            Button((60, 688, 92, 30), "%d dpi" % d, (lambda d=d: self.set_dpi(d)),
                   selected=(lambda d=d: self.dpi == d), tfont=font(15, True))
            for d in (150, 300)
        ]
        self.scale_slider = Slider(self.SCALE_SLIDER,
                                   self._image_scale, self._set_image_scale,
                                   IMAGE_SCALE_MIN, IMAGE_SCALE_MAX)
        self.buttons.append(
            Button((self.OPT_PANEL.x + 300, self.OPT_PANEL.y + 8, 148, 26),
                   "Flatten PSD", self.toggle_flatten, base=VIOLET,
                   tfont=font(13, True),
                   selected=lambda: self.flatten_psd))
        P = self.TEXT_PANEL
        self.buttons += [
            Button((P.x + 16, P.y + 34, 108, 32), "Add Text", self.add_text,
                   base=AQUA, tfont=font(15, True)),
            Button((P.x + 130, P.y + 34, 108, 32), "Delete box",
                   self.delete_text, base=(158, 122, 148), tfont=font(15, True)),
            Button((P.x + 244, P.y + 34, 44, 32), "B", self.toggle_text_bold,
                   base=(110, 140, 170), tfont=font(17, True),
                   selected=lambda: (self.selected_text is not None
                                     and 0 <= self.selected_text < len(self.texts)
                                     and bool(self.texts[self.selected_text]
                                              .get("bold")))),
        ]
        self.buttons += [
            Button((P.x + 58 + i * 66, P.y + 72, 62, 30), name,
                   (lambda k=name: self.set_font(k)), base=(120, 170, 200),
                   selected=(lambda k=name: self._current_font_key() == k),
                   tfont=font(14, True))
            for i, name in enumerate(FONT_ORDER)
        ]
        self.size_slider = Slider((P.x + 300, P.y + 78, 168, 16),
                                  self._selected_size, self._set_selected_size,
                                  TEXT_MIN_IN, TEXT_MAX_IN)
        self.buttons.append(
            Button((WINDOW[0] - 58, 18, 44, 44), "X", self.request_close,
                   base=(216, 64, 64), tfont=font(22, True), radius=22))

    def request_close(self):
        self.running = False

    # ------------------------------------------------------------------ #
    # file handling
    # ------------------------------------------------------------------ #
    def pick_files(self):
        dlg = _tk_dialog()
        if dlg is None:
            self.status, self.status_ok = (
                "File dialog unavailable - tkinter is not installed.", False)
            return
        tk, filedialog = dlg
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:                              # noqa: BLE001
            pass
        paths = filedialog.askopenfilenames(
            title="Choose turnaround source files",
            filetypes=[("Turnaround sources",
                        "*.png *.jpg *.jpeg *.bmp *.tga *.gif *.webp "
                        "*.psd *.psb *.ma *.mb *.obj"),
                       ("Images", "*.png *.jpg *.jpeg *.bmp *.tga *.gif *.webp"),
                       ("Photoshop", "*.psd *.psb"),
                       ("Maya / OBJ", "*.ma *.mb *.obj"),
                       ("All files", "*.*")])
        root.destroy()
        if paths:
            self.add_files(paths)

    def add_files(self, paths):
        added = 0
        for p in paths:
            p = str(Path(p))
            if Path(p).suffix.lower() not in IMAGE_EXTS | MODEL_EXTS | PSD_EXTS:
                continue
            if p not in self.inputs:
                self.inputs.append(p)
                added += 1
        if added:
            self.selected = len(self.inputs) - 1
            self.status = "Added %d file(s)." % added
            self.status_ok = True

    def remove_selected(self):
        if self.selected is None or not self.inputs:
            return
        name = Path(self.inputs.pop(self.selected)).name
        self.selected = len(self.inputs) - 1 if self.inputs else None
        self.status, self.status_ok = "Removed %s." % name, True

    def clear_all(self):
        self.inputs = []
        self.selected = None
        self.status, self.status_ok = "Cleared. Add a source file.", True

    # ------------------------------------------------------------------ #
    def set_views(self, v):
        self.views = v

    def set_orientation(self, o):
        self.orientation = o

    def set_dpi(self, d):
        self.dpi = d

    def _image_scale(self):
        return self.image_scale

    def _set_image_scale(self, value):
        value = min(IMAGE_SCALE_MAX, max(IMAGE_SCALE_MIN, value))
        if abs(value - self.image_scale) < 1e-6:
            return
        self.image_scale = value
        self._make_preview()          # zoom the preview so the slider is visible
        w, h = ts.output_size(self.orientation, self.dpi, self.image_scale)
        self.status, self.status_ok = (
            "Canvas scale %d%% -> %dx%d px (%.0fx%.0f in)."
            % (int(round(value * 100)), w, h,
               w / float(self.dpi), h / float(self.dpi)), True)

    def toggle_flatten(self):
        self.flatten_psd = not self.flatten_psd
        self._refresh_preview()

    def _refresh_preview(self):
        """Rebuild sheet + preview without touching the status line or disk.

        Used by the Flatten PSD toggle. Only the 100% sheet (which drives the
        preview) is rebuilt here - the canvas-scaled output is rebuilt on save /
        send, so dragging options never builds a huge surface.
        """
        if not self.inputs or self.busy:
            return
        try:
            sheet, info = ts.build_sheet(
                self.inputs, self.views, self.orientation, self.dpi,
                self.title_text, elevation=8.0, image_scale=1.0,
                psd_layers=not self.flatten_psd)
        except Exception:                                  # noqa: BLE001
            return
        self.base_sheet, self.base_info = sheet, info
        self._make_preview()

    # ------------------------------------------------------------------ #
    # text boxes
    # ------------------------------------------------------------------ #
    def add_text(self):
        n = len(self.texts)
        self.texts.append({
            "text": "Text",
            "x": 0.5,
            "y": min(0.9, 0.34 + 0.09 * (n % 6)),
            "size_in": ts.DEFAULT_TEXT_SIZE_IN,
            "bold": False,
            "color": (33, 35, 40),
            "font_key": self.font_key,
            "font": FONT_FACES[self.font_key],
        })
        self.selected_text = len(self.texts) - 1
        self.title_focus = False
        self.text_focus = True
        self.status, self.status_ok = (
            "Text box added - drag it on the preview; type to edit.", True)

    def delete_text(self):
        if self.selected_text is None or not self.texts:
            self.status, self.status_ok = "No text box selected.", False
            return
        self.texts.pop(self.selected_text)
        self.selected_text = None
        self.text_focus = False
        self.status, self.status_ok = "Text box removed.", True

    def _resize_text(self, delta):
        if self.selected_text is None:
            return
        it = self.texts[self.selected_text]
        it["size_in"] = min(TEXT_MAX_IN, max(TEXT_MIN_IN,
                                              it.get("size_in",
                                                     ts.DEFAULT_TEXT_SIZE_IN)
                                              + delta))

    def text_bigger(self):
        self._resize_text(0.03)

    def text_smaller(self):
        self._resize_text(-0.03)

    def _current_font_key(self):
        if (self.selected_text is not None
                and 0 <= self.selected_text < len(self.texts)):
            it = self.texts[self.selected_text]
            return it.get("font_key", self.font_key)
        return self.font_key

    def set_font(self, key):
        if key not in FONT_FACES:
            return
        self.font_key = key
        if (self.selected_text is not None
                and 0 <= self.selected_text < len(self.texts)):
            it = self.texts[self.selected_text]
            it["font_key"] = key
            it["font"] = FONT_FACES[key]
            self.status, self.status_ok = ("Text font: %s." % key, True)
        else:
            self.status, self.status_ok = (
                "New text boxes will use %s." % key, True)

    def _selected_size(self):
        if (self.selected_text is None
                or not (0 <= self.selected_text < len(self.texts))):
            return None
        return self.texts[self.selected_text].get("size_in",
                                                  ts.DEFAULT_TEXT_SIZE_IN)

    def _set_selected_size(self, value):
        if (self.selected_text is None
                or not (0 <= self.selected_text < len(self.texts))):
            return
        self.texts[self.selected_text]["size_in"] = min(
            TEXT_MAX_IN, max(TEXT_MIN_IN, value))

    def toggle_text_bold(self):
        if self.selected_text is None:
            return
        it = self.texts[self.selected_text]
        it["bold"] = not it.get("bold")

    def preview_scale(self):
        if self.preview is None or self.base_sheet is None:
            return None
        return self.preview.get_width() / float(self.base_sheet.get_width())

    def _clamp_pan(self):
        """Keep the stored pan inside the frame (so it cannot run away)."""
        if self.preview is None:
            self.pan = (0.0, 0.0)
            return
        f = self.PREVIEW_FRAME
        pw, ph = self.preview.get_size()
        if pw <= f.width:
            px = 0.0
        else:
            px = min((f.x + pw / 2.0) - f.centerx,
                     max((f.right - pw / 2.0) - f.centerx, self.pan[0]))
        if ph <= f.height:
            py = 0.0
        else:
            py = min((f.y + ph / 2.0) - f.centery,
                     max((f.bottom - ph / 2.0) - f.centery, self.pan[1]))
        self.pan = (px, py)

    def preview_origin(self):
        """Topleft of the preview on screen (panned, kept inside the frame)."""
        if self.preview is None:
            return None
        f = self.PREVIEW_FRAME
        pw, ph = self.preview.get_size()
        return (int(f.centerx + self.pan[0] - pw / 2.0),
                int(f.centery + self.pan[1] - ph / 2.0))

    def text_screen_rect(self, i):
        """On-screen rect of text box ``i`` inside the preview (or None)."""
        sc = self.preview_scale()
        if sc is None or self.base_info is None or not (0 <= i < len(self.texts)):
            return None
        ox, oy = self.preview_origin()
        ppi = self.base_info.get("px_per_inch", self.base_info["dpi"]) * sc
        it = self.texts[i]
        f = ts.text_font_for(it.get("size_in", ts.DEFAULT_TEXT_SIZE_IN), ppi,
                             it.get("bold"), it.get("font"))
        img = f.render(it.get("text") or " ", True, (0, 0, 0))
        cx = ox + it.get("x", 0.5) * self.preview.get_width()
        cy = oy + it.get("y", 0.5) * self.preview.get_height()
        return img.get_rect(center=(int(cx), int(cy)))

    def pick_text(self, pos):
        for i in range(len(self.texts) - 1, -1, -1):
            r = self.text_screen_rect(i)
            if r and r.inflate(10, 8).collidepoint(pos):
                return i
        return None

    def composited_sheet(self):
        """The base sheet with every text box stamped on (for save / send)."""
        if self.sheet is None:
            return None
        s = self.sheet.copy()
        ts.draw_texts(s, self.texts,
                      self.info.get("px_per_inch", self.info["dpi"]))
        return s

    def _drag_text(self, pos):
        sc = self.preview_scale()
        if not self.text_drag or sc is None:
            return
        ox, oy = self.preview_origin()
        gx, gy = self.text_drag["grab"]
        it = self.texts[self.text_drag["index"]]
        it["x"] = min(1.0, max(0.0, (pos[0] - gx - ox) /
                               self.preview.get_width()))
        it["y"] = min(1.0, max(0.0, (pos[1] - gy - oy) /
                               self.preview.get_height()))

    def _edit_text(self, event):
        it = self.texts[self.selected_text]
        if event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
            it["text"] = it["text"][:-1]
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.text_focus = False
        elif event.unicode and event.unicode.isprintable() \
                and len(it["text"]) < 64:
            it["text"] += event.unicode

    def _on_click(self, pos):
        for b in self.buttons:                 # let buttons own their clicks
            if b.rect.collidepoint(pos):
                return
        if self.TEXT_PANEL.collidepoint(pos):  # text panel owns its clicks too
            return
        if self.TITLE_FIELD.collidepoint(pos):
            self.title_focus = True
            self.text_focus = False
            return
        self.title_focus = False
        for i in range(len(self.inputs)):
            if self.list_row_rect(i).collidepoint(pos):
                self.selected = i
                return
        idx = self.pick_text(pos)
        if idx is not None:
            self.selected_text = idx
            self.text_focus = True
            r = self.text_screen_rect(idx)
            self.text_drag = {"index": idx,
                              "grab": (pos[0] - r.centerx, pos[1] - r.centery)}
        else:
            self.selected_text = None
            self.text_focus = False
            if self.PREVIEW_FRAME.collidepoint(pos):
                # grab empty preview space to pan the zoomed sheet into frame
                self.panning = {"start": pos, "pan": self.pan}

    # ------------------------------------------------------------------ #
    # actions
    # ------------------------------------------------------------------ #
    def build(self):
        if not self.inputs:
            self.status, self.status_ok = "Add at least one file first.", False
            return False
        self.busy = True
        self.status, self.status_ok = "Rendering views...", True
        self._paint()
        try:
            base_sheet, base_info = ts.build_sheet(
                self.inputs, self.views, self.orientation, self.dpi,
                self.title_text, elevation=8.0, image_scale=1.0,
                psd_layers=not self.flatten_psd)
            if abs(self.image_scale - 1.0) < 1e-6:
                sheet, info = base_sheet, base_info
            else:
                sheet, info = ts.build_sheet(
                    self.inputs, self.views, self.orientation, self.dpi,
                    self.title_text, elevation=8.0, image_scale=self.image_scale,
                    psd_layers=not self.flatten_psd)
            out_sheet = sheet.copy()
            ts.draw_texts(out_sheet, self.texts,
                          info.get("px_per_inch", info["dpi"]))
            pygame.image.save(out_sheet, str(OUT))
        except Exception as exc:                          # noqa: BLE001
            self.busy = False
            self.status, self.status_ok = "Build failed: %s" % exc, False
            return False
        self.busy = False
        self.sheet, self.info = sheet, info
        self.base_sheet, self.base_info = base_sheet, base_info
        self._make_preview()
        self.status = ("Built %dx%d px @ %d ppi - %d view(s) -> %s"
                       % (info["size"][0], info["size"][1], info["dpi"],
                          info["views"], OUT.name))
        self.status_ok = True
        return True

    def send(self):
        if not self.build():
            return
        self.busy = True
        self.status, self.status_ok = "Sending to Photoshop...", True
        self._paint()
        ok, msg = ts.send_to_photoshop(OUT, self.info)
        self.busy = False
        self.status, self.status_ok = msg, ok

    def save_as(self):
        if self.inputs and not self.build():
            return
        if self.sheet is None:
            return
        dlg = _tk_dialog()
        if dlg is None:
            self.status, self.status_ok = (
                "Save dialog unavailable - tkinter is not installed.", False)
            return
        tk, filedialog = dlg
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:                              # noqa: BLE001
            pass
        path = filedialog.asksaveasfilename(
            title="Save turnaround sheet", defaultextension=".png",
            initialfile=OUT.name, filetypes=[("PNG image", "*.png")])
        root.destroy()
        if path:
            pygame.image.save(self.composited_sheet(), str(path))
            self.status, self.status_ok = "Saved %s" % path, True

    def _make_preview(self):
        # Preview is built from the 100% sheet and zoomed by the canvas scale,
        # so the scale slider visibly grows / shrinks the sheet (100% = fits
        # the frame; above that it is clipped and can be panned).
        self.pan = (0.0, 0.0)                 # recentre on any geometry change
        self.panning = None
        if self.base_sheet is None:
            self.preview = None
            return
        f = self.PREVIEW_FRAME
        sw, sh = self.base_sheet.get_size()
        sc = min(f.width / sw, f.height / sh) * self.image_scale
        self.preview = pygame.transform.smoothscale(
            self.base_sheet, (max(1, int(sw * sc)), max(1, int(sh * sc))))

    def list_row_rect(self, i):
        return pygame.Rect(self.LIST_AREA.x + 6, self.LIST_AREA.y + 6 + i * 30,
                           self.LIST_AREA.width - 12, 26)

    # ------------------------------------------------------------------ #
    def handle(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if self.text_focus and self.selected_text is not None:
                self._edit_text(event)
                return True
            if event.key == pygame.K_ESCAPE:
                return False
            if self.title_focus:
                if event.key == pygame.K_BACKSPACE:
                    self.title_text = self.title_text[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.title_focus = False
                elif event.unicode and event.unicode.isprintable():
                    if len(self.title_text) < 48:
                        self.title_text += event.unicode
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.build()
            return True
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                          pygame.MOUSEMOTION):
            self.size_slider.handle(event)
            self.scale_slider.handle(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_click(event.pos)
        elif event.type == pygame.MOUSEMOTION and self.text_drag:
            self._drag_text(event.pos)
        elif event.type == pygame.MOUSEMOTION and self.panning:
            dx = event.pos[0] - self.panning["start"][0]
            dy = event.pos[1] - self.panning["start"][1]
            self.pan = (self.panning["pan"][0] + dx,
                        self.panning["pan"][1] + dy)
            self._clamp_pan()
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.text_drag = None
            self.panning = None
        for b in self.buttons:
            b.handle(event)
        return True

    def _paint(self):
        self.draw()
        pygame.display.flip()

    # ------------------------------------------------------------------ #
    def draw(self):
        screen = self.screen
        vgrad(screen, (0, 0, *WINDOW), SKY_TOP, WATER)
        glow = pygame.Surface((420, 420), pygame.SRCALPHA)
        for i in range(70, 0, -1):
            a = int(58 * (1 - i / 70.0))
            pygame.draw.circle(glow, (255, 252, 214, a), (210, 210), 60 + i * 2)
        screen.blit(glow, (WINDOW[0] - 420, -160))

        self.draw_header()
        self.draw_files()
        self.draw_options()
        self.draw_preview()
        self.draw_text_panel()
        self.draw_status()
        for b in self.buttons:
            b.draw(screen)

    def draw_header(self):
        text_shadow(self.screen, "Turnaround Studio", font(40, True), WHITE,
                    (44, 26))

    def draw_files(self):
        p = self.FILE_PANEL
        self.screen.blit(glass_panel(p.size), p.topleft)
        text_shadow(self.screen, "Source files", font(19, True), INK,
                    (p.x + 18, p.y + 14), sh=(255, 255, 255))
        self.screen.blit(font(12).render(
            "images + PSD + Maya .ma/.mb/.obj   (click a row to select)", True,
            INK_SOFT), (p.x + 20, p.y + 40))

        area = self.LIST_AREA
        self.screen.blit(rounded(area.size, 10, (255, 255, 255, 95)),
                         area.topleft)
        if not self.inputs:
            msg = font(15).render("No files yet - click 'Add file...'", True,
                                  INK_SOFT)
            self.screen.blit(msg, msg.get_rect(center=area.center))
        max_rows = (area.height - 12) // 30
        for i, path in enumerate(self.inputs[:max_rows]):
            row = self.list_row_rect(i)
            if i == self.selected:
                self.screen.blit(rounded(row.size, 8, (120, 210, 245, 225)),
                                 row.topleft)
            ext = Path(path).suffix.lower()
            if ext in MODEL_EXTS:
                ttext, tcol = "3D", GREEN
            elif ext in PSD_EXTS:
                ttext, tcol = "PS", VIOLET
            else:
                ttext, tcol = "IMG", AQUA_DEEP
            tag = font(12, True).render(ttext, True, tcol)
            self.screen.blit(tag, (row.x + 8, row.y + 6))
            name = Path(path).name
            maxw = row.width - 60
            if font(15).size(name)[0] > maxw:
                while name and font(15).size(name + "...")[0] > maxw:
                    name = name[:-1]
                name += "..."
            self.screen.blit(font(15).render(name, True, INK),
                             (row.x + 44, row.y + 4))
        if len(self.inputs) > max_rows:
            self.screen.blit(font(12).render(
                "+%d more" % (len(self.inputs) - max_rows), True, INK_SOFT),
                (area.x + 8, area.bottom - 18))

    def draw_options(self):
        p = self.OPT_PANEL
        self.screen.blit(glass_panel(p.size), p.topleft)
        text_shadow(self.screen, "Options", font(19, True), INK,
                    (p.x + 18, p.y + 12), sh=(255, 255, 255))
        lbl = font(13, True)
        self.screen.blit(lbl.render("Sheet title", True, INK_SOFT),
                         (60, 486))
        self.screen.blit(lbl.render("Rotation views", True, INK_SOFT),
                         (60, 552))
        self.screen.blit(lbl.render("Orientation", True, INK_SOFT),
                         (60, 612))
        self.screen.blit(lbl.render("Resolution", True, INK_SOFT),
                         (60, 672))
        self.screen.blit(lbl.render("Canvas scale", True, INK_SOFT),
                         (60, 732))
        self.scale_slider.draw(self.screen)
        self.screen.blit(font(14, True).render(
            "%d%%" % int(round(self._image_scale() * 100)), True, INK),
            (442, 740))

        fr = self.TITLE_FIELD
        self.screen.blit(rounded(fr.size, 12, (255, 255, 255, 155)), fr)
        border = (60, 150, 210, 255) if self.title_focus else (255, 255, 255, 200)
        pygame.draw.rect(self.screen, border, fr, width=2, border_radius=12)
        shown = self.title_text or "Type a title..."
        col = INK if self.title_text else (120, 140, 160)
        self.screen.blit(font(17).render(shown, True, col),
                         (fr.x + 12, fr.y + 8))
        if self.title_focus and int(self.t * 2) % 2 == 0:
            cx = fr.x + 12 + font(17).size(self.title_text)[0] + 1
            pygame.draw.line(self.screen, INK, (cx, fr.y + 8),
                             (cx, fr.bottom - 8), 2)

    def draw_preview(self):
        p = self.PREV_PANEL
        self.screen.blit(glass_panel(p.size), p.topleft)
        text_shadow(self.screen, "Preview", font(19, True), INK,
                    (p.x + 18, p.y + 14), sh=(255, 255, 255))
        self.screen.blit(font(12).render(
            "drag to pan the zoomed sheet", True, INK_SOFT),
            (p.x + 110, p.y + 20))
        fr = self.PREVIEW_FRAME
        self.screen.blit(rounded(fr.size, 10, (255, 255, 255, 185)),
                         fr.topleft)
        pygame.draw.rect(self.screen, (255, 255, 255, 220), fr, width=2,
                         border_radius=10)
        if self.preview:
            disp = self.preview.copy()
            sc = self.preview_scale()
            if self.texts and sc and self.base_info:
                ts.draw_texts(disp, self.texts,
                              self.base_info.get("px_per_inch",
                                                 self.base_info["dpi"]) * sc)
            clip = self.screen.get_clip()
            self.screen.set_clip(fr)
            self.screen.blit(disp, disp.get_rect(center=fr.center))
            if self.selected_text is not None:
                r = self.text_screen_rect(self.selected_text)
                if r:
                    hl = r.inflate(14, 10)
                    pygame.draw.rect(self.screen, AQUA_DEEP, hl, width=2,
                                     border_radius=6)
                    if self.text_focus and int(self.t * 2) % 2 == 0:
                        pygame.draw.line(self.screen, AQUA_DEEP,
                                         (r.right + 3, r.top - 2),
                                         (r.right + 3, r.bottom + 2), 2)
            zoom = font(14, True).render(
                "%d%%" % int(round(self.image_scale * 100)), True, AQUA_DEEP)
            self.screen.blit(zoom, (fr.right - zoom.get_width() - 10,
                                    fr.y + 8))
            self.screen.set_clip(clip)
        else:
            msg = font(15).render("Build to see your turnaround sheet", True,
                                  INK_SOFT)
            self.screen.blit(msg, msg.get_rect(center=fr.center))
        if self.busy:
            self.screen.blit(font(16, True).render("working...", True,
                                                   AQUA_DEEP),
                             (p.x + 18, p.bottom - 30))

    def draw_text_panel(self):
        p = self.TEXT_PANEL
        self.screen.blit(glass_panel(p.size, radius=14), p.topleft)
        text_shadow(self.screen, "Text boxes", font(19, True), INK,
                    (p.x + 18, p.y + 8), sh=(255, 255, 255))
        self.screen.blit(font(12).render(
            "Drag a box on the preview - click it to edit; type to change",
            True, INK_SOFT), (p.x + 160, p.y + 14))
        self.screen.blit(font(13, True).render("Font", True, INK),
                         (p.x + 16, p.y + 80))
        self.screen.blit(font(13, True).render("Size", True, INK),
                         (p.x + 262, p.y + 80))
        self.size_slider.draw(self.screen)
        v = self.size_slider._value()
        if v is None:
            val, col = "- pt", INK_SOFT
        else:
            val, col = "%d pt" % int(round(v * 72)), INK
        self.screen.blit(font(14, True).render(val, True, col),
                         (p.x + 478, p.y + 76))

    def draw_status(self):
        p = self.STATUS_PANEL
        self.screen.blit(glass_panel(p.size, radius=14), p.topleft)
        col = (30, 120, 70) if self.status_ok else (176, 56, 56)
        text = self.status
        img = font(14, True).render(text, True, col)
        while img.get_width() > p.width - 28 and len(text) > 4:
            text = text[:-1]
            img = font(14, True).render(text + "...", True, col)
        self.screen.blit(img, (p.x + 16, p.y + 24))

    # ------------------------------------------------------------------ #
    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.t += dt
            for event in pygame.event.get():
                if not self.handle(event):
                    self.running = False
            self.draw()
            pygame.display.flip()
        pygame.quit()


def main():
    App().run()


if __name__ == "__main__":
    main()
