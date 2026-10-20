/*
 * Color Script - UXP panel (Part 5 experiment)
 *
 * "Build from layout file..." lets the user pick the layout JSON that
 * palette_gui.py saves, then rebuilds the palette sheet natively in the
 * current Photoshop document - the same output as photoshop_palette.jsx, but
 * expressed with the modern UXP API (window.require("photoshop")) instead of
 * ExtendScript.
 *
 * This is a first experiment: see PLAN-INSIDE-PHOTOSHOP.md for what works,
 * what does not yet, and what porting the rest of the app would take.
 */

const photoshop = window.require("photoshop");
const fs = window.require("uxp").storage.localFileSystem;
const { app, action, core, constants } = photoshop;
const { LayerKind, ElementPlacement } = constants;

const DPI_DEFAULT = 150;
const DOC_NAME_DEFAULT = "Color Script";

/* ------------------------------------------------------------------ */
/* small helpers                                                       */
/* ------------------------------------------------------------------ */

function setStatus(text, kind) {
  const el = document.getElementById("status");
  el.textContent = text;
  el.className = kind || "";
}

function to255(c) {
  return { red: c[0], green: c[1], blue: c[2] };
}

function rectPts(x, y, w, h) {
  return [x, y, x + w, y, x + w, y + h, x, y + h];
}

function circlePts(x, y, w, h) {
  const cx = x + w / 2, cy = y + h / 2, rx = w / 2, ry = h / 2;
  const out = [];
  for (let i = 0; i < 48; i++) {
    const a = (i / 48) * 2 * Math.PI;
    out.push(cx + Math.cos(a) * rx, cy + Math.sin(a) * ry);
  }
  return out;
}

function roundedPts(x, y, w, h) {
  const r = Math.min(w, h) * 0.22;
  const corners = [
    [x + w - r, y + r, -90, 0],
    [x + w - r, y + h - r, 0, 90],
    [x + r, y + h - r, 90, 180],
    [x + r, y + r, 180, 270],
  ];
  const out = [];
  for (const c of corners) {
    for (let s = 0; s < 7; s++) {
      const a = ((c[2] + (c[3] - c[2]) * s / 6) * Math.PI) / 180;
      out.push(c[0] + Math.cos(a) * r, c[1] + Math.sin(a) * r);
    }
  }
  return out;
}

/** Points as the DOM Selection API wants them: an array of {x, y}. */
function shapePoints(sw) {
  const x = sw.x + (sw.dx || 0), y = sw.y + (sw.dy || 0);
  let flat;
  if (sw.shape === "circle") flat = circlePts(x, y, sw.w, sw.h);
  else if (sw.shape === "rounded") flat = roundedPts(x, y, sw.w, sw.h);
  else flat = rectPts(x, y, sw.w, sw.h);
  const out = [];
  for (let i = 0; i < flat.length; i += 2) out.push({ x: flat[i], y: flat[i + 1] });
  return out;
}

/* ------------------------------------------------------------------ */
/* batchPlay primitives                                                */
/* ------------------------------------------------------------------ */

/** Fill a polygon into the currently selected layer. */
async function fillPoly(points, color) {
  const doc = app.activeDocument;
  await doc.selection.selectPolygon(points);
  await action.batchPlay(
    [
      {
        _obj: "fill",
        using: { _enum: "fillContents", _value: "color" },
        color: { _obj: "RGBColor", ...to255(color) },
        opacity: { _unit: "percentUnit", _value: 100 },
        mode: { _enum: "blendMode", _value: "normal" },
      },
    ],
    {}
  );
  await deselect();
}

async function deselect() {
  await app.activeDocument.selection.deselect();
}

/** Fill a rectangle into the current layer (background / simple rects). */
async function fillRect(x, y, w, h, color) {
  const doc = app.activeDocument;
  await doc.selection.selectRectangle({ top: y, left: x, bottom: y + h, right: x + w });
  await action.batchPlay(
    [
      {
        _obj: "fill",
        using: { _enum: "fillContents", _value: "color" },
        color: { _obj: "RGBColor", ...to255(color) },
        opacity: { _unit: "percentUnit", _value: 100 },
        mode: { _enum: "blendMode", _value: "normal" },
      },
    ],
    {}
  );
  await deselect();
}

