// Build a "Color Script" palette document natively in Photoshop.
//
// The layout spec is injected as a JS object literal below (JSON is valid JS),
// so this file is run through photoshop_bridge.py:
//
//     python photoshop_bridge.py _palette_run.jsx
//
// Everything the sheet needs is in SPEC: canvas size/dpi, background colour,
// an optional title, and one block per palette with swatch rects (shape +
// exact fill colour + hex label), the source image thumbnails and a gradient
// strip PNG to place. Every element may carry dx/dy offsets - those are the
// GUI's hand-moved positions, applied on top of the planned coordinates.
//
// Notes learned on this machine (Photoshop 2026):
//   * a SolidColor's green channel MUST be set/read as `.green` - writing
//     `.grain` silently leaves the channel at 255;
//   * selections are filled with `doc.selection.select([[x,y],...])` +
//     `doc.selection.fill(color)` (no selectRectangle helper);
//   * a text layer only accepts `.textItem` after `layer.kind = LayerKind.TEXT`;
//   * layer duplicates need their source document frontmost, and the
//     destination frontmost again for the rename;

app.displayDialogs = DialogModes.NO;

var SPEC = %s;

var oldUnits = app.preferences.rulerUnits;
app.preferences.rulerUnits = Units.PIXELS;

function rgbColor(c) {
    var sc = new SolidColor();
    sc.rgb.red = c[0];
    sc.rgb.green = c[1];
    sc.rgb.blue = c[2];
    return sc;
}

function fillPoly(doc, pts, color) {
    var p = [];
    for (var i = 0; i < pts.length; i++) {
        p.push([Math.round(pts[i][0]), Math.round(pts[i][1])]);
    }
    doc.selection.select(p);
    doc.selection.fill(color);
    doc.selection.deselect();
}

function rectPts(x, y, w, h) {
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
}

function circlePts(x, y, w, h) {
    var cx = x + w / 2, cy = y + h / 2, rx = w / 2, ry = h / 2, pts = [];
    for (var i = 0; i < 48; i++) {
        var a = i / 48 * 2 * Math.PI;
        pts.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]);
    }
    return pts;
}

function roundedPts(x, y, w, h) {
    var r = Math.min(w, h) * 0.22, pts = [];
    var corners = [[x + w - r, y + r, -90, 0], [x + w - r, y + h - r, 0, 90],
                   [x + r, y + h - r, 90, 180], [x + r, y + r, 180, 270]];
    for (var c = 0; c < 4; c++) {
        for (var s = 0; s < 7; s++) {
            var a = (corners[c][2] + (corners[c][3] - corners[c][2]) *
                     s / 6) * Math.PI / 180;
            pts.push([corners[c][0] + Math.cos(a) * r,
                      corners[c][1] + Math.sin(a) * r]);
        }
    }
    return pts;
}

function ox(el) { return el.dx || 0; }
function oy(el) { return el.dy || 0; }

function shapePts(sw) {
    var x = sw.x + ox(sw), y = sw.y + oy(sw);
    if (sw.shape === "circle") {
        return circlePts(x, y, sw.w, sw.h);
    }
    if (sw.shape === "rounded") {
        return roundedPts(x, y, sw.w, sw.h);
    }
    return rectPts(x, y, sw.w, sw.h);
}

function addText(doc, contents, x, y, sizePx, color, bold, centered, name) {
    var layer = doc.artLayers.add();
    layer.kind = LayerKind.TEXT;
    var ti = layer.textItem;
    ti.contents = contents;
    ti.position = [Math.round(x), Math.round(y)];
    ti.size = sizePx * 72 / doc.resolution;
    ti.color = rgbColor(color);
    if (centered) {
        ti.justification = Justification.CENTER;
    }
    try { if (bold) { ti.fauxBold = true; } } catch (e) {}
    if (name) { layer.name = name; }
    return layer;
}

