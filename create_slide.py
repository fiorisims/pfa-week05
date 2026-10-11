import maya.cmds as cmds
import math

def create_playground_slide():
    # Slide parameters
    slide_height = 5.0
    slide_length = 8.0
    slide_width = 1.2
    rail_height = 0.3
    rail_thickness = 0.05
    platform_size = 2.0
    platform_thickness = 0.2
    num_steps = 6
    step_width = 0.8
    step_depth = 0.25
    step_height_offset = slide_height / num_steps
    post_radius = 0.1
    num_curve_points = 20

    slide_parts = []

    # --- Slide Surface (curved) ---
    slide_curve_pts = []
    for i in range(num_curve_points + 1):
        t = float(i) / num_curve_points
        x = t * slide_length
        # Steep start, flattening out at the bottom
        y = slide_height * (1.0 - t ** 0.7)
        z = 0
        slide_curve_pts.append((x, y, z))

    # Build slide surface with a plane and deform its vertices along a curve
    slide_surf = cmds.polyPlane(
        name="slide_surface",
        width=slide_length,
        height=slide_width,
        subdivisionsX=1,
        subdivisionsY=num_curve_points,
        axis=[0, 0, 1],
        ch=False
    )[0]

    slide_verts = cmds.polyEvaluate(slide_surf, vertex=True, v=True)
    for i in range(slide_verts[0]):
        for j in range(slide_verts[1]):
            vtx_index = i * slide_verts[1] + j
            vtx_name = f"{slide_surf}.vtx[{vtx_index}]"
            u = float(j) / (slide_verts[1] - 1) if slide_verts[1] > 1 else 0
            y_pos = slide_height * (1.0 - u ** 0.7)
            cmds.xform(vtx_name, ws=True, t=[u * slide_length, y_pos, (float(i) / (slide_verts[0] - 1) - 0.5) * slide_width])

    cmds.polyBevel3(slide_surf, offset=0.01, ch=False)
    cmds.select(clear=True)
    slide_parts.append(slide_surf)

    # --- Rails ---
    for side in [-1, 1]:
        rail_z = side * (slide_width / 2 + rail_thickness)

        rail_pts = []
        for i in range(num_curve_points + 1):
            t = float(i) / num_curve_points
            x = t * slide_length
            y = slide_height * (1.0 - t ** 0.7) + rail_height
            z = rail_z
            rail_pts.append((x, y, z))

        rail_cv = cmds.curve(
            name=f"rail_curve_{'L' if side < 0 else 'R'}",
            degree=3,
            point=rail_pts
        )

        # Sweep a circle profile along the rail curve to form the rail tube
        profile_cv = cmds.circle(
            name=f"rail_profile_{'L' if side < 0 else 'R'}",
            radius=rail_thickness,
            normal=[0, 1, 0],
            constructionHistory=False
        )[0]

        rail_surf = cmds.extrude(
            profile_cv,
            rail_cv,
            name=f"rail_{'L' if side < 0 else 'R'}",
            et=2,  # Tube
            upx=1, ch=False
        )[0]

        cmds.select(clear=True)
        slide_parts.append(rail_surf)

    # --- Platform ---
    platform = cmds.polyCube(
        name="platform",
        width=platform_size,
        height=platform_thickness,
        depth=slide_width + 0.4,
        ch=False
    )[0]
    cmds.xform(platform, ws=True, t=[-platform_size / 4, slide_height - platform_thickness / 2, 0])
    slide_parts.append(platform)

    # Platform edge rail
    for side_x in [-1, 1]:
        edge_rail = cmds.polyCube(
            name=f"platform_rail_{'L' if side_x < 0 else 'R'}",
            width=platform_size,
            height=rail_height,
            depth=rail_thickness,
            ch=False
        )[0]
        cmds.xform(edge_rail, ws=True, t=[-platform_size / 4, slide_height + rail_height / 2, side_x * (slide_width / 2 + 0.2 + rail_thickness / 2)])
        slide_parts.append(edge_rail)

    # --- Steps (ladder) ---
    ladder_offset_x = -platform_size / 2
    ladder_z = slide_width / 2 + 1.0
    ladder_depth = 1.0

    # Side posts
    for side_z in [-1, 1]:
        post = cmds.polyCylinder(
            name=f"ladder_post_{'L' if side_z < 0 else 'R'}",
            r=post_radius,
            h=slide_height,
            ch=False
        )[0]
        cmds.xform(post, ws=True, t=[ladder_offset_x, slide_height / 2, ladder_z + side_z * step_width / 2])
        slide_parts.append(post)

    # Steps
    for i in range(num_steps):
        step_y = step_height_offset * (i + 0.5)
        step = cmds.polyCube(
            name=f"step_{i}",
            width=step_width,
            height=step_depth,
            depth=step_depth,
            ch=False
        )[0]
        cmds.xform(step, ws=True, t=[ladder_offset_x, step_y, ladder_z])
        slide_parts.append(step)

    # --- Support Posts ---
    post_positions = [
        (slide_length * 0.15, 0),
        (slide_length * 0.4, 0),
        (slide_length * 0.65, 0),
        (slide_length * 0.9, 0),
    ]
    for idx, (px, pz) in enumerate(post_positions):
        t_ratio = px / slide_length
        post_h = slide_height * (1.0 - t_ratio ** 0.7) / 2.0

        post = cmds.polyCylinder(
            name=f"support_post_{idx}",
            r=post_radius,
            h=post_h,
            ch=False
        )[0]
        cmds.xform(post, ws=True, t=[px, post_h / 2, pz])
        slide_parts.append(post)

    cmds.select(clear=True)
    cmds.select(slide_parts)

    print("Playground slide created!")

create_playground_slide()
