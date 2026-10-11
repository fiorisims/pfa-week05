"""Spiral of alternating blue and pink cubes - run inside Maya via maya_bridge.py.

    python maya_bridge.py create_spiral.py

Builds a 4-turn helix (48 cubes, shrinking as it rises), grouped as `spiral_cubes`
and wrapped in a single undo chunk, so one Ctrl+Z removes the whole thing.
Re-running replaces the previous spiral. Press 5 for shaded view to see the colours.
"""

import math

import maya.cmds as cmds

GROUP = "spiral_cubes"
N = 48
TURNS = 4
RADIUS0, RADIUS1 = 3.0, 14.0
HEIGHT = 40.0
CUBE = 1.6
BLUE = (0.10, 0.35, 0.95)
PINK = (0.98, 0.35, 0.65)


def make_mat(name, rgb):
    """Lambert material plus its shading group (sets needs the SG, not the material)."""
    if not cmds.objExists(name):
        cmds.shadingNode("lambert", asShader=True, name=name)
        cmds.setAttr(name + ".color", rgb[0], rgb[1], rgb[2], type="double3")
    sg = name + "SG"
    if not cmds.objExists(sg):
        cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=sg)
        cmds.connectAttr(name + ".outColor", sg + ".surfaceShader", force=True)
    return sg


if cmds.objExists(GROUP):
    cmds.delete(GROUP)
for stray in cmds.ls("spiral_cube_*", type="transform") or []:
    if cmds.objExists(stray):
        cmds.delete(stray)

blue_sg = make_mat("spiral_blue_mat", BLUE)
pink_sg = make_mat("spiral_pink_mat", PINK)

cmds.undoInfo(openChunk=True, chunkName="spiral_cubes")
cubes = []
try:
    for i in range(N):
        t = i / float(N - 1)
        angle = t * TURNS * math.tau
        radius = RADIUS0 + (RADIUS1 - RADIUS0) * t
        x = math.cos(angle) * radius
        z = math.sin(angle) * radius
        y = t * HEIGHT
        size = CUBE * (1.0 - 0.45 * t)

        cube = cmds.polyCube(name="spiral_cube_%02d" % i,
                             width=size, height=size, depth=size)[0]
        cmds.xform(cube, ws=True, t=(x, y, z))
        cmds.xform(cube, os=True, ro=(0, math.degrees(angle), 0))
        cmds.sets(cube, e=True, forceElement=blue_sg if i % 2 == 0 else pink_sg)
        cubes.append(cube)

    group = cmds.group(cubes, name=GROUP)
finally:
    cmds.undoInfo(closeChunk=True)

try:
    cmds.viewFit(all=True)
except Exception:
    pass

print("created %s with %d cubes" % (group, len(cubes)))
__result__ = {"group": group, "count": len(cubes)}