/** Add an empty pixel layer and return its id. */
async function addLayer(name) {
  const [r] = await action.batchPlay(
    [
      {
        _obj: "make",
        _target: [{ _ref: "layer" }],
        using: { _obj: "layer", name },
      },
    ],
    {}
  );
  return r.layerID;
}

async function selectLayer(id) {
  await action.batchPlay(
    [{ _obj: "select", _target: { _ref: "layer", _id: id } }],
    {}
  );
}

/** Add a text layer. Returns its id. */
async function addText(contents, x, y, sizePx, color, bold, centered, name) {
  const id = await addLayer(name || contents);
  await action.batchPlay(
    [
      {
        _obj: "set",
        _target: { _ref: "layer", _id: id },
        to: { _obj: "textLayer", textKey: contents },
      },
    ],
    {}
  );
  await action.batchPlay(
    [
      {
        _obj: "set",
        _target: { _ref: "layer", _id: id },
        to: {
          _obj: "textLayer",
          textStyle: {
            _obj: "textStyle",
            size: { _unit: "pointsUnit", _value: (sizePx * 72) / DPI_DEFAULT },
            color: { _obj: "RGBColor", ...to255(color) },
            horizontalAlignment: centered ? "center" : "left",
            ...(bold ? { fauxBold: true } : {}),
          },
          textShape: [
            {
              _obj: "textShape",
              textType: { _obj: "textType", textType: "point" },
              transform: {
                _obj: "transform",
                origin: { _obj: "paint", horizontal: x, vertical: y },
              },
            },
          ],
        },
      },
    ],
    {}
  );
  return id;
}

/* ------------------------------------------------------------------ */
/* build                                                               */
/* ------------------------------------------------------------------ */

/** Resolve a native path (from the layout JSON) to a UXP Entry. */
async function entryForPath(p) {
  const url = "file:/" + p.replace(/\\/g, "/").replace(/^\/+/, "");
  return fs.getEntryWithUrl(url);
}

/** Place a PNG at (x,y) sized (w,h) using Place Embedded. Returns layer id. */
async function placePng(path, x, y, w, h, name) {
  const entry = await entryForPath(path);
  const token = fs.createSessionToken(entry);
  const [r] = await action.batchPlay(
    [
      {
        _obj: "placeEvent",
        null: { _path: token, _kind: "local" },
        freeTransformCenterState: { _enum: "quadCenterState", _value: "QCSAverage" },
        offset: { _obj: "offset", horizontal: { _unit: "pixelsUnit", _value: 0 }, vertical: { _unit: "pixelsUnit", _value: 0 } },
      },
    ],
    {}
  );
  const id = r.layerID;

  // Place Embedded sizes the image itself; scale it to the planned size.
  const [b] = await action.batchPlay(
    [{ _obj: "get", _target: { _ref: "layer", _id: id }, _property: "bounds" }],
    {}
  );
  const cw = b.bounds.right._value - b.bounds.left._value;
  const ch = b.bounds.bottom._value - b.bounds.top._value;
  if (w && h && (Math.round(cw) !== w || Math.round(ch) !== h)) {
    await action.batchPlay(
      [
        {
          _obj: "transform",
          _target: { _ref: "layer", _id: id },
          freeTransformCenterState: { _enum: "quadCenterState", _value: "QCSAverage" },
          width: { _unit: "percentUnit", _value: (w / cw) * 100 },
          height: { _unit: "percentUnit", _value: (h / ch) * 100 },
        },
      ],
      {}
    );
  }
  // Move the layer so the top-left lands on (x,y).
  const [b2] = await action.batchPlay(
    [{ _obj: "get", _target: { _ref: "layer", _id: id }, _property: "bounds" }],
    {}
  );
  await action.batchPlay(
    [
      {
        _obj: "move",
        _target: { _ref: "layer", _id: id },
        to: { _ref: "layer", _enum: "ordinal", _value: "targetEnum" },
        offset: {
          _obj: "offset",
          horizontal: { _unit: "pixelsUnit", _value: x - b2.bounds.left._value },
          vertical: { _unit: "pixelsUnit", _value: y - b2.bounds.top._value },
        },
      },
    ],
    {}
  );
  if (name) await renameLayer(id, name);
  return id;
}

async function renameLayer(id, name) {
  await action.batchPlay(
    [{ _obj: "set", _target: { _ref: "layer", _id: id }, to: { _obj: "layer", name } }],
    {}
  );
}

