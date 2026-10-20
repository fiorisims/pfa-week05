# pfa-week05
Fiori Sims Week 5 Homework for Programming for Animators FA26 
Photoshop Bridge
How to run: Install turnaround_gui.py file, Open Terminal, ask agent to run turnaround_gui.py or run it yourself through File Explorer. Insert .png,.jpeg, .psd or .mb file and click "Build Preview". Crop image to liking. Click "send to photoshop".
Asked agent to create a bridge between the terminal and Photoshop and create a UI where I can upload an image/Maya and create a full-body turnaround sheet of the model. 
Recording: https://drive.google.com/file/d/1QxCBU2fqnB5vpCianzwfmMu_ZGBTjxHk/view?usp=sharing

MIDTERM PROPOSAL: Photoshop Color Script Palette Organizer  
Tool: Opens an interface that allows user to insert pre-existing images (no limit on image count) and have it pull the dominant colors to generate a layout of swatches that the user can customize the orientation and shape of and overall look of the layout as well as create gradients from a collection of images to use in programs like photoshop. 
What Chore Does The Tool End: Creating a color script layout by hand and using the eyedropper tool to create swatches 
1 week goals: Design sleek UI that has simple settings and can generate decent layouts
2 week goals: Refine look/design of UI and anything that wasn't working properly and add more complex settings
3 week goals: Have the program function seamlessly and possibly have an in-photoshop option editor 

UI: https://drive.google.com/file/d/1-1poFaTcrw8bYwfcpXH836sC8DdxOisZ/view?usp=sharing

## How to install and run

### Windows
1. Install Python 3.10+ (`winget install Python.Python.3.12` in PowerShell).
2. Install the libraries the tool needs (pywin32 is how we talk to Photoshop on Windows):
   ```powershell
   python -m pip install pygame pywin32
   ```
3. Run the app:
   ```powershell
   python palette_gui.py
   ```

### macOS
1. Install Python 3.10+ (e.g. `brew install python`).
2. Install pygame (pywin32 is Windows-only and not needed):
   ```bash
   python3 -m pip install pygame
   ```
3. Run the app:
   ```bash
   python3 palette_gui.py
   ```

### Check the Photoshop connection first (either OS)
Before you trust a "Send to Photoshop", confirm the bridge can reach Photoshop:
```powershell
python photoshop_bridge.py --ping     # Windows
python3 photoshop_bridge.py --ping    # macOS
```
It prints something like `__result__ = Adobe Photoshop 27.11.0`. On macOS the
first call asks for permission to control Photoshop (System Settings >
Privacy & Security > Automation); if `--ping` fails, the bridge tells you
where to turn that back on. On Windows it says how to install pywin32 if it
is missing, and which Photoshop version it connected to.

### Send speed
"Sending to Photoshop" used to take 86-103 s for a 3-palette sheet. It now
builds the whole document with **Place Embedded** and wraps the build in a
single history state (`doc.suspendHistory`), so the same sheet lands in about
**41 s (~2.2x faster)**. The document it produces is unchanged - only the
route to it is faster. A representative sheet was checked against the pygame
render: swatches, images and gradient strips match pixel-for-pixel, and only
text anti-aliasing differs (pygame and Photoshop rasterize fonts differently).

### Text & fonts
Every word on the sheet is editable and can use three font faces. Click any
caption, title, hex label or free text box in the preview to select it (it gets
an outline and a blinking caret), then type to change it. The **text bar** under
the preview has:
- **Add Text** / **Delete box** (free text boxes only),
- **B** to toggle bold on the selected item,
- a **Sans / Serif / Mono** face picker,
- a **Size** slider.

`Add Text` drops a new box you can drag anywhere; a new box inherits the last
face you picked. Captions, the title and the hex labels are editable the same
way. The chosen face carries into the PNG **and** the Photoshop document, so the
PSD text matches what you see. Offline test: `python test_palette.py --no-live`
(131 checks); live round trip: `python test_palette.py` (140 checks).

