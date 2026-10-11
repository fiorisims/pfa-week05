"""Bridge-side test for spiral_gui.py. Run: python maya_bridge.py test_spiral_gui.py

Mutates the live scene, then restores the GUI to its defaults in a finally block.
"""

import maya.cmds as cmds

G = cmds._spiral_gui
W = G["widgets"]
DT = G["defaults"]
failures = []


def check(label, got, want):
    ok = got == want
    if not ok:
        failures.append("%s: got %r want %r" % (label, got, want))
    print("%-38s %s  %r" % (label, "ok" if ok else "FAIL", got))


def setv(key, val):
    """Edit a widget by probing edit flags; objectType() lies about these controls."""
    name = W[key]
    for fn, kw in ((cmds.intSliderGrp, {"value": val}),
                   (cmds.floatSliderGrp, {"value": val}),
                   (cmds.colorSliderGrp, {"rgb": val}),
                   (cmds.optionMenu, {"value": val})):
        try:
            fn(name, e=True, **kw)
            return
        except Exception:
            continue
    raise RuntimeError("cannot set %s (%s)" % (key, name))


def snapshot():
    return G["read"]()


def restore(snap):
    for key, val in snap.items():
        setv(key, val)
    G["update"]()


def cubes():
    return cmds.ls("spiral_cube_*", type="transform") or []


def col(i):
    return tuple(round(v, 3) for v in cmds.getAttr("spiral_color_%03d.color" % i)[0])


def pos(i):
    return tuple(round(v, 2) for v in cmds.xform(
        "spiral_cube_%03d" % i, q=True, ws=True, t=True))


before = snapshot()
try:
    print("--- load / adopt ---")
    check("window exists", cmds.window("spiral_generator_window", q=True, exists=True), True)
    check("window visible", cmds.window("spiral_generator_window", q=True, visible=True), True)
    check("scene matches count slider", len(cubes()), before["count"])
    check("all names canonical", all(len(c.rsplit("_", 1)[-1]) == 3 for c in cubes()), True)
    check("first name", sorted(cubes())[0], "spiral_cube_000")
    check("material count", len(cmds.ls("spiral_color_*", type="lambert")), len(cubes()))
    check("group exists", cmds.objExists("spiral_cubes"), True)
    check("group children", len(cmds.listRelatives("spiral_cubes", children=True) or []),
          len(cubes()))

    print("--- count up / down ---")
    setv("count", 70)
    G["update"]()
    check("count 70", len(cubes()), 70)
    check("mats follow count", len(cmds.ls("spiral_color_*", type="lambert")), 70)
    check("group follows count",
          len(cmds.listRelatives("spiral_cubes", children=True) or []), 70)
    setv("count", 20)
    G["update"]()
    check("count 20", len(cubes()), 20)
    check("mats trimmed", len(cmds.ls("spiral_color_*", type="lambert")), 20)
    setv("count", 48)
    G["update"]()
    check("count back to 48", len(cubes()), 48)
    check("mats back to 48", len(cmds.ls("spiral_color_*", type="lambert")), 48)

    print("--- gradient mode ---")
    setv("mode", "Gradient")
    setv("cycles", 3)
    setv("colorA", (0.0, 1.0, 0.0))
    setv("colorB", (1.0, 0.0, 0.0))
    setv("radius0", 1.0)
    setv("radius1", 10.0)
    setv("turns", 4.0)
    setv("height", 25.0)
    setv("size", 2.0)
    G["update"]()
    n = len(cubes())

    def expected(i):
        t = i / float(n - 1) if n > 1 else 0.0
        x = (t * 3) % 2.0                       # cycles = 3
        u = x if x <= 1.0 else 2.0 - x
        return (round(u, 3), round(1.0 - u, 3), 0.0)   # A = green, B = red

    check("first colour = A", col(0), (0.0, 1.0, 0.0))
    check("last colour = B (3rd ramp)", col(n - 1), expected(n - 1))
    check("mid colour interpolates",
          all(abs(col(n // 2)[k] - expected(n // 2)[k]) < 0.002 for k in range(3)), True)
    check("mid is neither A nor B", col(n // 2) not in ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
          True)
    check("pos 0 (r0, 0, 0)", pos(0), (1.0, 0.0, 0.0))
    check("pos last (r1, h, 0)", pos(n - 1), (10.0, 25.0, 0.0))
    check("scale", tuple(cmds.xform("spiral_cube_000", q=True, s=True)), (2.0, 2.0, 2.0))

    print("--- alternate + solid ---")
    setv("mode", "Alternate")
    setv("colorA", (0.2, 0.4, 0.6))
    setv("colorB", (0.9, 0.1, 0.3))
    G["update"]()
    check("alt even = A", col(0), (0.2, 0.4, 0.6))
    check("alt odd = B", col(1), (0.9, 0.1, 0.3))
    setv("mode", "Solid")
    setv("colorA", (0.3, 0.6, 0.9))
    G["update"]()
    check("solid 5", col(5), (0.3, 0.6, 0.9))
    check("solid 17", col(17), (0.3, 0.6, 0.9))

    print("--- cycles control enabled only in Gradient ---")
    setv("mode", "Alternate")
    G["update"]()
    off = cmds.control(W["cycles"], q=True, enable=True)
    setv("mode", "Gradient")
    G["update"]()
    on = cmds.control(W["cycles"], q=True, enable=True)
    check("cycles off in Alternate", off, False)
    check("cycles on in Gradient", on, True)

    print("--- undo = one Ctrl+Z per drag ---")
    setv("count", 33)
    G["update"]()
    check("count 33", len(cubes()), 33)
    cmds.undo()
    check("undo restores 48", len(cubes()), 48)

    print("--- rebuild / delete ---")
    G["build"]()
    check("rebuild keeps 48", len(cubes()), 48)
    check("window still up", cmds.window("spiral_generator_window", q=True, exists=True), True)

finally:
    print("--- restore pre-test settings ---")
    restore(before)
    print("restored: %d cubes, mode=%s, count slider=%d"
          % (len(cubes()), G["read"]()["mode"], G["read"]()["count"]))

if failures:
    raise AssertionError("%d failures: %s" % (len(failures), failures))
__result__ = "all checks passed"