async function moveBelow(id, targetId) {
  await action.batchPlay(
    [
      {
        _obj: "move",
        _target: { _ref: "layer", _id: id },
        to: { _ref: "layer", _id: targetId, _enum: "ordinal", _value: "below" },
      },
    ],
    {}
  );
}

/** Rebuild the sheet in the current doc. Runs inside executeAsModal. */
async function buildSheet(spec, execContext) {
  const doc = app.activeDocument;
  const w = spec.w, h = spec.h;

  // one history state for the whole build
  const suspension = await execContext.hostControl.suspendHistory({
    documentID: doc.id,
    name: "Color Script",
  });

  let swatchCount = 0, stripCount = 0, textCount = 0, imageCount = 0;

  // background
  const bgId = await addLayer("Background");
  await selectLayer(bgId);
  await fillRect(0, 0, w, h, spec.bg);

  if (spec.title) {
    const t = spec.title;
    await addText(t.text, t.cx + (t.dx || 0), t.y + (t.dy || 0), t.size, t.color, t.bold, true, "Title");
    textCount++;
  }

  // pass 1: images placed first, swatch layer added on top and images moved below
  for (const pal of spec.palettes) {
    const placed = [];
    if (pal.images) {
      for (const im of pal.images) {
        if (!im.png) continue;
        placed.push(await placePng(im.png, im.x + (im.dx || 0), im.y + (im.dy || 0), im.w, im.h, im.name));
        imageCount++;
      }
    }
    const swId = await addLayer(pal.layer_name);
    await selectLayer(swId);
    for (const sw of pal.swatches) {
      await fillPoly(shapePoints(sw), sw.color);
      swatchCount++;
    }
    await deselect();
    for (const id of placed) await moveBelow(id, swId);
  }

  // pass 2: captions + hex labels on top
  for (const pal of spec.palettes) {
    if (pal.caption) {
      const c = pal.caption;
      await addText(c.text, c.cx + (c.dx || 0), c.y + (c.dy || 0), c.size, c.color, c.bold, true, c.text);
      textCount++;
    }
    for (const sw of pal.swatches) {
      if (sw.label_cx === undefined || sw.label_cx === null) continue;
      await addText(sw.hex, sw.label_cx + (sw.dx || 0), sw.label_y + (sw.dy || 0), sw.label_size, sw.label_color, false, true, sw.hex);
      textCount++;
    }
  }

  // pass 3: gradient strips on top
  for (const pal of spec.palettes) {
    if (pal.strip && pal.strip.png) {
      await placePng(pal.strip.png, pal.strip.x + (pal.strip.dx || 0), pal.strip.y + (pal.strip.dy || 0), pal.strip.w, pal.strip.h, pal.strip.name);
      stripCount++;
    }
  }

  await execContext.hostControl.resumeHistory(suspension);

  return `${doc.name} | ${Math.round(doc.width)}x${Math.round(doc.height)} px @ ${doc.resolution} ppi | ` +
    `${swatchCount} swatches, ${stripCount} gradient(s), ${imageCount} image(s), ${textCount} labels | ` +
    `${spec.palettes.length} palette(s)`;
}

/* ------------------------------------------------------------------ */
/* button wiring                                                       */
/* ------------------------------------------------------------------ */

async function onBuild() {
  const btn = document.getElementById("btnBuild");
  const bar = document.getElementById("progress");
  try {
    if (!app.documents.length) {
      setStatus("Open a document in Photoshop first.", "err");
      return;
    }
    const file = await fs.getFileForOpening({ types: [".json"] });
    if (!file) {
      setStatus("No file selected.");
      return;
    }
    const text = await file.read();
    const spec = JSON.parse(text);

    btn.disabled = true;
    bar.hidden = false;
    setStatus("Building...");

    const summary = await core.executeAsModal(
      (ctx) => buildSheet(spec, ctx),
      { commandName: "Color Script: Build" }
    );

    setStatus("color script: " + summary, "ok");
  } catch (e) {
    console.error(e);
    setStatus("Build failed: " + (e && e.message ? e.message : e), "err");
  } finally {
    btn.disabled = false;
    bar.hidden = true;
  }
}

document.getElementById("btnBuild").addEventListener("click", onBuild);
