import maya.cmds as cmds
import random

def create_tree(pos, tree_id):
    trunk_h = random.uniform(2.5, 3.5)
    trunk_r = random.uniform(0.15, 0.25)
    foliage_layers = random.randint(2, 3)
    base_foliage_r = random.uniform(0.8, 1.2)

    trunk = cmds.polyCylinder(
        name=f"trunk_{tree_id}",
        r=trunk_r,
        h=trunk_h,
        subdivisionsAxis=12,
        ch=False
    )[0]
    cmds.xform(trunk, ws=True, t=[pos[0], trunk_h / 2, pos[2]])
    cmds.setAttr(f"trunk_{tree_id}.overrideEnabled", 1)
    cmds.setAttr(f"trunk_{tree_id}.overrideColor", 6)  # brown

    parts = [trunk]

    for i in range(foliage_layers):
        layer_y = trunk_h + i * 0.5
        layer_r = base_foliage_r * (1.0 - i * 0.25)
        layer_h = 1.0

        foliage = cmds.polyCone(
            name=f"foliage_{tree_id}_{i}",
            r=layer_r,
            h=layer_h,
            subdivisionsAxis=12,
            ch=False
        )[0]
        cmds.xform(foliage, ws=True, t=[pos[0], layer_y + layer_h / 2, pos[2]])
        cmds.setAttr(f"{foliage}.overrideEnabled", 1)
        cmds.setAttr(f"{foliage}.overrideColor", 8)  # green
        parts.append(foliage)

    cmds.select(clear=True)
    cmds.select(parts)
    cmds.group(name=f"tree_{tree_id}")
    cmds.select(clear=True)
    print(f"Tree {tree_id} created at ({pos[0]:.1f}, {pos[2]:.1f})")

def create_trees():
    positions = [
        (-3, 0, -3),
        ( 3, 0, -3),
        (-3, 0,  3),
        ( 3, 0,  3),
    ]
    random.seed(42)
    for i, pos in enumerate(positions):
        create_tree(pos, i + 1)
    print("All 4 trees created!")

create_trees()