function placePng(doc, path, x, y, name, below) {
    var src = app.open(new File(path));
    app.activeDocument = src;
    var placed = src.activeLayer.duplicate(below || doc,
        below ? ElementPlacement.PLACEAFTER : ElementPlacement.PLACEATBEGINNING);
    app.activeDocument = doc;
    placed.name = name;
    placed.translate(x, y);
    app.activeDocument = src;
    src.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
    return placed;
}

// close a previous palette document with the same name
for (var i = app.documents.length - 1; i >= 0; i--) {
    if (app.documents[i].name === SPEC.doc_name) {
        app.documents[i].close(SaveOptions.DONOTSAVECHANGES);
    }
}

var doc = app.documents.add(SPEC.w, SPEC.h, SPEC.dpi, SPEC.doc_name,
    NewDocumentMode.RGB, DocumentFill.WHITE);
app.activeDocument = doc;

var bgLayer = doc.artLayers.add();
bgLayer.name = "Background";
doc.activeLayer = bgLayer;
fillPoly(doc, rectPts(0, 0, SPEC.w, SPEC.h), rgbColor(SPEC.bg));

var swatchCount = 0, stripCount = 0, textCount = 0, imageCount = 0;

if (SPEC.title) {
    var t = SPEC.title;
    addText(doc, t.text, t.cx + ox(t), t.y + oy(t), t.size, t.color, t.bold,
            true, "Title");
    textCount++;
}

// Layers are stacked to match the PNG renderer's draw order. The PNG draws in
// explicit z-ordered passes - images, then swatches, then captions/labels on
// top, then strips - so a label can never be covered by an image no matter how
// the items are dragged. We mirror that order here with the same passes.

// pass 1: swatch fill layers (one layer per palette) with images placed
// directly underneath them
for (var pi = 0; pi < SPEC.palettes.length; pi++) {
    var pal = SPEC.palettes[pi];

    var layer = doc.artLayers.add();
    layer.name = pal.layer_name;
    doc.activeLayer = layer;
    for (var si = 0; si < pal.swatches.length; si++) {
        var sw = pal.swatches[si];
        fillPoly(doc, shapePts(sw), rgbColor(sw.color));
        swatchCount++;
    }

    // images sit directly under the swatches of their own palette
    if (pal.images) {
        for (var ii = 0; ii < pal.images.length; ii++) {
            var im = pal.images[ii];
            if (!im.png) { continue; }
            placePng(doc, im.png, im.x + ox(im), im.y + oy(im), im.name, layer);
            imageCount++;
        }
    }
}

// pass 2: captions and hex labels on top of every image and swatch
for (var pj = 0; pj < SPEC.palettes.length; pj++) {
    var pal2 = SPEC.palettes[pj];
    if (pal2.caption) {
        addText(doc, pal2.caption.text, pal2.caption.cx + ox(pal2.caption),
                pal2.caption.y + oy(pal2.caption), pal2.caption.size,
                pal2.caption.color, pal2.caption.bold, true,
                pal2.caption.text);
        textCount++;
    }
    for (var li = 0; li < pal2.swatches.length; li++) {
        var lw = pal2.swatches[li];
        if (lw.label_cx === undefined || lw.label_cx === null) { continue; }
        addText(doc, lw.hex, lw.label_cx + ox(lw), lw.label_y + oy(lw),
                lw.label_size, lw.label_color, false, true, lw.hex);
        textCount++;
    }
}

// pass 3: gradient strips on top
for (var pk = 0; pk < SPEC.palettes.length; pk++) {
    var pal3 = SPEC.palettes[pk];
    if (pal3.strip && pal3.strip.png) {
        placePng(doc, pal3.strip.png, pal3.strip.x + ox(pal3.strip),
                 pal3.strip.y + oy(pal3.strip), pal3.strip.name);
        stripCount++;
    }
}

doc.selection.deselect();
app.preferences.rulerUnits = oldUnits;

__result__ = "color script: " + doc.name + " | " + Math.round(doc.width.value) +
    "x" + Math.round(doc.height.value) + " px @ " + doc.resolution + " ppi | " +
    swatchCount + " swatches, " + stripCount + " gradient(s), " + imageCount +
    " image(s), " + textCount + " labels | " + SPEC.palettes.length +
    " palette(s)";
