import maya.cmds as cmds
import random
import math

WINDOW_NAME = "tree_generator_window"
TRUNK_MAT = "tree_trunk_mat"
FOLIAGE_MAT = "tree_foliage_mat"

DT = {}
DT["num_trees"] = 4
DT["trunk_h_min"] = 2.5
DT["trunk_h_max"] = 3.5
DT["trunk_r_min"] = 0.15
DT["trunk_r_max"] = 0.25
DT["foliage_layers_min"] = 2
DT["foliage_layers_max"] = 3
DT["foliage_r_min"] = 0.8
DT["foliage_r_max"] = 1.2
DT["foliage_h"] = 1.0
DT["seed"] = 42
DT["layout"] = "grid"
DT["grid_size"] = 4.0
DT["scatter_r"] = 5.0
DT["grid_cols"] = 2
DT["trunk_color"] = (0.45, 0.25, 0.1)
DT["foliage_color"] = (0.1, 0.6, 0.15)
DT["vary_colors"] = False


def delete_trees():
    for node in cmds.ls("trunk_*") + cmds.ls("foliage_*") + cmds.ls("tree_*"):
        if cmds.objExists(node):
            cmds.delete(node)
    for node in cmds.ls("tree_trunk_mat_*") + cmds.ls("tree_foliage_mat_*"):
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


def create_tree(pos, tid):
    trunk_h = random.uniform(DT["trunk_h_min"], DT["trunk_h_max"])
    trunk_r = random.uniform(DT["trunk_r_min"], DT["trunk_r_max"])
    layers = random.randint(DT["foliage_layers_min"], DT["foliage_layers_max"])
    base_r = random.uniform(DT["foliage_r_min"], DT["foliage_r_max"])
    fh = DT["foliage_h"]

    tc = list(DT["trunk_color"])
    fc = list(DT["foliage_color"])
    if DT["vary_colors"]:
        for c in (tc, fc):
            c[0] = max(0, min(1, c[0] + random.uniform(-0.12, 0.12)))
            c[1] = max(0, min(1, c[1] + random.uniform(-0.12, 0.12)))
            c[2] = max(0, min(1, c[2] + random.uniform(-0.12, 0.12)))

    if DT["vary_colors"]:
        trunk_mat = make_lambert(f"tree_trunk_mat_{tid}", tc)
    else:
        trunk_mat = TRUNK_MAT

    trunk = cmds.polyCylinder(name=f"trunk_{tid}", r=trunk_r, h=trunk_h,
                              subdivisionsAxis=12, ch=False)[0]
    cmds.xform(trunk, ws=True, t=[pos[0], trunk_h / 2, pos[2]])
    apply_material(trunk, trunk_mat)

    parts = [trunk]
    for i in range(layers):
        layer_y = trunk_h + i * 0.45
        layer_r = base_r * (1.0 - i * 0.22)
        fo = cmds.polyCone(name=f"foliage_{tid}_{i}", r=layer_r, h=fh,
                           subdivisionsAxis=12, ch=False)[0]
        cmds.xform(fo, ws=True, t=[pos[0], layer_y + fh / 2, pos[2]])
        if DT["vary_colors"]:
            foliage_mat = make_lambert(f"tree_foliage_mat_{tid}", fc)
        else:
            foliage_mat = FOLIAGE_MAT
        apply_material(fo, foliage_mat)
        parts.append(fo)

    cmds.select(parts)
    cmds.group(name=f"tree_{tid}")
    cmds.select(clear=True)


def generate_trees(*args):
    read_values()
    delete_trees()
    random.seed(DT["seed"])

    make_lambert(TRUNK_MAT, DT["trunk_color"])
    make_lambert(FOLIAGE_MAT, DT["foliage_color"])

    n = DT["num_trees"]
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
            r = random.uniform(0, DT["scatter_r"])
            positions.append((r * math.cos(ang), 0, r * math.sin(ang)))

    for i, p in enumerate(positions):
        create_tree(p, i + 1)

    print(f"Generated {n} trees")


