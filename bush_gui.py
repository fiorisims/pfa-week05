import maya.cmds as cmds
import random
import math

WINDOW_NAME = "bush_generator_window"
LEAF_MAT = "bush_leaf_mat"
BERRY_MAT = "bush_berry_mat"

DT = {}
DT["num_bushes"] = 4
DT["density"] = 16
DT["foliage_shape"] = 0.5
DT["bush_r_min"] = 0.8
DT["bush_r_max"] = 1.2
DT["bush_h"] = 1.0
DT["berry_size"] = 0.06
DT["berry_count"] = 20
DT["seed"] = 42
DT["layout"] = "grid"
DT["grid_size"] = 4.0
DT["scatter_r"] = 5.0
DT["grid_cols"] = 2
DT["leaf_color"] = (0.12, 0.5, 0.12)
DT["berry_color"] = (0.75, 0.1, 0.1)
DT["vary_colors"] = False


def delete_bushes():
    for node in cmds.ls("bush_*") + cmds.ls("leaf_*") + cmds.ls("berry_*"):
        if cmds.objExists(node):
            cmds.delete(node)
    for node in cmds.ls("bush_leaf_mat_*") + cmds.ls("bush_berry_mat_*"):
        if cmds.objExists(node):
            cmds.delete(node)


def make_lambert(name, rgb):
    if cmds.objExists(name):
        cmds.delete(name)
    mat = cmds.shadingNode("lambert", asShader=True, name=name)
    cmds.setAttr(f"{mat}.color", rgb[0], rgb[1], rgb[2], type="double3")
    return mat


def apply_material(obj, mat):
    cmds.select(obj)
    cmds.hyperShade(assign=mat)
    cmds.select(clear=True)


def create_bush(pos, bid):
    r = random.uniform(DT["bush_r_min"], DT["bush_r_max"])
    h = DT["bush_h"]
    density = DT["density"]
    shape = DT["foliage_shape"]

    lc = list(DT["leaf_color"])
    bc = list(DT["berry_color"])
    if DT["vary_colors"]:
        for c in (lc, bc):
            c[0] = max(0, min(1, c[0] + random.uniform(-0.12, 0.12)))
            c[1] = max(0, min(1, c[1] + random.uniform(-0.12, 0.12)))
            c[2] = max(0, min(1, c[2] + random.uniform(-0.12, 0.12)))

    if DT["vary_colors"]:
        leaf_mat = make_lambert(f"bush_leaf_mat_{bid}", lc)
        berry_mat = make_lambert(f"bush_berry_mat_{bid}", bc)
    else:
        leaf_mat = LEAF_MAT
        berry_mat = BERRY_MAT

    parts = []

    for i in range(density):
        az = random.uniform(0, 2 * math.pi)
        dist = random.uniform(r * 0.15, r * (0.55 + shape * 0.5))
        blob_y = random.uniform(h * 0.1, h * (0.6 + shape * 0.45))
        blob_r = random.uniform(r * 0.3, r * (0.38 + shape * 0.12))
        leaf = cmds.polySphere(name=f"leaf_{bid}_{i}",
                               radius=blob_r,
                               subdivisionsX=20,
                               subdivisionsY=14,
                               ch=False)[0]
        cmds.xform(leaf, ws=True,
                   t=[pos[0] + dist * math.cos(az), blob_y, pos[2] + dist * math.sin(az)])
        cmds.scale(1, 1.0 - shape * 0.35, 1, leaf, relative=True)
        apply_material(leaf, leaf_mat)
        parts.append(leaf)

    for i in range(DT["berry_count"]):
        az = random.uniform(0, 2 * math.pi)
        el = random.uniform(0.15, h / r * 0.85)
        surf_r = r * (1.0 - el * 0.35)
        berry = cmds.polySphere(name=f"berry_{bid}_{i}",
                                radius=DT["berry_size"],
                                subdivisionsX=10,
                                subdivisionsY=8,
                                ch=False)[0]
        cmds.xform(berry, ws=True,
                   t=[pos[0] + surf_r * math.cos(az),
                      el * h,
                      pos[2] + surf_r * math.sin(az)])
        apply_material(berry, berry_mat)
        parts.append(berry)

    cmds.select(parts)
    cmds.group(name=f"bush_{bid}")
    cmds.select(clear=True)


