# Project Memory

## Environment
- Platform: Windows (Maya-specific workflow)
- Working directory: `C:\Users\missm\OneDrive\Documents\Default Project`
- Not a git repo
- Tools are for **Autodesk Maya** (user runs scripts in Maya's Script Editor)

## Context
User builds simple 3D props/scenery for Maya: playground slide, trees, ping pong table, etc.
They run scripts via **Windows > General Editors > Script Editor** → Open Script → Ctrl+Enter.
Also builds standalone 2D pygame games in this same folder (not Maya-related).

## Toolchain / environment (non-Maya)
- **Python IS on PATH now** (verified 2026-10-04): `python` resolves to
  `C:\Users\missm\AppData\Local\Programs\Python\Python312\python.exe` (3.12.10), and the
  `py` launcher resolves to `...\Python\Launcher\py.exe`. The old "Microsoft Store stub"
  problem is gone — plain `python ball_game.py` and `Start-Process -FilePath "python"` work.
  If it ever regresses, fall back to the full path:
  `& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" "path\to\script.py"`
  (note the `&` call operator and the quotes — the project path contains a space).
- **pygame 2.6.1** (SDL 2.28.4) installed into that Python. Install with
  `python -m pip install pygame`.
- **pywin32 312** installed into that Python 2026-10-10 (`python -m pip install pywin32`) —
  required by the Photoshop bridge for COM automation. `win32com.client.Dispatch("Photoshop.Application")`
  launches the app if it is not running; `GetActiveObject(...)` only attaches to a running one.
- **Canvas bridge (2026-10-11): `canvas_bridge.py`** talks to the user's school Canvas over its
  REST API (stdlib `urllib` only — no `requests`). Config comes from the environment:
  `CANVAS_URL` (their base URL; **custom domain**, not given to me) and `CANVAS_TOKEN` (a personal
  access token the user generates at Account > Settings > + New Access Token — **never** ask them
  to paste it). Token is never written to disk or printed. Commands: `whoami`/`--ping`, `courses`,
  `assignments`, `submissions`, `grades`, `submit --file|--text|--link`, `get`, all with `--json`.
  **Verified only against a local mock server** (`test_canvas_bridge.py`, 33 checks) — the live
  school instance and the real upload path are untested (I have no token/host).
- **Adobe Photoshop 2026 is installed** at `C:\Program Files\Adobe\Adobe Photoshop 2026\Photoshop.exe`
  (registry App Paths confirms it); its scripting version reports as `Adobe Photoshop 27.10.0`.
- No Node, npm, choco, scoop, or docker. `winget` **is** available.
- **Git 2.55.0.5 + GitHub CLI 2.102.0** installed via winget 2026-10-08. Like OpenCode, the
  installers edit PATH → only visible in **newly opened** terminals. In an old session, refresh with
  `$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")`.
- **GitHub bridge plan (2026-10-08, user request)**: user wants assistant to auto-push this
  folder's scripts to GitHub. Decisions so far: use an **existing repo** (URL not yet provided),
  upload **everything in the folder**. Remaining: user runs `gh auth login` themselves in their
  own new PowerShell (web-browser flow; **never** ask them to paste a token), gives me the repo
  URL, then I `git init` + add remote + commit + push. Folder is **not a git repo yet**;
  should add a `.gitignore` (`__pycache__/`, Maya temp files, `_maya_in.py`/`_maya_out.txt`,
  `_ps_in.jsx`/`_ps_out.txt`, `.mayaSwatches`) before the first push.
- **OpenCode CLI v1.18.30** installed via `winget install SST.opencode` → binary lands in
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages\SST.opencode_...\opencode.exe`. winget edits PATH,
  so `opencode` only resolves in **newly opened** terminals. Note the user also has
  OpenCode **Desktop** (`SST.OpenCodeDesktop`) — separate package, no CLI bundled.
- OpenCode docs recommend WSL over native Windows; WSL is present but unused so far.

## Model limitations
- This model does **not** accept image input. The user tried pasting `image.png`; if they
  report a graphical bug, ask them to paste the traceback/description as text.
- For debugging Python, always run the script and read stderr — guessing produced 4 real bugs
  in `bounce_game.py` on the first attempt (see below).

## Maya bridge (live session control)
- Maya **2027.2** at `C:\Program Files\Autodesk\Maya2027\`; `mayapy.exe` and `mayabatch.exe`
  live in its `bin\` for offline/batch runs.
- **Client: `maya_bridge.py`** — run Python inside the user's *open* Maya session:
  - `python maya_bridge.py script.py` → execute a file in Maya, print its output
  - `python maya_bridge.py -c "import maya.cmds as cmds; print(cmds.ls())"` → inline
  - `python maya_bridge.py --ping` → health check (prints Maya version)
  - flags: `--port 7001`, `--timeout 60`
  - exit code 1 when the captured output contains a traceback; `__result__ = <value>` in the
    script comes back as `__result__ = ...`.
- **How it works:** Maya's command port `127.0.0.1:7001` (`protocol="echo"`,
  `sourceType="python"`) evaluates a **single expression** and echoes its repr. The client
  writes the code to `_maya_in.py`, sends the one-liner
  `(exec(open(r'...\maya_hook.py').read(), globals()), globals()['run'](IN, OUT))[1]`, which
  execs the hook into that command's namespace; `run()` executes the staged file with
  stdout/stderr captured and writes `_maya_out.txt`; the client prints that file.
- **The port is stateless** — every command gets a fresh namespace (`x=7` then `x` in separate
  calls → `NameError`), and statements echo `None` while expressions echo their value. Put
  everything you need in one script, never spread state across calls.
- **Port dies when Maya restarts** unless it is re-enabled:
  `import maya.cmds as cmds; cmds.commandPort(name="127.0.0.1:7001", protocol="echo", sourceType="python")`
  (no `userSetup.py` existed as of 2026-10-04).
- BOM/encoding gotchas (real failures on 2026-10-04): PowerShell `Set-Content -Encoding UTF8`
  writes a **BOM**, which breaks `compile()` if not stripped → always read scripts with
  `encoding="utf-8-sig"`; the console is **cp1252**, so non-ASCII output raises
  `UnicodeEncodeError` on print → `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`.
- It changes the **live scene** — unlike `mayapy.exe`, there is no separate scratch file, so
  keep tests non-destructive (create + delete, or query only).

## Photoshop bridge (live session control)
- **Client: `photoshop_bridge.py`** — run ExtendScript (JSX) inside the live Photoshop session:
  - `python photoshop_bridge.py script.jsx` → run a file, print its output
  - `python photoshop_bridge.py --% -c "$.writeln(6*7)"` → inline (the `--%` matters, see below)
  - `python photoshop_bridge.py --ping` → health check (prints `Adobe Photoshop 27.10.0`)
  - `--debug` opens the Photoshop JavaScript debugger instead of failing silently
  - exit code 1 when the output contains `BRIDGE ERROR:`; `__result__ = <value>` in JSX comes
    back as `__result__ = ...` (same convention as Maya).
- **How it works:** Photoshop has **no command port**; on Windows the only external scripting
  route is COM/OLE automation via pywin32. The client attaches to the running
  `Photoshop.Application` (`GetActiveObject`, falling back to `Dispatch` which **launches**
  Photoshop if it is closed — the first call can take ~20-60s), writes the JSX to `_ps_in.jsx`,
  then calls `app.DoJavaScript(hook + '__bridge_run__("<in>", "<out>")', [], mode)`.
- `photoshop_hook.jsx` defines `__bridge_run__(inPath, outPath)`: reads the staged file with
  `File(...).encoding = "UTF-8"`, overrides `$.writeln` to capture output, `eval`s the source
  (so `var`/`__result__` land in `__bridge_run__`'s scope), writes the log + `__result__` to
  `_ps_out.txt` and returns the text. `#target`/`#include` directives are **not** supported
  (source is eval'd).
- **Live session:** unlike `mayapy.exe` there is no scratch app, so keep tests non-destructive
  (create a doc → act → `doc.close(SaveOptions.DONOTSAVECHANGES)`).
- Verified 2026-10-10: ping, `$.writeln` capture, `__result__`, multiple output lines, unicode
  (`café ✓`), BOM'd script files, error propagation (partial output + `BRIDGE ERROR` + exit 1),
  full DOM round trip (new doc → layer → rename → close), inline `-c`.

## Files created

| File | Purpose | Run method |
|------|---------|------------|
| `create_slide.py` | Builds a playground slide: curved slide surface, side rail tubes (circle extruded along curve), top platform + edge rails, ladder with posts/steps, support posts. One-shot script. | Open in Script Editor, run |
| `create_trees.py` | One-shot: 4 trees in a square, trunk + 2-3 foliage cones, fixed random seed (42). | Open in Script Editor, run |
| `tree_gui.py` | GUI "Tree Generator" window with sliders for tree count, trunk height/radius ranges, foliage layers/radius/height, placement (grid/line/random), seed, color pickers (trunk/foliage), "vary colors" checkbox. Uses lambert materials. | Open in Script Editor, run |
| `cactus_gui.py` | (Reworked, research-based) GUI "Cactus Generator" with 3 styles: Saguaro (ribbed column + ribbed crown + L-shaped arms with elbow spheres), Barrel (stubby ribbed column + squashed ribbed crown), Prickly Pear (stacked flattened pads). Ribs = sinusoidal radius displacement of cylinder/sphere vertices. Spine clusters at areoles along each rib crest: 1 long central spine + N radial spines fanned around it. Spike size controls: length min/max, radius, central spine scale, radial spines per areole, radial spread, areole row spacing. Spines are cones aimed with an orthonormal-basis transform matrix (base at surface, tip protruding outward perpendicular to the body; radials fan in the horizontal plane). Placement/colors/seed same as tree_gui. **Undo chunking**: `cmds.undoInfo(openChunk=True, chunkName="cactus_script")` at the very top of the script and `cmds.undoInfo(closeChunk=True)` at the very end (assignment requirement); `generate_cacti()` additionally opens/closes its own chunk (try/finally) so a single Ctrl+Z removes only the cacti that click created. | Open in Script Editor, run |
| `create_spiral.py` | **Created 2026-10-04 via the Maya bridge.** 48 cubes on a 4-turn helix (radius 3→14, height 0→40, size shrinking 55%), alternating blue `(0.10,0.35,0.95)` / pink `(0.98,0.35,0.65)` lambert materials, grouped as `spiral_cubes`, rotated to face outward, one undo chunk, `viewFit(all=True)` at the end. Re-run replaces the previous spiral (deletes the group + stray `spiral_cube_*` transforms). | `python maya_bridge.py create_spiral.py` |
| `maya_bridge.py` | **Maya bridge client (created 2026-10-04).** Sends a staged Python file into the live Maya 2027 session over command port `127.0.0.1:7001`, then prints the captured output. CLI: `python maya_bridge.py script.py`, `-c "code"`, `--ping`, `--port`, `--timeout`. Staging files `_maya_in.py` / `_maya_out.txt` live next to it. | `python maya_bridge.py script.py` |
| `maya_hook.py` | Helper exec'd *inside* Maya by the bridge one-liner; defines `run(inp, out)` which compiles/execs the staged file with stdout/stderr captured and writes the log + `__result__` to the output file. | (called by the bridge) |
| `photoshop_bridge.py` | **Photoshop bridge client (created 2026-10-10).** Runs ExtendScript (JSX) in the live Photoshop 2026 session over COM (`win32com` → `Photoshop.Application.DoJavaScript`), then prints the captured output. CLI: `python photoshop_bridge.py script.jsx`, `--% -c "jsx"` (PowerShell), `--ping`, `--debug`. Attaches to a running Photoshop or launches one; staging files `_ps_in.jsx` / `_ps_out.txt` live next to it. Exit code 1 on `BRIDGE ERROR:`. | `python photoshop_bridge.py script.jsx` |
| `photoshop_hook.jsx` | ExtendScript hook eval'd *inside* Photoshop: `__bridge_run__(inPath, outPath)` reads the staged JSX, captures `$.writeln` output, evals the source (so `__result__` is readable), writes the log + `__result__` to `_ps_out.txt`. | (called by the bridge) |
| `test_photoshop.jsx` | **Created 2026-10-10.** Bridge test: proves the DOM round trip — reads `app.name`/`version`, creates a 256x256 RGB doc, adds + renames a layer, prints multiple lines incl. unicode, closes the doc with `SaveOptions.DONOTSAVECHANGES`, `__result__ = "all checks passed"` (or the failure list). | `python photoshop_bridge.py test_photoshop.jsx` |
| `canvas_bridge.py` | **Created 2026-10-11.** Canvas LMS REST client (stdlib `urllib` only). Config from env: `CANVAS_URL` + `CANVAS_TOKEN` (never stored/printed). Commands: `whoami`/`--ping`, `courses [--all]`, `assignments COURSE`, `submissions COURSE ASSIGN`, `grades [COURSE]`, `submit COURSE ASSIGN --file\|--text\|--link`, `get PATH [--paginate]`; `--json` on any command. Follows `Link` pagination, explains 401/403/404, exits 1 on error. `submit --file` does the 3-step Canvas upload (`.../submissions/self/files` → multipart POST to `upload_url` → `submission[file_ids][]`). | `python canvas_bridge.py courses` (after setting the two env vars) |
| `test_canvas_bridge.py` | **Created 2026-10-11.** Offline test for `canvas_bridge.py`: spins up an in-process mock Canvas HTTP server, points the bridge at it, and exercises every command (whoami/ping, courses incl. **pagination** via `Link`, assignments, submissions, grades, `submit --text` and `submit --file` upload, `get --json`) plus the bad-token/missing-config exit-1 paths. 33 checks. | `python test_canvas_bridge.py` (expect exit 0, "all checks passed") |
| `human_viewer.py` | **Created 2026-10-10; reworked into an anatomical human skeleton.** Standalone pygame app: a **human skeleton** (`BONE` ivory, `BONE_DARK` teeth/cartilage, `SOCKET` dark eye sockets/nasal cavity; skull with cranium+face+jaw+eye sockets+nasal cavity+teeth, cervical vertebrae, ribcage of 9 rib pairs + sternum + clavicles + scapulae over a vertebral column, sacrum/iliac/ischium/pubis pelvis, humerus / radius+ulna+olecranon / carpals+metacarpals+4 fingers+thumb, femur with angled neck+greater trochanter / patella+tibia+fibula / calcaneus+talus+midfoot+toes) built from a **bone skeleton** and drawn by a hand-rolled software renderer (painter's algorithm on average face depth + Lambert shading, no culling → `abs(dot(n, LIGHT))`), gradient backdrop, floor + soft shadow. Proportions follow standard anthropometry: feet at y=0, ~1.72 m tall, hip pivot at the greater trochanter (~half height), shoulder ~0.82 H, elbow ~0.63 H, wrist ~0.49 H, knee ~0.28 H, ankle ~0.04 H. **Click-drag a joint to pose that limb** (rotation carries down the chain via forward kinematics); drag empty space to orbit; wheel zoom. GUI: **"Camera angle" slider (0-360°)**, camera-height, distance sliders, arrow keys orbit/zoom, **"Reset pose"** button, **"Import model..."** button (native file picker → loads an OBJ or Maya .ma/.mb via `model_import.py`, auto-fits + centers it on the floor, hides joints & disables posing so you can only orbit/zoom), **"Use skeleton"** button (restores the built-in skeleton), **"Open in Photoshop"** (renders to `human_view.png` 1000x1000 and imports it as a layer named "Skeleton render" in the "New Illustration" document, replacing that document from the previous send), **"Save PNG"**, and an **"Auto-sync to Photoshop"** toggle (0.35 s after the last change). Keys: `R` reset pose, `A` auto-sync, `S` send, `Esc` quit. While a model is imported `R` is a no-op and the status line points at "Use skeleton". | `python human_viewer.py` |
| `turnaround_sheet.py` | **Created 2026-10-11.** Builds a character/object **turnaround sheet** and drops it into Photoshop as **one layer**. CLI: `python turnaround_sheet.py INPUT... [--views 3|4|5|8] [--orientation landscape|portrait] [--dpi 150] [--title "..."] [--elevation 8] [--out turnaround_sheet.png] [--send] [--doc-name] [--layer-name]`. Inputs may be mixed: **images** (png/jpg/bmp/tga/gif/webp — each becomes one view, labelled by filename stem), **Photoshop files** (`.psd`/`.psb` — flattened to a temp PNG via `flatten_psd()`, which opens the doc in Photoshop through `photoshop_bridge`, forces RGB/8-bit + `displayDialogs=NO` and `saveAs` PNG; cached by path+mtime+size so rebuilds are cheap) and **3D files** (Maya `.ma`/`.mb` or `.obj` — rendered from the chosen rotation angles with its own software renderer, so **no Maya render setup/lights/Arnold needed**; faces come from `model_import`). Sheet = 11x17in at `--dpi` (landscape default 17x11 → 2550x1650 @150; portrait 11x17), white background, header `--title` top-centre, a light **ground line**, views evenly spaced left→right at **one shared scale (orthographic; camera-relative key light)** with a **caption under each pose**. Standard rotation order left→right (research-based): FRONT, 3/4, SIDE, 3/4 BACK, BACK (`--views 5`; sets for 3/4/8 too). Views render at `SS=2` supersample then smoothscale for AA. Saves the composite PNG, then `send_to_photoshop()` runs PS JSX (reuses the human_viewer pattern) that closes any doc named `--doc-name`, creates an 11x17in RGB doc at the DPI (saved/restored `rulerUnits`), duplicates the sheet in as `--layer-name`, and **removes the "Background" layer so exactly one layer remains**. `photoshop_bridge.run` launches Photoshop if it is closed. **Free text boxes:** `build_sheet(..., texts=[...])` plus the shared `draw_texts(surface, texts, px_per_inch)` / `text_font_for()` stamp user text at **fractional positions** (`x`,`y` are 0..1 of the surface, centred; `DEFAULT_TEXT_SIZE_IN=0.20`); each item may carry a `font` (a `SysFont` name list) so a box's face renders the same on the sheet and in the GUI preview. | `python turnaround_sheet.py MODEL.ma --title "Name" --send` |
| `turnaround_gui.py` | **Created 2026-10-11.** A **Frutiger Aero** pygame GUI front-end for `turnaround_sheet.py`. Window "Turnaround Studio" (1120x820): aqua sky→water vertical gradient, soft sun glow, and hand-rolled glass widgets — `glass_panel()` (frosted rounded panel + soft drop-shadow + top gloss + bright rim) and `glossy_button()` (vertical gradient clipped to a rounded mask via `BLEND_RGBA_MULT`, top-half glass highlight). Panels: **Source files** (list of chosen inputs with IMG/PS/3D tags, click-row-to-select, Add file…/Remove/Clear all), **Options** (Sheet title text field with blinking caret + click-to-focus, Rotation views 3/4/5/8 segmented, Orientation Landscape/Portrait, Resolution 150/300 dpi), **Preview** (scaled composite in a glass frame). Buttons: Save PNG As…, Build preview, Send to Photoshop. `add_files(paths)` is the testable core of the file picker (`pick_files()` wraps a tkinter `askopenfilenames`; images + `.ma/.mb/.obj`). Build/Send just call `ts.build_sheet` / `ts.send_to_photoshop`. **Add Text:** a "Text boxes" bar inserts free text boxes (`Add Text` / `Delete box` / `B` bold) with a **Font** picker (`FONT_ORDER` = Sans/Serif/Mono → `FONT_FACES` SysFont lists) and a **Size** `Slider` (0.08–0.60 in, shown in pt; `TEXT_MIN_IN`/`TEXT_MAX_IN`); click a box on the preview to select+edit (type to change, Enter/Esc to stop editing), drag it to place it anywhere. Font/size/bold edit the selected box live; a new box inherits the last font choice. Boxes are overlaid live on the preview (`ts.draw_texts` at `dpi*preview_scale`) and stamped onto the saved/sent sheet by `composited_sheet()`, so the base sheet stays text-free (no double-draw during drag). Keys: Enter=build, Esc=quit. Headless smoke test drives `add_files`, row selection, option setters, title typing, build, remove/clear and a full `draw()`. | `python turnaround_gui.py` |
| `model_import.py` | **Created 2026-10-10.** `load_model(path) -> (faces, summary)` for the viewer. **OBJ** parsed directly (`v` / `f` with `v`, `v/vt`, `v/vt/vn`, `v//vn`; negative indices handled; `usemtl` → colours from the referenced `.mtl`'s `Kd`, default grey `(0.72,0.73,0.76)`). **`.ma`/`.mb` converted to a temp OBJ by Maya's `mayapy.exe`** (found under `C:\Program Files\Autodesk\Maya*\bin` — newest wins — or `%MAYAPY%`), because a `.ma` mesh with construction history stores **no vertex data** and history-free meshes use the compressed `polyFaces` (`f 4 <signed edge idx>...`) format; letting Maya evaluate and export is the only robust route. `fit_to_view(faces)` centers the model on the floor at the origin and scales its largest extent to `FIT_SIZE=1.7` (so the fixed camera sliders still work); `FIT_TARGET_Y`/`FIT_DISTANCE` are what the viewer's camera uses. Temp dir is removed after parsing (300 s subprocess timeout). | `import model_import` |
| `test_human_viewer.py` | **Created 2026-10-10.** Headless (dummy SDL) checks for `human_viewer.py`: 53 assertions — mesh bounds, camera basis, projection, slider mapping, PNG written, rotation changes the image, **bone-tone pixels** with the head in the upper half, **skeleton/posing (elbow moves the hand but not the head, shoulder carries elbow+wrist, joint picking by click, reset restores rest, simulated mouse drag swings the leg)**, **model import (OBJ face/material-colour parsing, `fit_to_view` scale + floor placement, imported mesh renders in its material colour, posing disabled while imported, skeleton restore)**, and the live Photoshop hand-off (closes its "New Illustration" doc afterwards). **Double-click friendly**: when launched from Explorer (an `explorer.exe` ancestor via `py.exe`) it holds the console open at the end with "Press Enter to close..." so results are readable; run from a terminal it exits immediately. | `python test_human_viewer.py` (expect exit 0, "all checks passed") |
| `spiral_gui.py` | **Created 2026-10-04 via the bridge.** GUI "Spiral Generator" — live window for the cube spiral: float sliders (radius start/end, turns, height, cube size), int slider (count 1–150), color mode optionMenu (Gradient / Alternate / Solid), Color A + Color B pickers, gradient cycles (only enabled in Gradient mode), Rebuild / Delete Spiral buttons. **Every control has `dragCommand=changeCommand=update`** → the scene rewrites continuously while dragging (delta create/delete of `spiral_cube_*` + one `spiral_color_%03d` lambert per cube; whole update in one `undoInfo` chunk = 1 Ctrl+Z per drag). Adopts an existing spiral on load: `normalize()` renames any legacy 2-digit names (`spiral_cube_00`) to canonical `spiral_cube_000` via temp names, `adopt()` forceElement-assigns index materials, then `update()` syncs scene↔sliders. Re-running the script seeds new widgets from the **old window's live values** (`read_values()` before `deleteUI`) so settings survive reload. Stashes `cmds._spiral_gui = {update, read, build, delete, rebuild, widgets, defaults}` for bridge-side tests. | `python maya_bridge.py spiral_gui.py` |
| `test_spiral_gui.py` | **Created 2026-10-04.** Bridge-side regression test for the spiral GUI: 26 checks (adopt/canonical names, count up/down incl. materials + group children, gradient/alternate/solid colours vs the triangle-wave formula, positions/scale vs slider values, cycles enable state, single-undo-per-drag, rebuild). Snapshots the user's slider values first and restores them in a `finally`. | `python maya_bridge.py test_spiral_gui.py` (expect exit 0, `__result__ = 'all checks passed'`) |
| `ping_pong_table.py` | (Existing user file, not created by assistant) | — |
| `bounce_game.py` | **Created 2026-09-29.** Breakout-style paddle game (pygame, 800x600). Paddle follows mouse or arrow keys; bounce angle set by where the ball hits the paddle. Ball accelerates on every paddle/brick hit (capped 780). 3 levels with +1 brick row each (max 7), score 10/brick, 3 lives, win/lose states. Particles + white screen flash on brick break. Tones generated in code via `make_beep()` (no sound files) with silent fallback if mixer init fails. Brick reflection picks the smaller overlap axis (X vs Y). Mouse/arrows move, `Space` launch/continue, `R` restart, `Esc` quit. | `py bounce_game.py` |
| `ball_game.py` | **"Planet Breaker"** (2D pygame): the player is a **small rocket ship** — `draw_ship()` draws a hull/nose/canopy polygon plus a short flickering engine flame, rotated to `self.ship_heading` (cached from velocity every frame, so the nose keeps pointing where the ship is headed even at near-zero speed). **Left click fires a bolt** at the cursor via `Game.fire()` (`FIRE_DELAY`=0.16s rate limit, `set_speed(len-45)` recoil); bolts are 11px streaks (`Bolt`, `BOLT_SPEED`=720, `BOLT_LIFE`=1.2s) that die on walls/expiry and deal 1 damage on planet contact. Holding the left button still drag-steers the ship (pointer-drag velocity pull), so one button both aims and shoots. Ram collisions still reflect + chip. Motion otherwise unchanged: wall ricochet, accelerating speed (capped), bounce counter. **Planets** replace the old spiky stars: 5 kinds (cratered moon, banded gas giant, ringed, ice, volcanic) pre-rendered once per planet via `render_planet()` — base disc, surface detail (craters/bands/storm/cracks), masked to the disc with `BLEND_RGBA_MULT`, two-step offset shadow disc for the terminator, rim-light arc on the lit limb, atmosphere ring; drawn at 3x supersample then `smoothscale` down. Ringed planets draw two `draw_arc` halves (top behind the planet, bottom in front). Collision is now circle-vs-circle. Damage from bolts and rams both run through `damage_planet()` (crack 2-3 hits, then shatter); **no particle trails anywhere** (no ship trail, no debris chunks, no meteor tail — user removed them all; `Shard` class deleted). Volcanic planets are shooters: glow while charging then fire meteors at the ship (fireball head, bounce off walls, die after 3 bounces); a hit costs a life (3 lives, 1.3s invulnerable blink, meteors+bolts cleared, ship respawns centre), 0 lives = GAME OVER (`Space` restarts). Planets drift slowly and bounce off the screen edges; starfield background. `difficulty()` ramps per level: planets 5→8, shooters 1→6, fire interval 2.3→0.55s, meteor speed 130→520, volley 1→3 (level 4/8), planet hits +1 from level 6. `Space` reset ship, `N` next level, `R` randomize hull color, `Esc` quit. | `python ball_game.py` |

## Key technical notes (Maya gotchas learned)
- Windows: `filePath` for Open Script must be absolute.
- `cmds.radioButtonGrp(..., select=...)` takes an **int index (1-based)**, not a string — map layout names via dict `{"grid":1,"line":2,"random":3}`. Use `columnWidth3` for 3 buttons, not `columnWidth`.
- `cmds.intFieldGrp` is queried with `value1=True`; `cmds.intField` is a different widget.
- **`overrideColorRGB` component access via `.r/.g/.b` fails; set all three at once** with `cmds.setAttr(obj.overrideColorRGB, r, g, b)`.
- Viewport override attributes on the **transform** are unreliable for RGB colors → **use lambert materials instead**: `cmds.shadingNode("lambert", asShader=True, name=mat)`, `cmds.setAttr(f"{mat}.color", r, g, b, type="double3")`, assign with `cmds.select(obj); cmds.hyperShade(assign=mat)`.
- Colors only display in **Smooth Shade All** viewport mode (press 5).
- For per-tree color variation with shared materials: create per-object materials named `tree_trunk_mat_{tid}` / `tree_foliage_mat_{tid}`; shared mats are `tree_trunk_mat` / `tree_foliage_mat`.
- Deleting by pattern: `cmds.ls("tree_*")` also matches `tree_trunk_mat_*` names — harmless due to `objExists` guards.
- Aiming a cone/cylinder at a direction: **don't use `aimConstraint`** — on constraint delete the rotation may not bake (reset to identity). Instead build an orthonormal basis (a=perp up, d, b=cross(d,a)) and set the transform matrix via `cmds.xform(obj, ws=True, m=[...])` (row-major: rows = X,Y,Z axis images + translation). Note `polyCone`/`polyCylinder` pivots sit at the geometry **center**, so after orientation, translate by `pos + dir*len/2` to put the base on the surface/tip outward (and spine body centered at pos).
- Ribbed cactus columns: higher-resolution `polyCylinder`, then for each wall vertex (skip cap interior via `distance < radius*0.98`) set radius = `R*(1 + depth*cos(ribs*theta))` using `cmds.xform(v, ws=True, t=...)`.
- Cactus crown (`make_ribbed_crown`): starts as a **unit sphere** (radius 1) minus bottom-half faces, so it MUST be scaled to the body radius *inside* the function (`cmds.xform(dome, s=(r,r,r))`) — otherwise the top is ~2-3x the body. Rib-displace before scaling, using the same crest angles as the column so the rims match. Barrel style then adds only a relative Y-squash `(1,1,0.55)`; don't re-scale by body radius there.
- **`cmds.xform` has no `p` (=pivot) flag** — passing `p=(0,0,0)` raises "Invalid arguments for flag 'p'. Expected int". Use `piv=` or omit it (objects are at origin anyway). `cmds.rotate(..., p=(0,0,0))` is fine.

- **`cmds.rotate(obj, 0, deg, 0, os=True)` fails** — mixed object + numbers positional args make Maya read `0` as an object name (`TypeError: Object 0 is invalid`). Use `cmds.xform(obj, os=True, ro=(0, deg, 0))`.
- **`cmds.sets(obj, e=True, forceElement=mat)` fails "NOT a set"** — `forceElement` wants a *shading group*, not a material. Build both: `shadingNode("lambert", asShader=True, name=mat)` + `setAttr(mat.color, r,g,b, type="double3")`, then `sets(renderable=True, noSurfaceShader=True, empty=True, name=sg)` + `connectAttr(mat+".outColor", sg+".surfaceShader", force=True)`, and pass **sg** to `forceElement`.
- **Membership lives on the shape, and `sets -q` on an object lies**: `cmds.sets(transform, q=True)` / `cmds.sets(shape, q=True)` both return `None` even when assigned, and `listConnections(transform, type="shadingEngine")` is empty. Query the set instead: `cmds.sets("mySG", q=True)` → `['cube1Shape', ...]`.
- `cmds.ls("pat*")` returns **shapes as well as transforms** — deleting the transforms first makes the shape names stale → `ValueError: No object matches name xShape`. Use `ls(pat, type="transform")` and guard each delete with `cmds.objExists()`.
- **`colorSliderGrp` uses the `rgb` flag, not `value`**: create `cmds.colorSliderGrp(label=..., rgb=(r,g,b), dragCommand=..., changeCommand=...)`, query `q=True, rgb=True` → `[r,g,b]`. `value=True` raises `Invalid flag 'value'`.
- **`cmds.objectType()` lies about slider controls** — for `floatSliderGrp`/`intSliderGrp` it returns `rowGroupLayout`, so never dispatch widget edits on it. Probe edit flags with try/except instead (`intSliderGrp(name, e=True, value=v)` → `floatSliderGrp(..., value=v)` → `colorSliderGrp(..., rgb=v)` → `optionMenu(..., value=v)`).
- **`optionMenu(value=...)` is invalid at creation** (`RuntimeError: Item not found: Gradient` — menu items don't exist yet). Create the menu, add `menuItem`s, *then* `optionMenu(name, e=True, value=...)`.
- **`cmds.setAttr(attr, q=True)` returns `None` for a double3** — use `cmds.getAttr(mat + ".color")[0]` → `(r, g, b)`.
- **Name patterns can collide across generations** (`create_spiral.py` wrote `spiral_cube_00`, the GUI writes `spiral_cube_000`; both match `spiral_cube_*`, and both parse to index 0 → two cubes share one material and tail-deletes pick the wrong one). Normalize on load by renaming through temp names (`spiral_tmp_%04d` → `spiral_cube_%03d`), and treat the cube's **position in the sorted list** as its index, never the parsed name.
- **Python callbacks passed to UI controls survive the bridge script exiting** — the function object keeps its exec'd globals dict alive, so `dragCommand=update` still works on later bridge calls. (The port's *namespace* is still stateless; it's the callback reference that holds the state. If you rebuild the window, the stash `cmds._spiral_gui` points at the new closures.)
- Seed widget values from the **old window before `deleteUI`** when re-running a GUI script, otherwise a reload silently resets the user's slider tweaks.

## Key technical notes (Photoshop gotchas learned)
- **Photoshop has no scripting port** (unlike Maya's command port). On Windows, external control
  is COM-only: `win32com.client.GetActiveObject("Photoshop.Application")` attaches to a running
  Photoshop, `Dispatch(...)` **launches** it if closed (cold start took ~19s here). A first
  `DoJavaScript` call after launch can take a minute.
- **ExtendScript has no `print`** — use `$.writeln(text)` (one line per call). `$.writeln` is a
  plain property on the global `$`, so you can swap it for a collector and restore it afterwards;
  that's how the hook captures output.
- Painting a color: `$.writeln("café ✓")` round-trips fine (files written `UTF-8`, read back with
  `utf-8-sig` to swallow a possible BOM).
- New/close a scratch doc: `app.documents.add(256,256,72,"name",NewDocumentMode.RGB,DocumentFill.WHITE)`
  then `doc.close(SaveOptions.DONOTSAVECHANGES)`; `doc.artLayers.add()`, `layer.name = "..."`,
  `doc.width.value` reads the number off a UnitValue.
- **`eval(source)` inside a function scopes the payload's `var`s to that function**, so
  `if (typeof __result__ !== "undefined")` right after the `eval` can read what the script set.
  `#target` / `#include` directives can't be used (the source is eval'd, not file-run).
- **PowerShell 5.1 strips double quotes** out of a single-quoted argument when calling a native
  exe: `-c '$.writeln("x")'` reaches Python as `$.writeln(x)` and splits at spaces (argparse
  "unrecognized arguments"). Use a script file, or the stop-parsing symbol:
  `python photoshop_bridge.py --% -c "$.writeln(6*7)"`. Everything after `--%` is literal, so
  don't append `; more; commands` to that same line.
- **Photoshop has no live 3D viewport any more** — Adobe retired the 3D engine in v23 (2022),
  so Photoshop 2026 cannot render a 3D model. The only sane "view the model in Photoshop"
  pattern is **render the current view to a PNG and import it as a layer**: close any open doc
  whose `name` equals `DOC_NAME` ("New Illustration"), then `app.documents.add(...)` a fresh
  doc and duplicate the opened PNG's layer into it. That is what
  `human_viewer.send_to_photoshop` does, so every new camera angle replaces the imported layer
  instead of piling up documents. `app.documents[i].name` compares against the *document* name
  (the basename), not the path.
- **A modal Photoshop dialog blocks ALL COM scripting** with
  `(-2147417846, 'The message filter indicated that the application is busy.')` — even a plain
  `--ping` fails, and the call can hang (Python-side timeout) until the dialog is dismissed.
  Opening an **untagged PNG** (our pygame renders carry no ICC profile) pops the "Missing
  Profile" dialog and triggers exactly this; the doc opens flagged with a trailing `#` in its
  title. Fix: begin the JSX with `app.displayDialogs = DialogModes.NO;`. To clear an already
  stuck dialog without a COM call, focus Photoshop and send Escape/Enter
  (`$ws=New-Object -ComObject wscript.shell; $ws.AppActivate((Get-Process Photoshop).Id);
  $ws.SendKeys("{ESC}"); $ws.SendKeys("{ENTER}")`) — after that `--ping` responds again.
- **Frontmost-document rules when copying a layer across documents** (became real errors here):
  `src.activeLayer.duplicate(doc, ...)` needs **src** frontmost ("You can only duplicate layers
  from the frontmost document"), while renaming the placed layer (`placed.name = ...`) and
  `src.close(...)` each need **their** document frontmost ("The requested action requires that
  the target document is the frontmost document"). Set `app.activeDocument` immediately before
  every such op: `activeDocument = src` → duplicate → `activeDocument = doc` → rename →
  `activeDocument = src` → close → `activeDocument = doc`.
- **Exporting an open doc to PNG**: `doc.saveAs(new File(out), new PNGSaveOptions(), true, Extension.LOWERCASE)`
  writes the flattened composite as a new copy (original stays open) — that's how
  `turnaround_sheet.flatten_psd()` converts `.psd/.psb` inputs. Force
  `app.displayDialogs = DialogModes.NO` first (an untagged doc pops the "Missing Profile"
  dialog), and coerce to RGB/8-bit (`doc.changeMode(ChangeMode.RGB)`,
  `doc.bitsPerChannel = BitsPerChannelType.EIGHT`) because PNG export needs RGB/8-bit.
  There is **no `selectEllipse`/`selectRectangle`** — set a selection with
  `doc.selection.select([[x,y],...])` (polygon points); `doc.selection.fill(color)` and
  `opts = new PhotoshopSaveOptions()` (for PSD) are the other bits needed to script-create tests.

## Key technical notes (Canvas gotchas learned)
- **Auth is a bearer token**, `Authorization: Bearer <token>`; the token is a *personal access
  token* the user makes in Canvas (Account > Settings > + New Access Token). Treat it like a
  password: read it from `CANVAS_TOKEN`, never log or commit it. 401 = bad/expired token,
  403 = token lacks scope, 404 = wrong id **or** no access to that course.
- **Only stdlib is available** (no `requests`): use `urllib.request` + `urllib.parse`. POST bodies
  are `application/x-www-form-urlencoded` (Canvas uses Rails-style `submission[body]` keys); file
  upload uses a hand-built `multipart/form-data` body.
- **Pagination is in the `Link` response header** (`rel="next"`), not the body. `canvas_bridge.api()`
  follows it when `paginate=True` (guarded against runaway loops).
- **File submission is 3 calls**: (1) `POST /api/v1/courses/:c/assignments/:a/submissions/self/files`
  with `name`+`size` → returns `upload_url`+`upload_params`; (2) multipart `POST` the file to
  `upload_url` (S3/Instructure; no auth header needed there) → returns the file JSON with `id`;
  (3) `POST .../submissions` with `submission[submission_type]=online_upload` and
  `submission[file_ids][]=<id>`. Text/link submissions skip the upload and use
  `online_text_entry`+`submission[body]` / `online_url`+`submission[url]`.
- **`--json` must sit *after* the subcommand** (it lives on each subparser via a shared `parents=`
  parser). A top-level `--json` would be silently overridden by the subparser's default — the
  classic argparse "subparser defaults clobber parent values" gotcha; `main()` also `getattr`s a
  default for the bare `--ping` path where no subparser runs.
- Console is cp1252 → course names can raise `UnicodeEncodeError`; `canvas_bridge.py` reconfigures
  stdout to `utf-8, errors=replace`.
- **Verification:** `test_canvas_bridge.py` is a *mock* Canvas (`ThreadingHTTPServer`) so it runs
  offline; the **live** instance + real upload path are still untested (no token/host here).

## Key technical notes (pygame gotchas learned)
- **Cross-platform (added 2026-10-11)**: `turnaround_sheet.py` / `turnaround_gui.py` /
  `model_import.py` now run on **Windows, macOS and Linux** (building sheets); only the
  Photoshop *send* is OS-bound. Changes: fonts use a comma-separated `pygame.font.SysFont`
  fallback list `FONT_CANDIDATES` ("Segoe UI, Helvetica Neue, Arial, DejaVu Sans, Liberation
  Sans, Noto Sans, FreeSans...") instead of Windows-only `segoeuib`; `model_import.find_mayapy()`
  searches `%MAYAPY%`, `PATH`, then `C:\Program Files\Autodesk\Maya*` (Win),
  `/Applications/Autodesk/maya*/Maya.app/Contents/bin/mayapy` (Mac) and `/usr|/opt/autodesk/...`
  (Linux); `human_viewer.photoshop_running()` returns `True` on Mac if an
  `/Applications/Adobe Photoshop*.app` exists, `None` only when pywin32 is missing on Windows.
- **`photoshop_bridge.py` is now cross-platform**: Windows keeps the COM path
  (`GetActiveObject`/`Dispatch` → `DoJavaScript`); **macOS** writes the hook+call to a staged
  `_ps_run.jsx` and runs it through AppleScript — `osascript -e 'set jsxCode to read (POSIX file
  "…") as «class utf8»' -e 'tell application "Adobe Photoshop NNNN" to do javascript jsxCode
  [showing debugger]'` — then reads `_ps_out.txt` as usual (the app name comes from the newest
  `/Applications/Adobe Photoshop*.app`); **Linux** (no Photoshop) raises a clear `RuntimeError`.
  `connect()` returns the app-bundle *path* (a `str`) on Mac and the COM object on Windows, and
  `run()` branches on `isinstance(app, str)`. On Mac, `tell application … to do javascript` also
  *launches* Photoshop if closed (same "first call is slow" caveat as Windows).

- **A blit of an SRCALPHA surface does NOT erase what is underneath** — where the source
  alpha is 0 the destination keeps its old pixels. Drawing a starfield that way instead of
  `fill()` leaves every moving object permanently duplicated (ghosts/smears). Always
  `world.fill(BG)` first, then blit overlays.
- **`pygame.draw.arc` in pygame 2.6.1 IGNORES `start_angle`/`stop_angle`** — it always
  draws the *full* ellipse/circle outline. Use a sampled polyline helper instead:
  `math.cos/sin` points → `pygame.draw.lines(surface, color, False, pts, width)`.
  Its 4th/5th args are a **rect**, not (center, radius) — `arc(s, c, (50,50), 20, 0, 90)`
  raises "rect argument is invalid". Angle convention: 0 = right, 90 = **down** (y grows
  down), 180 = left, 270 = up.
- Mask generated content to a shape by drawing a white circle on an SRCALPHA surface and
  `blit(mask, (0,0), special_flags=pygame.BLEND_RGBA_MULT)` — multiplies RGB *and* alpha,
  so pixels outside the circle become fully transparent.
- **Always open a real window with `pygame.display.set_mode((W, H))`.** There is no
  `pygame.display.Surface(...)` — it raises `AttributeError`. (`pygame.Surface` exists but
  is offscreen-only and gives no visible window.)
- `pygame.draw.circle()` takes a **center `(x, y)` pair**, not a `Rect`. Passing `rect`
  raises `TypeError: center argument must be a pair of numbers`.
- Mixer sample buffers must be **signed** 16-bit. `int.to_bytes()` on a negative sample
  raises `OverflowError: can't convert negative int to unsigned` — build them with
  `array("h")` and pass `buf.tobytes()` to `pygame.mixer.Sound(buffer=...)`.
- Guard audio with try/except `pygame.error` around `pygame.mixer.init()` — headless/VM
  machines have no audio device and it would otherwise kill the game at startup.
- `Start-Process -ArgumentList` **splits on spaces** — a path with spaces silently becomes
  "No such file or directory". Wrap it in escaped quotes: `-ArgumentList '"C:\my dir\game.py"'`.
- `pygame.mixer.pre_init(...)` must be called before `pygame.init()` to take effect.
- A running game loop makes a foreground `bash` call hang until timeout. That's success, not
  a crash — launch it with `Start-Process` and check `$p.HasExited` instead.
- Bounce the ball off a rect by comparing `overlap_x` vs `overlap_y` and reversing the
  velocity component with the *smaller* overlap.
- **Headless verification of a pygame game works and is the fastest way to test changes.**
  Set `$env:SDL_VIDEODRIVER="dummy"; $env:SDL_AUDIODRIVER="dummy"`, then
  `python -c "import ball_game as bg; g = bg.Game(); ..."` and drive the game directly:
  `g.update(1/60.0, mouse)`, `g.draw()`, and `pygame.event.post(pygame.event.Event(...))`
  to fake input through `g.handle_events()`. Lets you assert state (planet hits, lives,
  score, list lengths) and even count pixels via `g.world.get_at((x,y))` without a window.
  A foreground `Game().run()` would block forever — never call it in a test.
- **Relaunching the game after an edit:** kill the old window by title, then start a new one
  and confirm the PID:
  `Get-Process python | ? { $_.MainWindowTitle -like "*Planet*" } | Stop-Process -Force`
  then `Start-Process -FilePath "python" -ArgumentList "ball_game.py" -WorkingDirectory "<project dir>"`
  → `Get-Process python | Select Id, MainWindowTitle`. The user tests by looking at the
  window, so always relaunch after a visual/logic change.
- **Double-clicking a `.py` in Explorer** runs `py.exe "<file>"` in a console that closes the
  moment the script ends (so a plain test looks like "nothing opened"). `.py` is associated
  with `py.exe` under `HKCU\SOFTWARE\Classes\Python.File`. To keep a console script readable on
  double-click, pause at exit only when double-clicked: detect it by walking the ancestor
  process chain (Toolhelp32 `CreateToolhelp32Snapshot`) — a real double-click shows
  `py.exe → explorer.exe`, a terminal run has a shell (`powershell.exe`/`cmd.exe`) ancestor.
  `test_human_viewer.py` does this via `_owns_console()` + `atexit`. (Launching through
  `Shell.Application.ShellExecute` from this session does **not** reproduce it — it inherits
  the opener's ancestry; use `Start-Process explorer.exe -ArgumentList '"<file>"'` instead.)
- **numpy is NOT installed** in this Python (only stdlib + pygame/pywin32), so software 3D
  rendering must be pure Python (tuples/lists + `math`). Fine for a few hundred faces; avoid
  per-pixel loops on big surfaces (old 1000x1000 backdrop gradients are fine because they are
  cached — `human_viewer.backdrop()` memoises by size).
- **Software-render a mesh** (see `human_viewer.render_view`): transform verts into camera
  space, drop faces behind the near clip, project, then **painter's algorithm** — sort faces by
  average depth (far→near) and `draw.polygon` them. Shade with `abs(dot(normal, LIGHT))` so
  back faces aren't black (no back-face culling → double-sided). Degenerate quads (sphere poles
  where two verts coincide) draw fine. A `draw.polygon` call with < 3 points is safest guarded
  (`if all(projected)`), not relied upon.

## human_viewer.py architecture (for future edits)
- Constants: `BONE` (ivory) / `BONE_DARK` (teeth/cartilage) / `SOCKET` (dark eye sockets &
  nasal cavity; the only near-black tone), `LIGHT`, `AMBIENT=0.38`, `DIFFUSE=0.68`, `FOV=34`,
  `WINDOW=(980,700)`, `VIEWPORT=Rect(12,12,956,500)`, `PNG_PATH=human_view.png`,
  `VIEW_NAME="human_view.png"`, `DOC_NAME="New Illustration"` (Photoshop doc the render is
  imported into), `LAYER_NAME="Skeleton render"`, `JOINT_RADIUS=16`, `ROT_PER_PIXEL=0.014`
  (radians of limb rotation per pixel dragged).
- Vector helpers (`add/sub/dot/cross/norm`) on plain tuples; primitives `box`, `cylinder`,
  `sphere` (squash for ellipsoids), `loft(rings, color)` (smooth surface through
  `[(y, rx, rz)]` elliptical rings), plus bone helpers `long_bone(p0, p1, radius, color, sides,
  bulge, cap)` (shaft + a bulged epiphysis ball at each end) and `tube_along(points, radius,
  color, sides)` (bent tube threaded through points — ribs/jaw/clavicles/pubis). Faces are
  `[(points, color), ...]`.
- **Matrix math**: `IDENTITY`, `mat_mul`, `mat_vec`, `axis_angle(axis, angle)` (Rodrigues).
- `Camera(angle, height, distance, target)` + `basis()` → `(pos, right, up, fwd)`; `angle` is the
  orbit azimuth in degrees, `height` the elevation above the target, `distance` in metres.
- `backdrop(size)` memoised vertical gradient; `floor_faces()` = one big quad;
  `shadow_poly()` = soft shadow footprint under the model.
- **Skeleton (forward kinematics)**: `Bone(name, parent, pivot, parts, tip, exposed)` in `SKELETON`;
  `BONE_ORDER` is parents-first. `build_skeleton()` returns the skeleton (pelvis root → torso →
  neck → head, and per side shoulder→elbow→wrist / hip→knee→ankle); each bone's `parts` is real
  skeletal geometry (skull w/ eye sockets + jaw, 9 rib pairs via `tube_along`, sternum,
  clavicles, scapulae, sacrum/iliac/ischium/pubis pelvis, long limb bones). Proportions are
  anthropometric (~1.72 m; hip pivot at the greater trochanter). `pose_mesh()` walks the
  chain: for a bone `M = Mp·R`, `t = Mp·(pivot − R·pivot) + tp` (rotation about the **rest**
  pivot, expressed in world-rest axes, then the parent transform — so a joint's own rotation
  leaves its pivot fixed but the parent carries it), writes each bone's `m_pos` (current joint)
  and `m_tip` (far end), and returns the transformed world faces. `HUMAN = pose_mesh()` is the
  rest mesh (~2856 faces). `reset_pose()` clears all rotations; `rotate_joint(name, axis, angle)`
  pre-multiplies a joint's rotation (`R = axis_angle · R`) — used by the tests.
- `make_projector(cam, rect)` → a function `world_point -> pixels` (or `None` behind the near
  clip); `project_point(cam, point, size)` wraps it for a `(w,h)` screen. `pick_joint(cam, pos,
  rect, radius=JOINT_RADIUS)` returns the nearest **exposed** joint whose `m_pos` projects within
  the radius (call `pose_mesh()` first so `m_pos` is current).
- `render_view(surface, rect, cam, faces=HUMAN)` draws backdrop → floor → `faces`
  (painter's algorithm) → shadow; `render_png(cam, size=(1000,1000), faces=HUMAN)` writes the
  PNG; `send_to_photoshop(cam, faces=HUMAN)` renders + runs the JSX: it sets
  `displayDialogs = NO`, closes any doc named `DOC_NAME`, opens the PNG, adds a fresh doc
  named `DOC_NAME`, duplicates the PNG layer in as `LAYER_NAME`, closes the source, and returns
  `illustration: <doc> | layer: <layer> WxH`. `photoshop_running()` imports
  `win32com`/`pythoncom`, `CoInitialize`s and `GetActiveObject`s the running Photoshop; returns
  `True`/`False`/`None` (pywin32 missing).
- **Posing (Viewer)**: `handle_viewport(event)` — left-click in `VIEWPORT` picks a joint
  (`pick_joint`) → `self.dragging`, capturing `drag_rot0`, `drag_pivot`/`drag_tip`, and the
  camera `drag_right`/`drag_up`; empty space → `self.orbiting` (drag changes `cam.angle`/`height`,
  syncing the sliders). `pose_drag(pos)`: `motion = dx·right − dy·up` (screen→world), `axis =
  cross(lever, motion)`, `angle = |d|·ROT_PER_PIXEL`, `dragging.rot = axis_angle(axis,angle) ·
  drag_rot0` (tip follows the cursor), then `self.faces = pose_mesh()`. Mouse-up releases.
  `draw_handles()` circles every exposed joint (highlighted when hovered/selected/dragging).
- Widgets are hand-rolled (`Slider`, `Button`, `Toggle`); `Viewer` owns them + `Camera`.
  Sliders: angle 0-360°, height 5-60°, distance 2-8 m. `font(size, bold)` caches a
  `pygame.font.SysFont("segoeui", ...)`.
- Keys: Left/Right nudge the focused slider, Up/Down change distance by 0.2 m, `R` reset pose,
  `A` toggle auto-sync, `S` send, `Esc` quit. Auto-sync re-sends 0.35 s after the last change.
- Layout rows: viewport 12..512; angle/height sliders left (x=150), distance slider right
  (x=600); **Reset pose button (150,618)**; toggle y=584; send/save buttons y=616; help y=660;
  status y=682. Keep the slider labels (drawn 20 px above each track) from overlapping.
- **Import/restore**: `ask_model_file()` (tkinter hidden root) → `model_import.load_model` +
  `fit_to_view`; result lands in `self.faces` with `self.custom=True` and `self.model_name`.
  While `custom`, `draw_handles()` returns early, `handle_viewport()` skips `pick_joint` (any
  viewport drag orbits), and `on_reset()` is a no-op. `on_use_skeleton()` resets the pose,
  restores `self.faces = pose_mesh()`, `custom=False`, target `(0,0.9,0)` + distance `4.2`.
  Import buttons: `import_btn (302,618,158,30)`, `skeleton_btn (466,618,130,30)`.
- Tests: `test_human_viewer.py` (53 checks, headless). The Photoshop case **closes the
  "New Illustration" document afterwards** with a JSX loop so repeat runs don't pile up docs.

## ball_game.py architecture (for future edits)
- Constants at the top; `PROJ_*` are volcanic-planet meteors, `BOLT_*` are the player's shots.
- `Ball` keeps its original name (it is now the ship): physics + `set_speed()` clamp only, no drawing.
- Rendering split: `draw_world()` composes the playfield into `self.world` (must `fill()` first),
  then `draw()` blits it with screen shake + HUD (level/speed/planets/score/lives/banner/footer).
- Order inside `update()`: drag → ball move/bounce + `ship_heading` → planet ram collisions →
  planet update → shooters → meteors → meteor-vs-ship → `update_bolts()` → level timer → timers.
- Damage funnels through `damage_planet()` (used by both bolts and rams). `collide_planets(count_hits=False)`
  is the "push the ship out but deal no damage" pass run right after spawning a level.
- `handle_events()` maps left click to **both** `dragging = True` and `fire(e.pos)`.
- Keyboard: `Space` reset, `N` next level, `R` randomize hull color, `Esc` quit, `Space`/`R` restart on game over.

## tree_gui.py architecture (for future edits)
- `DT` dict holds all params (defaults set at top of file).
- `WINDOW_NAME = "tree_generator_window"`; all widgets prefixed with it.
- `read_values()` queries all widgets into `DT` (called by Generate button).
- `build_gui()` destroys/recreates the window if it exists; call it at the end of the script (top-level `if window exists: deleteUI` then `build_gui()`).
- `generate_trees()` → `read_values()` → `delete_trees()` → seed random → `make_lambert` shared mats → build positions by layout → `create_tree(pos, tid)` per tree.
- `delete_trees()` removes `trunk_*`, `foliage_*`, `tree_*`, and per-tree mats.

## spiral_gui.py architecture (for future edits)
- `DT` = defaults dict, `W` = widget-name dict (both module level). `WINDOW_NAME = "spiral_generator_window"`, `GROUP = "spiral_cubes"`, `MAX_CUBES = 150`.
- Identity helpers: `cube_name(i)`/`mat_name(i)` → `spiral_cube_%03d` / `spiral_color_%03d`; `get_cubes()` sorts by `(index_of(name), name)`; `index_of()` parses the trailing number.
- `normalize()` (runs first in `build_gui`) renames every cube through `spiral_tmp_%04d` so legacy 2-digit names can't collide; `adopt()` then forceElement-assigns each cube its position material.
- `ensure_count(n)` delta-creates/deletes cubes and their lambert + SG (position-based index); `ensure_mat(i)` is idempotent lambert+SG creation.
- `update()` = read_values → enable cycles only in Gradient mode → one undo chunk → ensure_count → group strays → per-cube `xform(ws, t/ro/s)` + `setAttr(color)` → close chunk. Returns cube count.
- `color_at(i,n,p)`: Solid→A, Alternate→even A / odd B, Gradient→triangle wave over `(t*cycles) % 2` (smooth A→B→A, so odd cycles end on B).
- `build_gui()` seeds `seed = dict(DT)`, overlays `read_values()` of the old window if it exists and `len(get_cubes())`, deletes/recreates the window, wires every control to `update` via `dragCommand=changeCommand`, then `normalize(); adopt(); update()`.
- Buttons: `rebuild` = `delete_spiral` + `update`; `delete_spiral` removes cubes, `spiral_color_*` (mats + SGs), and the group.
- Test hook: `cmds._spiral_gui = {update, read, build, delete, rebuild, widgets, defaults}`.