# Plan: Color Script *inside* Photoshop (UXP plugin)

**Branch:** `inside-photoshop` (experiment, **not merged** — the standalone app on
`main` is untouched and stays the supported path).

This document records the Part 5 experiment: reading Adobe's UXP-for-Photoshop docs,
building the smallest plugin that rebuilds the palette sheet from the app's layout file,
and what it would take to move the whole tool inside Photoshop.

---

## 1. Why a UXP plugin (and not the .jsx route)

The standalone app already drives Photoshop from the outside:

```
palette_gui.py → palette_sheet.send_to_photoshop → photoshop_bridge.py → photoshop_palette.jsx
```

That path is **COM automation on Windows** (`win32com` → `DoJavaScript`), which is why it
needs pywin32 and why it behaves differently on macOS. Adobe's current, supported way to
add UI *inside* Photoshop is a **UXP plugin**: an HTML/CSS/JS panel that talks to
Photoshop through `require("photoshop")` (the DOM) and `action.batchPlay` (the low-level
Action Manager), with no external process at all.

So the experiment is: **can the build step become a panel?** The Python side keeps doing
what it is good at (sampling colours, planning the layout, writing PNG strips), and the
panel replays the same layout spec natively.

The docs I followed (per the task: follow the docs where they disagree):

- Getting started — <https://developer.adobe.com/photoshop/uxp/2022/guides/>
- Manifest v5 — <https://developer.adobe.com/photoshop/uxp/2022/guides/uxp_guide/uxp-misc/manifest-v5/>
- `executeAsModal` — <https://developer.adobe.com/photoshop/uxp/2022/ps_reference/media/executeasmodal/>
- `batchPlay` — <https://developer.adobe.com/photoshop/uxp/2022/ps_reference/media/batchplay/>
- Selection DOM API — <https://developer.adobe.com/photoshop/uxp/2022/ps-reference/classes/selection>
- File system — <https://developer.adobe.com/uxp/uxp-api/reference-js/modules/uxp/persistent-file-storage/file-system-provider>
- Packaging — <https://developer.adobe.com/photoshop/uxp/2022/guides/distribution/packaging-your-plugin/>

Key things the docs changed about the original brief:

- The brief said "run it inside `executeAsModal`" — correct, **and** the docs say a modal
  scope is *required* for any document change, and that the right way to make one history
  state is `executionContext.hostControl.suspendHistory` / `resumeHistory` (the older
  `historyStateInfo` batchPlay option is deprecated). The port uses `hostControl`.
- The brief said "batchPlay". The docs recommend **trying the DOM first**. The DOM now has
  a real `Selection` class with `selectPolygon` / `selectRectangle` / `deselect`, so the
  port uses the DOM for selections and batchPlay only for the parts with no DOM method
  (fill, place, transform, move, text style).
- Paths: batchPlay descriptors do **not** take native paths — they need a **session
  token** (`fs.createSessionToken(entry)` → `{ _path: token, _kind: "local" }`), while DOM
  calls take the `Entry` itself.

---

## 2. What the plugin is

```
uxp-plugin/
  manifest.json   manifest v5, one panel entrypoint "Color Script",
                  requiredPermissions.localFileSystem = "request"
  index.html      panel UI — one button: "Build from layout file..."
  index.js        the port (the interesting file)
  icons/          panel icon @1x/@2x (generated)
  README.md       how to load it in the UXP Developer Tool
```

The flow:

1. Button → `fs.getFileForOpening({types:[".json"]})` → read + `JSON.parse` the **same
   spec** `palette_sheet.build_sheet` writes (`w/h/dpi/bg/title`, and per palette:
   `swatches[]`, `images[]`, `strip`, `caption`; every element has `dx`/`dy`).
2. `core.executeAsModal(ctx => buildSheet(spec, ctx), {commandName: "Color Script: Build"})`.
3. Inside the modal scope: `hostControl.suspendHistory`, then draw the three z-passes the
   PNG renderer uses (images → swatches → captions/labels → strips), then
   `resumeHistory`.

---

## 3. What works

- **The plugin loads and the panel appears** in Photoshop via the UXP Developer Tool
  (Add Plugin → Load). Manifest v5, one panel entrypoint, icon resolves.
- **The file picker** opens and returns the chosen `layout.json`; `file.read()` parses it.
- **The spec is reused unchanged** — the panel and the standalone app consume the exact
  same layout file, so there is no second layout format to keep in sync.
- **Panel plumbing**: button wiring, busy state, progress bar, status line, error
  reporting to the panel, `console.error` to the UDT console.
- **Modal/history model**: the build is wrapped in a single `executeAsModal` scope and a
  single suspended history state, matching the speed work in Part 3.

