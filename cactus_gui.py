import maya.cmds as cmds
import random
import math

cmds.undoInfo(openChunk=True, chunkName="cactus_script")

WINDOW_NAME = "cactus_generator_window"
BODY_MAT = "cactus_body_mat"
SPIKE_MAT = "cactus_spike_mat"

DT = {}
DT["num_cacti"] = 5
DT["style"] = "saguaro"
DT["height_min"] = 3.0
DT["height_max"] = 5.0
DT["radius_min"] = 0.35
DT["radius_max"] = 0.6
DT["ribs"] = 10
DT["rib_depth"] = 0.35
DT["areole_step"] = 0.6
DT["spike_len_min"] = 0.08
DT["spike_len_max"] = 0.30
DT["spike_radius"] = 0.02
DT["spike_central"] = 2.0
DT["spike_radials"] = 5
DT["spike_spread"] = 30.0
DT["arms_min"] = 0
DT["arms_max"] = 3
DT["arm_reach"] = 0.7
DT["arm_height"] = 1.4
DT["seed"] = 42
DT["layout"] = "grid"
DT["grid_size"] = 4.0
DT["scatter_r"] = 5.0
DT["grid_cols"] = 2
DT["body_color"] = (0.25, 0.62, 0.3)
DT["spike_color"] = (0.95, 0.9, 0.75)
DT["vary_colors"] = False


def norm(v):
    l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if l < 1e-9:
        return (0.0, 1.0, 0.0)
    return (v[0] / l, v[1] / l, v[2] / l)


def delete_cacti():
    for node in cmds.ls("cactus_*"):
        if cmds.objExists(node):
            cmds.delete(node)
    for node in cmds.ls("cactus_body_mat_*") + cmds.ls("cactus_spike_mat_*"):
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


def make_ribbed_column(radius, height, ribs, depth, name):
    axis = max(8, ribs * 6)
    cyl = cmds.polyCylinder(name=name, r=radius, h=height,
                            subdivisionsAxis=axis, subdivisionsHeight=8,
                            subdivisionsCaps=1, ch=False)[0]
    for v in cmds.ls(f"{cyl}.vtx[*]", flatten=True):
        p = cmds.xform(v, q=True, ws=True, t=True)
        d = math.hypot(p[0], p[2])
        if d < radius * 0.98:
            continue
        th = math.atan2(p[2], p[0])
        rr = radius * (1.0 + depth * math.cos(ribs * th))
        cmds.xform(v, ws=True, t=(rr * math.cos(th), p[1], rr * math.sin(th)))
    cmds.select(clear=True)
    return cyl


def make_ribbed_crown(radius, ribs, depth, name):
    dome = cmds.polySphere(name=name, r=1.0,
                           subdivisionsX=max(24, ribs * 6),
                           subdivisionsY=6, ch=False)[0]
    verts = cmds.ls(f"{dome}.vtx[*]", flatten=True)
    bottom = [v for v in verts
              if cmds.xform(v, q=True, ws=True, t=True)[1] < -0.001]
    faces = cmds.polyListComponentConversion(bottom, toFace=True) or []
    if faces:
        cmds.delete(faces)
    cmds.select(clear=True)
    for v in cmds.ls(f"{dome}.vtx[*]", flatten=True):
        p = cmds.xform(v, q=True, ws=True, t=True)
        if p[1] < -0.001:
            continue
        th = math.atan2(p[2], p[0])
        fade = max(0.25, 1.0 - 0.8 * p[1])
        rr = 1.0 + depth * math.cos(ribs * th) * fade
        cmds.xform(v, ws=True, t=(rr * math.cos(th), p[1], rr * math.sin(th)))
    cmds.xform(dome, s=(radius, radius, radius), r=True)
    cmds.select(clear=True)
    return dome


