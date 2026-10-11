import maya.cmds as cmds

cmds.file(new=True, force=True)

# --- Table Top ---
table = cmds.polyCube(w=2.74, h=0.05, d=1.525, name="pingPongTable")[0]
cmds.setAttr(table + ".translateY", 0.76)
cmds.setAttr(table + ".receiveShadows", 1)
cmds.setAttr(table + ".overrideEnabled", 1)
cmds.setAttr(table + ".overrideRGBColors", 1)
cmds.setAttr(table + ".overrideColorRGB", 0.05, 0.2, 0.6)
cmds.select(table)
cmds.hyperShade(assign="blinn1")
cmds.setAttr("blinn1.color", 0.05, 0.2, 0.6)
cmds.setAttr("blinn1.specularColor", 0.3, 0.3, 0.3)

# --- Legs ---
leg_positions = [
    (1.27, 0, 0.6625),
    (-1.27, 0, 0.6625),
    (1.27, 0, -0.6625),
    (-1.27, 0, -0.6625),
]

for i, (x, _, z) in enumerate(leg_positions):
    leg = cmds.polyCylinder(r=0.04, h=0.76, name=f"leg_{i}")[0]
    cmds.setAttr(leg + ".translateX", x)
    cmds.setAttr(leg + ".translateY", 0.38)
    cmds.setAttr(leg + ".translateZ", z)
    cmds.setAttr(leg + ".overrideEnabled", 1)
    cmds.setAttr(leg + ".overrideRGBColors", 1)
    cmds.setAttr(leg + ".overrideColorRGB", 0.2, 0.2, 0.2)
    cmds.select(leg)
    cmds.hyperShade(assign="blinn2")
    cmds.setAttr("blinn2.color", 0.2, 0.2, 0.2)

# --- Net ---
net = cmds.polyCube(w=0.01, h=0.15, d=1.525, name="net")[0]
cmds.setAttr(net + ".translateY", 0.835)
cmds.setAttr(net + ".overrideEnabled", 1)
cmds.setAttr(net + ".overrideRGBColors", 1)
cmds.setAttr(net + ".overrideColorRGB", 0.1, 0.7, 0.1)
cmds.select(net)
cmds.hyperShade(assign="blinn3")
cmds.setAttr("blinn3.color", 0.1, 0.7, 0.1)
cmds.setAttr("blinn3.transparency", 0.3, 0.3, 0.3)

# --- Net Posts ---
for x in [0.7625, -0.7625]:
    post = cmds.polyCylinder(r=0.015, h=0.15, name="netPost")[0]
    cmds.setAttr(post + ".translateX", x)
    cmds.setAttr(post + ".translateY", 0.835)
    cmds.setAttr(post + ".overrideEnabled", 1)
    cmds.setAttr(post + ".overrideRGBColors", 1)
    cmds.setAttr(post + ".overrideColorRGB", 0.2, 0.2, 0.2)
    cmds.select(post)
    cmds.hyperShade(assign="blinn2")

# --- White Lines on Table ---
# Center line
line1 = cmds.polyCube(w=2.74, h=0.052, d=0.01, name="centerLine")[0]
cmds.setAttr(line1 + ".translateY", 0.76)
cmds.select(line1)
cmds.hyperShade(assign="blinn4")
cmds.setAttr("blinn4.color", 1, 1, 1)

# Side lines
for z in [0.7625, -0.7625]:
    line = cmds.polyCube(w=2.74, h=0.052, d=0.01, name="sideLine")[0]
    cmds.setAttr(line + ".translateY", 0.76)
    cmds.setAttr(line + ".translateZ", z)
    cmds.select(line)
    cmds.hyperShade(assign="blinn4")

# Short edge lines
for x in [1.37, -1.37]:
    line = cmds.polyCube(w=0.01, h=0.052, d=1.525, name="edgeLine")[0]
    cmds.setAttr(line + ".translateY", 0.76)
    cmds.setAttr(line + ".translateX", x)
    cmds.select(line)
    cmds.hyperShade(assign="blinn4")

print("Ping pong table created!")