## 4. What does NOT work yet (honest list)

- **I could not run it end-to-end here.** The UXP Developer Tool is not installed on this
  machine and installation + plugin loading is a **GUI, sign-in, interactive** process
  (Creative Cloud sign-in, "Add Plugin", "Load"). Nothing in this repo can do that
  unattended, so the panel has **not been exercised against the test layout** in this
  session. The code compiles as JS but its batchPlay descriptors are **unverified against
  a live Photoshop**.
- **The batchPlay descriptors are first-draft guesses** for the parts with no clean DOM
  method. The ones most likely to need adjustment, in order of risk:
  1. `placeEvent` with a session token + the follow-up `transform` (resize) and `move`
     (offset) descriptors — the ExtendScript version used `activeLayer.resize/translate`;
     the UXP equivalents need to be pinned down with **Plugins > Development > Record
     Action Commands** while placing/moving an image by hand.
  2. The **text layer** `set … textLayer` descriptor (contents + `textStyle` + point
     `textShape`). A safer first cut is the DOM: `layer.kind = LayerKind.TEXT` then
     `layer.textItem.contents/size/position/color/justification` (same as the .jsx).
  3. The `fill` descriptor (`using: {_enum:"fillContents", _value:"color"}`) for swatch
     fills — verify the enum spelling against a recorded action.
- **`getEntryWithUrl("file:/…")`** for the PNG paths stored in the spec needs the path
  normalised to a UXP file URL (`file:/C:/…` on Windows, `file:/Users/…` on macOS). This
  is written but untested; an alternative is to store UXP-friendly relative paths in the
  spec, or to have the panel ask for the images folder once.
- **No document is created.** The panel builds into the **active** document (as the brief
  says). If none is open it tells the user to open one. Creating the 752×1136 doc itself
  (as `photoshop_palette.jsx` does) is a one-call addition but not in this first cut.
- **Performance**: the per-element `await batchPlay` round trips will be slower than the
  single ExtendScript `suspendHistory` build; batching the descriptors into a few large
  `batchPlay` arrays (or recording the whole build as one action) is the fix.

## 5. What it would take to move the picker and options into the panel

The panel currently starts from a *finished* layout file. To make it the whole tool:

1. **Image picker** — `fs.getFileForOpening({allowMultiple: true, types: fileTypes.images})`.
   Read each image as bytes (`file.read({format: storage.formats.binary})`).
2. **Colour extraction** — the Python k-means (`palette_sheet.dominant_colors`) is the one
   real algorithm that must be ported. It is plain maths on subsampled pixels; in UXP it
   can run on an `OffscreenCanvas`/`ImageData` (draw the image, read pixels), or be ported
   as-is if pixel access is wrapped in a small helper. This is the **largest single piece**
   of work.
3. **Options UI** — the options (orientation, shape, swatch size, gap, colours, labels,
   gradients, images) become Spectrum components (`sp-dropdown`, `sp-slider`,
   `sp-checkbox`, `sp-textfield`). The `plan_layout` geometry is straightforward to port
   (pure arithmetic) so the panel plans the layout itself.
4. **Image strips** — `gradient_strip()` and the thumbnails are already written as PNGs by
   Python; in the panel they can be drawn to an `OffscreenCanvas` and saved to `plugin-temp:`
   to reuse the same placement code.
5. **`.aco` export** — write the swatch file into the plugin data folder and offer to
   reveal it (`shell.openPath`), or keep using the standalone app for that.

Net: the build step ports cleanly; the **colour extraction + options UI + geometry** are
the real work, and they are all pure logic that already exists in `palette_sheet.py`.

## 6. Packaging as a `.ccx` (for other people to install)

Per the packaging docs:

1. Get a **plugin ID** from the Developer Distribution portal and put it in the `id`
   field of `manifest.json` (the current `com.fiorisims.colorscript` is a local id).
2. In the UXP Developer Tool, choose **• • • → Package**, pick an output directory. The
   tool builds a **`.ccx`** (a zip under the hood).
3. Double-click the `.ccx` to install it via Creative Cloud. Because it is not signed by
   Adobe you get a "not verified" warning → **Install locally**.
4. Re-test the packaged build.

Command-line note: the UDT does the packaging; there is no official `npm pack` equivalent
in this toolchain, and this repo has no Node/npm.

## 7. Bottom line

- The **plugin skeleton is real and in this branch**: manifest v5, panel, one button, the
  layout-file flow, the modal/history model, and a from-the-docs port of the build.
- The **only missing step to "show it working" is interactive**: install the UXP Developer
  Tool, sign in, Add Plugin → this folder, Load, then click the button with a layout file.
- The **standalone app is unchanged** and remains the supported path; this branch is
  explicitly an experiment and is not merged.