def orient_cone(cone, d):
    dn = norm(d)
    a = (-dn[1], dn[0], 0.0)
    la = math.hypot(a[0], a[1])
    if la < 1e-6:
        a = (1.0, 0.0, 0.0)
    else:
        a = (a[0] / la, a[1] / la, a[2] / la)
    b = (dn[1] * a[2] - dn[2] * a[1],
         dn[2] * a[0] - dn[0] * a[2],
         dn[0] * a[1] - dn[1] * a[0])
    mat = [a[0], a[1], a[2], 0.0,
           dn[0], dn[1], dn[2], 0.0,
           b[0], b[1], b[2], 0.0,
           0.0, 0.0, 0.0, 1.0]
    cmds.xform(cone, ws=True, m=mat)
    return dn


def make_spine(pos, d, length, radius, name):
    cone = cmds.polyCone(name=name, r=radius, h=length,
                         subdivisionsAxis=6, ch=False)[0]
    dn = orient_cone(cone, d)
    cmds.xform(cone, ws=True,
               t=(pos[0] + dn[0] * length * 0.5,
                  pos[1] + dn[1] * length * 0.5,
                  pos[2] + dn[2] * length * 0.5))
    return cone


def place_areole(pos, rad_dir, tid, mat, idx, scale=1.0):
    slen = random.uniform(DT["spike_len_min"], DT["spike_len_max"]) * scale
    h = math.hypot(rad_dir[0], rad_dir[2])
    if h < 1e-6:
        d0 = (1.0, 0.0, 0.0)
    else:
        d0 = (rad_dir[0] / h, 0.0, rad_dir[2] / h)
    spikes = []
    c = make_spine(pos, d0, slen * DT["spike_central"], DT["spike_radius"],
                   f"cactus_spike_{tid}_{idx}")
    apply_material(c, mat)
    spikes.append(c)
    idx += 1
    for s in range(DT["spike_radials"]):
        az = math.radians(random.uniform(-DT["spike_spread"], DT["spike_spread"]))
        nx = d0[0] * math.cos(az) + d0[2] * math.sin(az)
        nz = -d0[0] * math.sin(az) + d0[2] * math.cos(az)
        sl = slen * random.uniform(0.5, 0.8)
        sp = make_spine(pos, norm((nx, 0.0, nz)), sl, DT["spike_radius"] * 0.8,
                        f"cactus_spike_{tid}_{idx}")
        apply_material(sp, mat)
        spikes.append(sp)
        idx += 1
    return idx, spikes


def add_column_areoles(body_h, body_r, ribs, depth, px, pz, tid, mat, idx):
    crest = body_r * (1.0 + depth)
    h = 0.4
    spikes = []
    while h <= body_h - 0.35:
        for k in range(ribs):
            th = 2.0 * math.pi * k / ribs + math.radians(random.uniform(-4, 4))
            rr = crest * random.uniform(0.97, 1.0)
            ax = px + rr * math.cos(th)
            az = pz + rr * math.sin(th)
            d = (math.cos(th), 0.0, math.sin(th))
            idx, sp = place_areole((ax, h, az), d, tid, mat, idx)
            spikes += sp
        h += DT["areole_step"]
    return idx, spikes


def ring_basis(axis):
    a = norm(axis)
    if abs(a[1]) < 0.9:
        u = norm((-a[2], 0.0, a[0]))
    else:
        u = (1.0, 0.0, 0.0)
    v = norm((a[1] * u[2] - a[2] * u[1],
              a[2] * u[0] - a[0] * u[2],
              a[0] * u[1] - a[1] * u[0]))
    return u, v


def add_ring_areoles(axis_pt, axis, count, radius, tid, mat, idx):
    u, v = ring_basis(axis)
    spikes = []
    for k in range(count):
        th = 2.0 * math.pi * k / count
        rd = (u[0] * math.cos(th) + v[0] * math.sin(th),
              u[1] * math.cos(th) + v[1] * math.sin(th),
              u[2] * math.cos(th) + v[2] * math.sin(th))
        px = axis_pt[0] + rd[0] * radius
        py = axis_pt[1] + rd[1] * radius
        pz = axis_pt[2] + rd[2] * radius
        idx, sp = place_areole((px, py, pz), rd, tid, mat, idx)
        spikes += sp
    return idx, spikes