def read_values():
    DT["num_trees"] = cmds.intSliderGrp(f"{WINDOW_NAME}_num", q=True, value=True)
    DT["trunk_h_min"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_th_min", q=True, value=True)
    DT["trunk_h_max"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_th_max", q=True, value=True)
    DT["trunk_r_min"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_tr_min", q=True, value=True)
    DT["trunk_r_max"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_tr_max", q=True, value=True)
    DT["foliage_layers_min"] = cmds.intSliderGrp(f"{WINDOW_NAME}_fl_min", q=True, value=True)
    DT["foliage_layers_max"] = cmds.intSliderGrp(f"{WINDOW_NAME}_fl_max", q=True, value=True)
    DT["foliage_r_min"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_fr_min", q=True, value=True)
    DT["foliage_r_max"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_fr_max", q=True, value=True)
    DT["foliage_h"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_fh", q=True, value=True)
    DT["seed"] = cmds.intFieldGrp(f"{WINDOW_NAME}_seed", q=True, value1=True)
    DT["grid_cols"] = cmds.intSliderGrp(f"{WINDOW_NAME}_cols", q=True, value=True)
    DT["grid_size"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_gsize", q=True, value=True)
    DT["scatter_r"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_srad", q=True, value=True)
    DT["layout"] = cmds.radioButtonGrp(f"{WINDOW_NAME}_layout", q=True, select=True)
    DT["trunk_color"] = cmds.colorSliderGrp(f"{WINDOW_NAME}_trunk_col", q=True, rgb=True)
    DT["foliage_color"] = cmds.colorSliderGrp(f"{WINDOW_NAME}_foliage_col", q=True, rgb=True)
    DT["vary_colors"] = cmds.checkBox(f"{WINDOW_NAME}_vary", q=True, value=True)


def build_gui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    win = cmds.window(WINDOW_NAME, title="Tree Generator", widthHeight=(360, 460),
                      sizeable=True)

    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

    # ---- Counts ----
    cmds.text(label="TRUNK", align="center", font="boldLabelFont")
    cmds.intSliderGrp(f"{WINDOW_NAME}_num", label="Number of Trees",
                      minValue=1, maxValue=16, value=DT["num_trees"])

    cmds.separator(height=10)
    cmds.text(label="TRUNK", align="center", font="boldLabelFont")
    cmds.floatSliderGrp(f"{WINDOW_NAME}_th_min", label="Height Min",
                        minValue=0.5, maxValue=6.0, precision=2, value=DT["trunk_h_min"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_th_max", label="Height Max",
                        minValue=0.5, maxValue=6.0, precision=2, value=DT["trunk_h_max"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_tr_min", label="Radius Min",
                        minValue=0.02, maxValue=0.6, precision=2, value=DT["trunk_r_min"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_tr_max", label="Radius Max",
                        minValue=0.02, maxValue=0.6, precision=2, value=DT["trunk_r_max"])

    cmds.separator(height=10)
    cmds.text(label="FOLIAGE", align="center", font="boldLabelFont")
    cmds.intSliderGrp(f"{WINDOW_NAME}_fl_min", label="Layers Min",
                      minValue=1, maxValue=6, value=DT["foliage_layers_min"])
    cmds.intSliderGrp(f"{WINDOW_NAME}_fl_max", label="Layers Max",
                      minValue=1, maxValue=6, value=DT["foliage_layers_max"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_fr_min", label="Base Radius Min",
                        minValue=0.2, maxValue=3.0, precision=2, value=DT["foliage_r_min"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_fr_max", label="Base Radius Max",
                        minValue=0.2, maxValue=3.0, precision=2, value=DT["foliage_r_max"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_fh", label="Cone Height",
                        minValue=0.2, maxValue=3.0, precision=2, value=DT["foliage_h"])

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
    cmds.colorSliderGrp(f"{WINDOW_NAME}_trunk_col", label="Trunk Color",
                        rgb=DT["trunk_color"])
    cmds.colorSliderGrp(f"{WINDOW_NAME}_foliage_col", label="Foliage Color",
                        rgb=DT["foliage_color"])
    cmds.checkBox(f"{WINDOW_NAME}_vary", label="Vary Colors Per Tree",
                  value=DT["vary_colors"])

    cmds.separator(height=10)
    cmds.text(label="RANDOM & OPTIONS", align="center", font="boldLabelFont")
    cmds.intFieldGrp(f"{WINDOW_NAME}_seed", label="Seed", value1=DT["seed"])

    cmds.separator(height=10)
    cmds.rowLayout(numberOfColumns=3, columnAlign3=["left", "center", "right"])
    cmds.button(label="Generate", command=generate_trees, width=100)
    cmds.button(label="Delete Trees", command=lambda *a: delete_trees(), width=100)
    cmds.button(label="Close", command=lambda *a: cmds.deleteUI(WINDOW_NAME), width=100)
    cmds.setParent("..")

    cmds.showWindow(win)


if cmds.window(WINDOW_NAME, exists=True):
    cmds.deleteUI(WINDOW_NAME)
build_gui()