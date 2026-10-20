# Color Script — UXP plugin (Part 5 experiment)

A Photoshop **panel** that rebuilds the palette sheet inside the open document.
It is the "inside Photoshop" sibling of the standalone `palette_gui.py` app:
instead of the terminal driving Photoshop, the panel lives inside Photoshop.

```
manifest.json     plugin metadata (manifest v5, one panel entrypoint)
index.html        the panel UI (one button)
index.js          the port: reads the layout JSON and builds the sheet via batchPlay
icons/            panel icon (@1x and @2x)
```

## What it does

1. You click **"Build from layout file..."**.
2. It opens a file picker and you choose the `layout.json` that
   `palette_sheet.build_sheet` wrote (the same spec `photoshop_palette.jsx` uses).
3. It rebuilds the sheet in the **currently open Photoshop document**: background,
   title, one swatch-fill layer per palette with the source-image thumbnails placed
   underneath, then captions + hex labels, then the gradient strips — all inside one
   `executeAsModal` scope with a single suspended history state.

It is deliberately a *thin* port: it reuses the exact spec the Python side already
produces, so the panel and the standalone app stay in lock-step.

## Loading it (development)

1. Install **Adobe UXP Developer Tool** from the Creative Cloud desktop app
   (Creative Cloud > Market / All apps > "UXP Developer Tool").
2. Open the UXP Developer Tool and sign in with the same Adobe ID as Photoshop.
3. **Add Plugin…** → choose this `uxp-plugin/` folder (manifest v5 is read automatically).
4. Click **• • • → Load**. Photoshop opens the **Color Script** panel
   (Plugins menu → Color Script, if it is not already visible).
5. Open any Photoshop document, then click **Build from layout file...** and pick a
   layout JSON.

To see console output, use **• • • → Debug** (opens the plugin console) or
**• • • → Watch** to reload on save.

## Notes / current limits

See `../PLAN-INSIDE-PHOTOSHOP.md` for what works, what does not yet, and what it would
take to move the image picker and the options into the panel. This folder is an
experiment on the `inside-photoshop` branch and is **not merged**; the standalone app is
untouched and remains the supported path.