def generate_bushes(*args):
    read_values()
    delete_bushes()
    random.seed(DT["seed"])

    make_lambert(LEAF_MAT, DT["leaf_color"])
    make_lambert(BERRY_MAT, DT["berry_color"])

    n = DT["num_bushes"]
    positions = []

    if DT["layout"] == "grid":
        cols = DT["grid_cols"]
        rows = (n + cols - 1) // cols
        for i in range(n):
            cx = (i % cols) - (cols - 1) / 2.0
            cy = (i // cols) - (rows - 1) / 2.0
            positions.append((cx * DT["grid_size"] * 0.5, 0, cy * DT["grid_size"] * 0.5))
    elif DT["layout"] == "line":
        for i in range(n):
            x = (i - (n - 1) / 2.0) * 2.0
            positions.append((x, 0, 0))
    else:
        for i in range(n):
            ang = random.uniform(0, 2 * math.pi)
            rd = random.uniform(0, DT["scatter_r"])
            positions.append((rd * math.cos(ang), 0, rd * math.sin(ang)))

    for i, p in enumerate(positions):
        create_bush(p, i + 1)

    print(f"Generated {n} bushes")


def read_values():
    DT["num_bushes"] = cmds.intSliderGrp(f"{WINDOW_NAME}_num", q=True, value=True)
    DT["density"] = cmds.intSliderGrp(f"{WINDOW_NAME}_density", q=True, value=True)
    DT["foliage_shape"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_fshape", q=True, value=True)
    DT["bush_r_min"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_br_min", q=True, value=True)
    DT["bush_r_max"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_br_max", q=True, value=True)
    DT["bush_h"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_bh", q=True, value=True)
    DT["berry_size"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_bsize", q=True, value=True)
    DT["berry_count"] = cmds.intSliderGrp(f"{WINDOW_NAME}_bcount", q=True, value=True)
    DT["seed"] = cmds.intFieldGrp(f"{WINDOW_NAME}_seed", q=True, value1=True)
    DT["grid_cols"] = cmds.intSliderGrp(f"{WINDOW_NAME}_cols", q=True, value=True)
    DT["grid_size"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_gsize", q=True, value=True)
    DT["scatter_r"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_srad", q=True, value=True)
    DT["layout"] = cmds.radioButtonGrp(f"{WINDOW_NAME}_layout", q=True, select=True)
    DT["leaf_color"] = cmds.colorSliderGrp(f"{WINDOW_NAME}_leaf_col", q=True, rgb=True)
    DT["berry_color"] = cmds.colorSliderGrp(f"{WINDOW_NAME}_berry_col", q=True, rgb=True)
    DT["vary_colors"] = cmds.checkBox(f"{WINDOW_NAME}_vary", q=True, value=True)


def build_gui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    win = cmds.window(WINDOW_NAME, title="Bush & Berry Generator",
                      widthHeight=(360, 470), sizeable=True)

    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

    cmds.text(label="COUNT & FOLIAGE", align="center", font="boldLabelFont")
    cmds.intSliderGrp(f"{WINDOW_NAME}_num", label="Number of Bushes",
                      minValue=1, maxValue=16, value=DT["num_bushes"])
    cmds.intSliderGrp(f"{WINDOW_NAME}_density", label="Foliage Density",
                      minValue=6, maxValue=40, value=DT["density"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_fshape", label="Foliage Shape",
                        minValue=0.0, maxValue=1.0, precision=2, value=DT["foliage_shape"])

    cmds.separator(height=10)
    cmds.text(label="BUSH SHAPE", align="center", font="boldLabelFont")
    cmds.floatSliderGrp(f"{WINDOW_NAME}_br_min", label="Radius Min",
                        minValue=0.3, maxValue=3.0, precision=2, value=DT["bush_r_min"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_br_max", label="Radius Max",
                        minValue=0.3, maxValue=3.0, precision=2, value=DT["bush_r_max"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_bh", label="Bush Height",
                        minValue=0.3, maxValue=3.0, precision=2, value=DT["bush_h"])

    cmds.separator(height=10)
    cmds.text(label="BERRIES", align="center", font="boldLabelFont")
    cmds.floatSliderGrp(f"{WINDOW_NAME}_bsize", label="Berry Size",
                        minValue=0.02, maxValue=0.25, precision=2, value=DT["berry_size"])
    cmds.intSliderGrp(f"{WINDOW_NAME}_bcount", label="Berry Count",
                      minValue=1, maxValue=60, value=DT["berry_count"])

    cmds.separator(height=10)
    cmds.text(label="PLACEMENT", align="center", font="boldLabelFont")
    cmds.radioButtonGrp(f"{WINDOW_NAME}_layout", label="Layout:",
                        numberOfRadioButtons=3,
                        labelArray3=["Grid", "Line", "Random"],
                        columnWidth3=[70, 70, 70],
                        select={"grid": 1, "line": 2, "random": 3}[DT["layout"]])
    cmds.intSliderGrp(f"{WINDOW_NAME}_cols", label="Grid Columns",
                      minValue=1, maxValue=8, value=DT["grid_cols"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_gsize", label="Grid Spacing",
                        minValue=1.0, maxValue=12.0, precision=1, value=DT["grid_size"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_srad", label="Scatter Radius",
                        minValue=1.0, maxValue=15.0, precision=1, value=DT["scatter_r"])

    cmds.separator(height=10)
    cmds.text(label="COLORS", align="center", font="boldLabelFont")
    cmds.colorSliderGrp(f"{WINDOW_NAME}_leaf_col", label="Leaf Color",
                        rgb=DT["leaf_color"])
    cmds.colorSliderGrp(f"{WINDOW_NAME}_berry_col", label="Berry Color",
                        rgb=DT["berry_color"])
    cmds.checkBox(f"{WINDOW_NAME}_vary", label="Vary Colors Per Bush",
                  value=DT["vary_colors"])

    cmds.separator(height=10)
    cmds.text(label="RANDOM & OPTIONS", align="center", font="boldLabelFont")
    cmds.intFieldGrp(f"{WINDOW_NAME}_seed", label="Seed", value1=DT["seed"])

    cmds.separator(height=10)
    cmds.rowLayout(numberOfColumns=3, columnAlign3=["left", "center", "right"])
    cmds.button(label="Generate", command=generate_bushes, width=100)
    cmds.button(label="Delete Bushes", command=lambda *a: delete_bushes(), width=100)
    cmds.button(label="Close", command=lambda *a: cmds.deleteUI(WINDOW_NAME), width=100)
    cmds.setParent("..")

    cmds.showWindow(win)


if cmds.window(WINDOW_NAME, exists=True):
    cmds.deleteUI(WINDOW_NAME)
build_gui()