def add_arm(px, pz, tid, ai, body_mat, spike_mat, body_r, body_h, idx):
    ang = random.uniform(0.0, 2.0 * math.pi)
    dx, dz = math.cos(ang), math.sin(ang)
    crest = body_r * (1.0 + DT["rib_depth"])
    h_att = random.uniform(0.4 * body_h, 0.6 * body_h)
    arm_r = body_r * 0.45
    reach = DT["arm_reach"]
    arm_h = DT["arm_height"]
    aribs = max(4, DT["ribs"] // 2)
    adepth = DT["rib_depth"] * 0.8

    ho = make_ribbed_column(arm_r, reach, aribs, adepth,
                            f"cactus_arm_{tid}_{ai}_h")
    orient_cone(ho, (dx, 0, dz))
    cmds.xform(ho, ws=True,
               t=(px + dx * (crest + reach * 0.5), h_att, pz + dz * (crest + reach * 0.5)))
    apply_material(ho, body_mat)

    bx = px + dx * (crest + reach)
    bz = pz + dz * (crest + reach)
    elb = cmds.polySphere(name=f"cactus_arm_{tid}_{ai}_e", r=arm_r * 1.15,
                          subdivisionsAxis=8, subdivisionsHeight=6, ch=False)[0]
    cmds.xform(elb, ws=True, t=(bx, h_att, bz))
    apply_material(elb, body_mat)

    vo = make_ribbed_column(arm_r, arm_h, aribs, adepth,
                            f"cactus_arm_{tid}_{ai}_v")
    cmds.xform(vo, ws=True, t=(bx, h_att + arm_h * 0.5, bz))
    apply_material(vo, body_mat)

    tip = cmds.polySphere(name=f"cactus_arm_{tid}_{ai}_t", r=arm_r * 1.15,
                          subdivisionsAxis=8, subdivisionsHeight=6, ch=False)[0]
    cmds.xform(tip, ws=True, t=(bx, h_att + arm_h, bz))
    apply_material(tip, body_mat)

    parts = [ho, elb, vo, tip]
    crest_arm = arm_r * (1.0 + adepth)
    nring = max(3, DT["spike_radials"])

    s = 0.5
    while s <= reach - 0.3:
        idx, sp = add_ring_areoles((px + dx * (crest + s), h_att, pz + dz * (crest + s)),
                                   (dx, 0, dz), nring, crest_arm, tid, spike_mat, idx)
        parts += sp
        s += DT["areole_step"]

    s = 0.5
    while s <= arm_h - 0.3:
        idx, sp = add_ring_areoles((bx, h_att + s, bz), (0, 1, 0),
                                   nring, crest_arm, tid, spike_mat, idx)
        parts += sp
        s += DT["areole_step"]

    return idx, parts


def create_saguaro(pos, tid, body_mat, spike_mat):
    px, pz = pos[0], pos[2]
    body_h = random.uniform(DT["height_min"], DT["height_max"])
    body_r = random.uniform(DT["radius_min"], DT["radius_max"])
    ribs = DT["ribs"]
    depth = DT["rib_depth"]

    body = make_ribbed_column(body_r, body_h, ribs, depth, f"cactus_body_{tid}")
    cmds.xform(body, ws=True, t=(px, body_h / 2.0, pz))
    apply_material(body, body_mat)
    parts = [body]

    crown = make_ribbed_crown(body_r, ribs, depth, f"cactus_crown_{tid}")
    cmds.xform(crown, ws=True, t=(px, body_h, pz))
    apply_material(crown, body_mat)
    parts.append(crown)

    idx, sp = add_column_areoles(body_h, body_r, ribs, depth, px, pz, tid, spike_mat, 0)
    parts += sp

    for ai in range(random.randint(DT["arms_min"], DT["arms_max"])):
        idx, ap = add_arm(px, pz, tid, ai, body_mat, spike_mat, body_r, body_h, idx)
        parts += ap

    return parts


def create_barrel(pos, tid, body_mat, spike_mat):
    px, pz = pos[0], pos[2]
    body_h = random.uniform(DT["height_min"], DT["height_max"])
    body_r = random.uniform(DT["radius_min"], DT["radius_max"])
    ribs = DT["ribs"]
    depth = DT["rib_depth"]

    body = make_ribbed_column(body_r, body_h, ribs, depth, f"cactus_body_{tid}")
    cmds.xform(body, ws=True, t=(px, body_h / 2.0, pz))
    apply_material(body, body_mat)
    parts = [body]

    crown = make_ribbed_crown(body_r, ribs, depth, f"cactus_crown_{tid}")
    cmds.xform(crown, s=(1.0, 1.0, 0.55), r=True)
    cmds.xform(crown, ws=True, t=(px, body_h, pz))
    apply_material(crown, body_mat)
    parts.append(crown)

    idx, sp = add_column_areoles(body_h, body_r, ribs, depth, px, pz, tid, spike_mat, 0)
    parts += sp

    return parts


def make_pad(center, rr, name):
    pad = cmds.polySphere(name=name, r=1.0,
                          subdivisionsX=10, subdivisionsY=8, ch=False)[0]
    cmds.xform(pad, s=(rr, rr * 0.35, rr))
    cmds.rotate(0, random.uniform(0, 180), random.uniform(-18, 18),
                pad, r=True, p=(0, 0, 0))
    cmds.xform(pad, ws=True, t=center)
    return pad


def create_prickly(pos, tid, body_mat, spike_mat):
    parts = []
    pads = []
    idx = 0
    r0 = random.uniform(0.55, 0.8)
    first = make_pad((pos[0], r0 * 0.2, pos[2]), r0, f"cactus_pad_{tid}_0")
    apply_material(first, body_mat)
    parts.append(first)
    pads.append(first)
    level = [(first, r0, (pos[0], r0 * 0.2, pos[2]))]
    cnt = 1

    for L in range(3):
        nxt = []
        for parent, pr, ctr in level:
            for cl in range(random.randint(0, 1)):
                if cnt >= 7:
                    break
                az = random.uniform(0.0, 2.0 * math.pi)
                cr = pr * 0.7
                cx = ctr[0] + math.cos(az) * pr * 0.55
                cy = ctr[1] + pr * 0.35
                cz = ctr[2] + math.sin(az) * pr * 0.55
                pad = make_pad((cx, cy, cz), cr, f"cactus_pad_{tid}_{cnt}")
                apply_material(pad, body_mat)
                parts.append(pad)
                pads.append(pad)
                nxt.append((pad, cr, (cx, cy, cz)))
                cnt += 1
        level = nxt
        if not level:
            break

    for pad in pads:
        verts = cmds.ls(f"{pad}.vtx[*]", flatten=True)
        step = max(1, len(verts) // 20)
        pivot = cmds.xform(pad, q=True, ws=True, rp=True)
        for k in range(1, len(verts), step):
            w = cmds.xform(verts[k], q=True, ws=True, t=True)
            hx = w[0] - pivot[0]
            hz = w[2] - pivot[2]
            hl = math.hypot(hx, hz)
            if hl < 1e-6:
                d = norm((random.uniform(-1, 1), 0.0, random.uniform(-1, 1)))
            else:
                d = (hx / hl, 0.0, hz / hl)
            idx, sp = place_areole(tuple(w), d, tid, spike_mat, idx, scale=0.5)
            parts += sp

    return parts


def create_cactus(pos, tid):
    bc = list(DT["body_color"])
    sc = list(DT["spike_color"])
    if DT["vary_colors"]:
        bc = [max(0, min(1, c + random.uniform(-0.12, 0.12))) for c in bc]
        sc = [max(0, min(1, c + random.uniform(-0.12, 0.12))) for c in sc]
    if DT["vary_colors"]:
        bm = make_lambert(f"cactus_body_mat_{tid}", bc)
        sm = make_lambert(f"cactus_spike_mat_{tid}", sc)
    else:
        bm, sm = BODY_MAT, SPIKE_MAT

    if DT["style"] == "barrel":
        parts = create_barrel(pos, tid, bm, sm)
    elif DT["style"] == "prickly":
        parts = create_prickly(pos, tid, bm, sm)
    else:
        parts = create_saguaro(pos, tid, bm, sm)

    cmds.select(parts)
    cmds.group(name=f"cactus_{tid}")
    cmds.select(clear=True)


def generate_cacti(*args):
    read_values()
    cmds.undoInfo(openChunk=True, chunkName="cactus_generate")
    try:
        delete_cacti()
        random.seed(DT["seed"])

        make_lambert(BODY_MAT, DT["body_color"])
        make_lambert(SPIKE_MAT, DT["spike_color"])

        n = DT["num_cacti"]
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
            create_cactus(p, i + 1)

        print(f"Generated {n} cacti ({DT['style']})")
    finally:
        cmds.undoInfo(closeChunk=True)


def read_values():
    DT["num_cacti"] = cmds.intSliderGrp(f"{WINDOW_NAME}_num", q=True, value=True)
    sel = cmds.radioButtonGrp(f"{WINDOW_NAME}_style", q=True, select=True)
    DT["style"] = {1: "saguaro", 2: "barrel", 3: "prickly"}[sel]
    DT["height_min"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_h_min", q=True, value=True)
    DT["height_max"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_h_max", q=True, value=True)
    DT["radius_min"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_r_min", q=True, value=True)
    DT["radius_max"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_r_max", q=True, value=True)
    DT["ribs"] = cmds.intSliderGrp(f"{WINDOW_NAME}_ribs", q=True, value=True)
    DT["rib_depth"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_rdepth", q=True, value=True)
    DT["areole_step"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_astep", q=True, value=True)
    DT["spike_len_min"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_sl_min", q=True, value=True)
    DT["spike_len_max"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_sl_max", q=True, value=True)
    DT["spike_radius"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_srad", q=True, value=True)
    DT["spike_central"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_scent", q=True, value=True)
    DT["spike_radials"] = cmds.intSliderGrp(f"{WINDOW_NAME}_sradn", q=True, value=True)
    DT["spike_spread"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_sspread", q=True, value=True)
    DT["arms_min"] = cmds.intSliderGrp(f"{WINDOW_NAME}_arms_min", q=True, value=True)
    DT["arms_max"] = cmds.intSliderGrp(f"{WINDOW_NAME}_arms_max", q=True, value=True)
    DT["arm_reach"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_reach", q=True, value=True)
    DT["arm_height"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_arm_h", q=True, value=True)
    DT["seed"] = cmds.intFieldGrp(f"{WINDOW_NAME}_seed", q=True, value1=True)
    sel = cmds.radioButtonGrp(f"{WINDOW_NAME}_layout", q=True, select=True)
    DT["layout"] = {1: "grid", 2: "line", 3: "random"}[sel]
    DT["grid_cols"] = cmds.intSliderGrp(f"{WINDOW_NAME}_cols", q=True, value=True)
    DT["grid_size"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_gsize", q=True, value=True)
    DT["scatter_r"] = cmds.floatSliderGrp(f"{WINDOW_NAME}_sr", q=True, value=True)
    DT["body_color"] = cmds.colorSliderGrp(f"{WINDOW_NAME}_body_col", q=True, rgb=True)
    DT["spike_color"] = cmds.colorSliderGrp(f"{WINDOW_NAME}_spike_col", q=True, rgb=True)
    DT["vary_colors"] = cmds.checkBox(f"{WINDOW_NAME}_vary", q=True, value=True)


def build_gui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    win = cmds.window(WINDOW_NAME, title="Cactus Generator",
                      widthHeight=(430, 700), sizeable=True)

    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

    cmds.text(label="STYLE", align="center", font="boldLabelFont")
    cmds.radioButtonGrp(f"{WINDOW_NAME}_style", label="Style:",
                        numberOfRadioButtons=3,
                        labelArray3=["Saguaro", "Barrel", "Prickly Pear"],
                        columnWidth3=[70, 90, 90],
                        select={"saguaro": 1, "barrel": 2, "prickly": 3}[DT["style"]])

    cmds.separator(height=10)
    cmds.text(label="CACTUS BODY", align="center", font="boldLabelFont")
    cmds.intSliderGrp(f"{WINDOW_NAME}_num", label="Number of Cacti",
                      minValue=1, maxValue=16, value=DT["num_cacti"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_h_min", label="Height Min",
                        minValue=0.5, maxValue=9.0, precision=2, value=DT["height_min"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_h_max", label="Height Max",
                        minValue=0.5, maxValue=9.0, precision=2, value=DT["height_max"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_r_min", label="Radius Min",
                        minValue=0.1, maxValue=1.5, precision=2, value=DT["radius_min"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_r_max", label="Radius Max",
                        minValue=0.1, maxValue=1.5, precision=2, value=DT["radius_max"])
    cmds.intSliderGrp(f"{WINDOW_NAME}_ribs", label="Rib Count",
                      minValue=4, maxValue=24, value=DT["ribs"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_rdepth", label="Rib Depth (0=round, 1=deep)",
                        minValue=0.0, maxValue=0.8, precision=2, value=DT["rib_depth"])

    cmds.separator(height=10)
    cmds.text(label="SPIKES", align="center", font="boldLabelFont")
    cmds.floatSliderGrp(f"{WINDOW_NAME}_astep", label="Areole Spacing (rows)",
                        minValue=0.15, maxValue=2.0, precision=2, value=DT["areole_step"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_sl_min", label="Spike Length Min",
                        minValue=0.02, maxValue=1.0, precision=2, value=DT["spike_len_min"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_sl_max", label="Spike Length Max",
                        minValue=0.02, maxValue=1.0, precision=2, value=DT["spike_len_max"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_srad", label="Spike Radius",
                        minValue=0.005, maxValue=0.15, precision=3, value=DT["spike_radius"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_scent", label="Central Spine Scale",
                        minValue=1.0, maxValue=4.0, precision=2, value=DT["spike_central"])
    cmds.intSliderGrp(f"{WINDOW_NAME}_sradn", label="Radial Spines per Areole",
                      minValue=2, maxValue=12, value=DT["spike_radials"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_sspread", label="Radial Spread (deg)",
                        minValue=5.0, maxValue=75.0, precision=1, value=DT["spike_spread"])

    cmds.separator(height=10)
    cmds.text(label="ARMS (Saguaro)", align="center", font="boldLabelFont")
    cmds.intSliderGrp(f"{WINDOW_NAME}_arms_min", label="Arms Min",
                      minValue=0, maxValue=4, value=DT["arms_min"])
    cmds.intSliderGrp(f"{WINDOW_NAME}_arms_max", label="Arms Max",
                      minValue=0, maxValue=4, value=DT["arms_max"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_reach", label="Arm Reach",
                        minValue=0.2, maxValue=3.0, precision=2, value=DT["arm_reach"])
    cmds.floatSliderGrp(f"{WINDOW_NAME}_arm_h", label="Arm Height",
                        minValue=0.5, maxValue=5.0, precision=2, value=DT["arm_height"])

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
    cmds.floatSliderGrp(f"{WINDOW_NAME}_sr", label="Scatter Radius",
                        minValue=1.0, maxValue=15.0, precision=1, value=DT["scatter_r"])

    cmds.separator(height=10)
    cmds.text(label="COLORS", align="center", font="boldLabelFont")
    cmds.colorSliderGrp(f"{WINDOW_NAME}_body_col", label="Body Color",
                        rgb=DT["body_color"])
    cmds.colorSliderGrp(f"{WINDOW_NAME}_spike_col", label="Spike Color",
                        rgb=DT["spike_color"])
    cmds.checkBox(f"{WINDOW_NAME}_vary", label="Vary Colors Per Cactus",
                  value=DT["vary_colors"])

    cmds.separator(height=10)
    cmds.text(label="RANDOM", align="center", font="boldLabelFont")
    cmds.intFieldGrp(f"{WINDOW_NAME}_seed", label="Seed", value1=DT["seed"])

    cmds.separator(height=10)
    cmds.rowLayout(numberOfColumns=3, columnAlign3=["left", "center", "right"])
    cmds.button(label="Generate", command=generate_cacti, width=100)
    cmds.button(label="Delete Cacti", command=lambda *a: delete_cacti(), width=100)
    cmds.button(label="Close", command=lambda *a: cmds.deleteUI(WINDOW_NAME), width=100)
    cmds.setParent("..")

    cmds.showWindow(win)


if cmds.window(WINDOW_NAME, exists=True):
    cmds.deleteUI(WINDOW_NAME)
build_gui()

cmds.undoInfo(closeChunk=True)