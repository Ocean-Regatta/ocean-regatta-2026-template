#!/usr/bin/env python3
"""
Realistic Procedural Seafloor Generator for Gazebo Sim (Jetty / Harmonic).
Generates high-fidelity 3D bathymetry models (OBJ + MTL + PNG textures) and SDF 1.9 files.

Features:
  - Covers the full 1000m x 1000m evaluation world area (-500m to +500m in X and Y).
  - Realistic multi-zone seabed materials:
      * Fine golden marine sand with subaqueous current ripples
      * Coarse gravel and shell hash transition substrate
      * Weathered dark oceanic basalt/granite rock with marine algae patina
  - Procedural 3D rock formations and boulders:
      * Breakwater riprap toe protection armor around the harbor mole foundation
      * Natural craggy reef formations on elevated underwater knolls
      * Solitary glacial erratics and boulders scattered across the continental shelf
  - Bathymetry tailored to the evaluation world:
      * Depth averages -16.2m, matching the harbor wall foundation exactly
      * Seamless smoothstep leveling beneath the harbor wall (no gaps or clipping)
      * Submerged depths between -11m and -21m (safe clearance below all surface vessels)
  - Visual-only: strictly NO collision geometry generated for maximum simulation performance.
"""

import os
import sys
import math
import zlib
import struct
import random
import argparse


def write_png(filename, width, height, rgb_data):
    """Writes an uncompressed 24-bit RGB PNG file using pure standard library."""
    def chunk(chunk_type, data):
        return struct.pack('>I', len(data)) + chunk_type + data + struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    raw_lines = bytearray()
    row_bytes = width * 3
    for y in range(height):
        raw_lines.append(0)  # Filter type 0 (None)
        start = y * row_bytes
        raw_lines.extend(rgb_data[start : start + row_bytes])
    idat = chunk(b'IDAT', zlib.compress(bytes(raw_lines), 6))
    iend = chunk(b'IEND', b'')
    with open(filename, 'wb') as f:
        f.write(header + ihdr + idat + iend)


def clamp(val, low=0, high=255):
    """Clamps a numeric value into the valid byte range [low, high]."""
    return max(low, min(high, int(val)))


def generate_textures(tex_dir, size=512, seed=42):
    """
    Generates photorealistic seamlessly-tileable textures:
      1. sand_ripples.png: Golden marine sand with subaqueous current ripples & shell flecks.
      2. rock_marine.png: Weathered marine rock with Voronoi fractures, algae & barnacle specks.
      3. gravel_sand_mix.png: Mixed coarse sand with distinct 3D-shaded pebbles and stones.
    """
    os.makedirs(tex_dir, exist_ok=True)
    random.seed(seed)
    w = h = size

    # Precompute sine/cosine lookup tables for toroidal seamless wrapping
    lut_sin = [math.sin(2.0 * math.pi * i / float(w)) for i in range(w)]
    lut_cos = [math.cos(2.0 * math.pi * i / float(w)) for i in range(w)]

    print(f"  -> Generating seamlessly tileable sand texture ({w}x{h})...")
    sand_buf = bytearray(w * h * 3)
    for y in range(h):
        row_start = y * w * 3
        for x in range(w):
            # Directional current ripple harmonics (toroidally periodic)
            u1 = (8 * x + 4 * y) % w
            u2 = (16 * x + 8 * y) % w
            u3 = (2 * x - 4 * y) % w
            w_main = lut_sin[u1] * 0.68 + lut_sin[u2] * 0.22 + lut_sin[u3] * 0.14

            # Subtle secondary cross-ripples
            u4 = (3 * x - 1 * y) % w
            w_cross = lut_cos[u4] * 0.12

            # Sand grain noise & mineral speckles
            grain = random.randint(-7, 7)
            speckle = 0
            rnd_val = random.random()
            if rnd_val < 0.015:
                speckle = 32   # bright shell fragment
            elif rnd_val > 0.985:
                speckle = -28  # dark heavy mineral grain

            total_wave = w_main + w_cross

            # Marine sand base color: warm golden-beige (212, 188, 142)
            r = clamp(212 + total_wave * 26 + grain + speckle)
            g = clamp(188 + total_wave * 22 + grain + speckle * 0.8)
            b = clamp(142 + total_wave * 15 + grain + speckle * 0.6)

            idx = row_start + x * 3
            sand_buf[idx] = r
            sand_buf[idx+1] = g
            sand_buf[idx+2] = b
    write_png(os.path.join(tex_dir, "sand_ripples.png"), w, h, sand_buf)

    print(f"  -> Generating marine rock texture ({w}x{h})...")
    # Cellular Voronoi fracture pattern with spatial grid optimization
    num_seeds = 36
    seeds = [(random.randint(0, w - 1), random.randint(0, h - 1)) for _ in range(num_seeds)]
    grid_n = 8
    cell_w = w // grid_n
    cell_h = h // grid_n
    grid = [[[] for _ in range(grid_n)] for _ in range(grid_n)]
    for sx, sy in seeds:
        gx = min(grid_n - 1, sx // cell_w)
        gy = min(grid_n - 1, sy // cell_h)
        grid[gy][gx].append((sx, sy))

    rock_buf = bytearray(w * h * 3)
    for y in range(h):
        row_start = y * w * 3
        gy0 = y // cell_h
        algae_y = lut_sin[(2 * y) % w] + lut_cos[(3 * y) % w] * 0.5
        for x in range(w):
            gx0 = x // cell_w
            d1 = 1e9
            d2 = 1e9
            for dgy in (-1, 0, 1):
                gy = (gy0 + dgy) % grid_n
                for dgx in (-1, 0, 1):
                    gx = (gx0 + dgx) % grid_n
                    for sx, sy in grid[gy][gx]:
                        dx = abs(x - sx)
                        if dx > w // 2: dx = w - dx
                        dy = abs(y - sy)
                        if dy > h // 2: dy = h - dy
                        d = dx * dx + dy * dy
                        if d < d1:
                            d2 = d1
                            d1 = d
                        elif d < d2:
                            d2 = d
            crack_dist = math.sqrt(d2) - math.sqrt(d1) if d2 < 1e8 else 10.0
            is_crack = 1.0 - min(1.0, crack_dist / 4.2)

            # Organic marine algae/biofilm patches
            algae_x = lut_sin[(3 * x) % w] + lut_cos[(1 * x) % w] * 0.5
            algae = max(0.0, (algae_x + algae_y) * 0.5)

            # Oceanic dark basalt/granite base: (88, 85, 82)
            noise = random.randint(-9, 9)
            base_r = 88 + noise
            base_g = 85 + noise
            base_b = 82 + noise

            # Olive/green algae shift
            base_r = int(base_r * (1.0 - algae * 0.32))
            base_g = int(base_g * (1.0 + algae * 0.28))
            base_b = int(base_b * (1.0 - algae * 0.22))

            # Fissure / crack shading
            r = clamp(base_r * (1.0 - is_crack * 0.65))
            g = clamp(base_g * (1.0 - is_crack * 0.65))
            b = clamp(base_b * (1.0 - is_crack * 0.65))

            # Calcareous barnacle specks
            if random.random() < 0.01:
                r, g, b = 175, 180, 172

            idx = row_start + x * 3
            rock_buf[idx] = r
            rock_buf[idx+1] = g
            rock_buf[idx+2] = b
    write_png(os.path.join(tex_dir, "rock_marine.png"), w, h, rock_buf)

    print(f"  -> Generating gravel & shell mix texture ({w}x{h})...")
    gravel_buf = bytearray(w * h * 3)
    # Base sand matrix
    for y in range(h):
        row_start = y * w * 3
        sy = lut_sin[(4 * y) % w]
        for x in range(w):
            sx = lut_sin[(4 * x) % w]
            grain = random.randint(-10, 10)
            r = clamp(190 + (sx + sy) * 8 + grain)
            g = clamp(168 + (sx + sy) * 7 + grain)
            b = clamp(126 + (sx + sy) * 5 + grain)
            idx = row_start + x * 3
            gravel_buf[idx] = r
            gravel_buf[idx+1] = g
            gravel_buf[idx+2] = b

    # Scattered 3D shaded pebbles
    pebble_palette = [
        (110, 108, 105),  # slate grey
        (148, 142, 132),  # granite
        (78, 74, 70),     # dark basalt
        (165, 135, 110),  # sandstone
        (178, 178, 172),  # quartz
        (132, 98, 82),    # ironstone
    ]
    for _ in range(130):
        px = random.randint(0, w - 1)
        py = random.randint(0, h - 1)
        rx = random.randint(5, 13)
        ry = random.randint(4, 11)
        angle = random.uniform(0, math.pi)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        p_color = random.choice(pebble_palette)
        max_r = max(rx, ry) + 3

        for dy in range(-max_r, max_r + 1):
            for dx in range(-max_r, max_r + 1):
                lx = dx * cos_a + dy * sin_a
                ly = -dx * sin_a + dy * cos_a
                dist_sq = (lx / rx)**2 + (ly / ry)**2
                if dist_sq <= 1.0:
                    norm_z = math.sqrt(max(0.0, 1.0 - dist_sq))
                    norm_x = (lx / rx) * cos_a - (ly / ry) * sin_a
                    norm_y = (lx / rx) * sin_a + (ly / ry) * cos_a
                    light = (-norm_x * 0.5 - norm_y * 0.5 + norm_z * 0.7)
                    shade = max(0.5, min(1.4, 0.9 + light * 0.42))

                    tx = (px + dx) % w
                    ty = (py + dy) % h
                    idx = (ty * w + tx) * 3
                    pr = clamp(p_color[0] * shade + random.randint(-5, 5))
                    pg = clamp(p_color[1] * shade + random.randint(-5, 5))
                    pb = clamp(p_color[2] * shade + random.randint(-5, 5))
                    gravel_buf[idx] = pr
                    gravel_buf[idx+1] = pg
                    gravel_buf[idx+2] = pb
                elif dist_sq <= 1.35 and (dx > 0 or dy > 0):
                    # Drop shadow
                    tx = (px + dx) % w
                    ty = (py + dy) % h
                    idx = (ty * w + tx) * 3
                    gravel_buf[idx] = clamp(gravel_buf[idx] * 0.75)
                    gravel_buf[idx+1] = clamp(gravel_buf[idx+1] * 0.75)
                    gravel_buf[idx+2] = clamp(gravel_buf[idx+2] * 0.75)

    write_png(os.path.join(tex_dir, "gravel_sand_mix.png"), w, h, gravel_buf)
    print("  -> Textures generated successfully.")


def compute_bathymetry(x, y, base_depth=16.2):
    """
    Computes natural seabed elevation Z at coordinate (x, y).
    Features:
      - Regional shelf slope (deeper offshore towards West, shallower towards coastal East).
      - Multi-harmonic sand dunes and bathymetric wave topography.
      - Underwater ridges and mounds where reefs/rock formations occur.
      - Harbor mole leveling: smoothly locks depth to exactly -16.2m under the breakwater wall.
    """
    # 1. Regional gentle shelf slope
    # x in [-500, 500], y in [-500, 500]
    z_reg = -base_depth + 0.0035 * (x - 60.0) - 0.0020 * y

    # 2. Multi-harmonic sand waves & dunes
    z_waves = (
        1.35 * math.sin(2.0 * math.pi * (x * 0.0042 + y * 0.0025)) +
        0.95 * math.cos(2.0 * math.pi * (-x * 0.0028 + y * 0.0055)) +
        0.55 * math.sin(2.0 * math.pi * (x * 0.0105 + y * 0.0078))
    )

    # 3. Localized underwater knolls & ridges
    knolls = [
        # (cx, cy, amp, rx, ry)
        (-150.0, 130.0, 3.4, 80.0, 130.0),   # Northwest reef ridge
        (180.0, -170.0, 2.7, 95.0, 95.0),    # Southeast shoal
        (50.0, 260.0, 3.0, 85.0, 85.0),      # North mound
        (40.0, 38.0, 1.8, 45.0, 45.0),       # Cardinal south underwater knoll
        (-210.0, -220.0, -2.4, 110.0, 110.0) # Southwest deep trench
    ]
    z_knolls = 0.0
    for cx, cy, amp, rx, ry in knolls:
        dist_sq = ((x - cx) / rx)**2 + ((y - cy) / ry)**2
        if dist_sq < 4.0:
            z_knolls += amp * math.exp(-0.5 * dist_sq)

    z_natural = z_reg + z_waves + z_knolls

    # 4. Harbor mole leveling:
    # Wall arms:
    # Arm 1: X in [65.0, 120.0], Y in [-4.5, 0.0]
    # Arm 2: X in [115.5, 120.0], Y in [0.0, 35.0]
    # Compute minimum distance to the two arms
    d_arm1_x = max(0.0, 65.0 - x, x - 120.0)
    d_arm1_y = max(0.0, -4.5 - y, y - 0.0)
    d_arm1 = math.sqrt(d_arm1_x**2 + d_arm1_y**2)

    d_arm2_x = max(0.0, 115.5 - x, x - 120.0)
    d_arm2_y = max(0.0, 0.0 - y, y - 35.0)
    d_arm2 = math.sqrt(d_arm2_x**2 + d_arm2_y**2)

    d_hw = min(d_arm1, d_arm2)

    # Smoothstep leveling within 24m of harbor wall
    blend_radius = 24.0
    if d_hw < blend_radius:
        # Smooth hermite weight from 1.0 (at wall) to 0.0 (at 24m)
        t = d_hw / blend_radius
        w = 1.0 - (3.0 * t**2 - 2.0 * t**3)
        z = (1.0 - w) * z_natural + w * (-base_depth)
    else:
        z = z_natural

    # Ensure depth is strictly submerged (-22m to -10m)
    return max(-22.0, min(-10.0, z))


def generate_rock_mesh(cx, cy, cz, rx, ry, rz, seed=0):
    """
    Generates a realistic 3D deformed polyhedron rock mesh.
    Returns:
      vertices: list of (x, y, z)
      faces: list of (i0, i1, i2)
    """
    t = (1.0 + math.sqrt(5.0)) / 2.0
    ico_verts = [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)
    ]
    ico_faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)
    ]
    # Subdivide icosahedron once (42 vertices, 80 faces)
    mid_cache = {}
    verts = [v for v in ico_verts]

    def get_mid(i1, i2):
        k = (min(i1, i2), max(i1, i2))
        if k in mid_cache:
            return mid_cache[k]
        v1, v2 = verts[i1], verts[i2]
        mv = ((v1[0] + v2[0]) * 0.5, (v1[1] + v2[1]) * 0.5, (v1[2] + v2[2]) * 0.5)
        idx = len(verts)
        verts.append(mv)
        mid_cache[k] = idx
        return idx

    sub_faces = []
    for f in ico_faces:
        m01 = get_mid(f[0], f[1])
        m12 = get_mid(f[1], f[2])
        m20 = get_mid(f[2], f[0])
        sub_faces.extend([
            (f[0], m01, m20),
            (f[1], m12, m01),
            (f[2], m20, m12),
            (m01, m12, m20)
        ])

    rnd = random.Random(seed)
    yaw = rnd.uniform(0, 2.0 * math.pi)
    cyaw, syaw = math.cos(yaw), math.sin(yaw)

    final_verts = []
    for vx, vy, vz in verts:
        dist = math.sqrt(vx * vx + vy * vy + vz * vz)
        nx, ny, nz = vx / dist, vy / dist, vz / dist

        # Multi-frequency radial displacement
        disp = 1.0 + 0.24 * (rnd.random() - 0.5) + 0.16 * math.sin(nx * 4.2 + ny * 3.1 + nz * 4.8)
        px = nx * rx * disp
        py = ny * ry * disp
        pz = nz * rz * disp

        # Flatten bottom so rock seats naturally on the seafloor
        if pz < -0.25 * rz:
            pz = -0.25 * rz + (pz + 0.25 * rz) * 0.35

        # Apply yaw rotation
        rx_rot = px * cyaw - py * syaw
        ry_rot = px * syaw + py * cyaw
        final_verts.append((cx + rx_rot, cy + ry_rot, cz + pz))

    return final_verts, sub_faces


def write_seafloor_mtl(mtl_path):
    """Writes the Wavefront MTL material library."""
    content = """# Seafloor Material Library
# Photorealistic underwater materials for Gazebo Sim (Ogre2 engine)

newmtl Seafloor_Sand
Ka 0.45 0.42 0.38
Kd 0.88 0.84 0.74
Ks 0.06 0.06 0.06
Ns 6.0
map_Kd textures/sand_ripples.png

newmtl Seafloor_Rock
Ka 0.34 0.34 0.32
Kd 0.65 0.68 0.65
Ks 0.12 0.12 0.12
Ns 18.0
map_Kd textures/rock_marine.png

newmtl Seafloor_Gravel
Ka 0.40 0.38 0.34
Kd 0.78 0.75 0.68
Ks 0.08 0.08 0.08
Ns 10.0
map_Kd textures/gravel_sand_mix.png
"""
    with open(mtl_path, "w") as f:
        f.write(content)


def generate_seafloor_mesh(obj_path, mtl_filename,
                           width=1000.0, length=1000.0, grid_res=121,
                           base_depth=16.2, num_rocks=120, seed=42):
    """
    Generates the complete seafloor OBJ mesh combining:
      1. Continuous undulating bathymetric terrain mesh with material classification
         (Seafloor_Sand, Seafloor_Gravel, Seafloor_Rock).
      2. 3D procedural boulders & rocks (breakwater riprap armor, reefs, solitary erratics).
    """
    print(f"  -> Building bathymetry terrain grid ({grid_res}x{grid_res}, {width}m x {length}m)...")
    half_w = width * 0.5
    half_l = length * 0.5
    dx = width / float(grid_res - 1)
    dy = length / float(grid_res - 1)

    # 1. Generate heightfield grid
    grid_z = []
    for j in range(grid_res):
        row_z = []
        y = -half_l + j * dy
        for i in range(grid_res):
            x = -half_w + i * dx
            row_z.append(compute_bathymetry(x, y, base_depth))
        grid_z.append(row_z)

    # 2. Compute smooth vertex normals & UVs
    all_verts = []
    all_uvs = []
    all_normals = []

    uv_tile = 16.0  # Texture repeats every 16 meters for high texel resolution
    for j in range(grid_res):
        y = -half_l + j * dy
        for i in range(grid_res):
            x = -half_w + i * dx
            z = grid_z[j][i]
            all_verts.append((x, y, z))

            # UV coordinates
            u = (x + half_w) / uv_tile
            v = (y + half_l) / uv_tile
            all_uvs.append((u, v))

            # Central difference gradient for normals
            i_prev = max(0, i - 1)
            i_next = min(grid_res - 1, i + 1)
            j_prev = max(0, j - 1)
            j_next = min(grid_res - 1, j + 1)

            dz_dx = (grid_z[j][i_next] - grid_z[j][i_prev]) / ((i_next - i_prev) * dx)
            dz_dy = (grid_z[j_next][i] - grid_z[j_prev][i]) / ((j_next - j_prev) * dy)

            # Normal pointing upward: (-dz/dx, -dz/dy, 1.0)
            norm_len = math.sqrt(dz_dx * dz_dx + dz_dy * dz_dy + 1.0)
            nx = -dz_dx / norm_len
            ny = -dz_dy / norm_len
            nz = 1.0 / norm_len
            all_normals.append((nx, ny, nz))

    # 3. Classify terrain triangles by material
    sand_faces = []
    gravel_faces = []
    rock_faces = []

    def get_v_idx(i, j):
        return j * grid_res + i + 1  # 1-indexed for OBJ

    for j in range(grid_res - 1):
        for i in range(grid_res - 1):
            v00 = get_v_idx(i, j)
            v10 = get_v_idx(i + 1, j)
            v11 = get_v_idx(i + 1, j + 1)
            v01 = get_v_idx(i, j + 1)

            quad_triangles = [
                (v00, v10, v11),
                (v00, v11, v01)
            ]

            for tri in quad_triangles:
                # Calculate slope and elevation for material selection
                z_avg = (all_verts[tri[0] - 1][2] + all_verts[tri[1] - 1][2] + all_verts[tri[2] - 1][2]) / 3.0
                nz_avg = (all_normals[tri[0] - 1][2] + all_normals[tri[1] - 1][2] + all_normals[tri[2] - 1][2]) / 3.0
                slope = math.sqrt(max(0.0, 1.0 - nz_avg * nz_avg))

                if slope > 0.065 or (z_avg > -13.5 and slope > 0.035):
                    rock_faces.append(tri)
                elif slope > 0.032 or (z_avg > -14.8 and slope > 0.022):
                    gravel_faces.append(tri)
                else:
                    sand_faces.append(tri)

    print(f"  -> Terrain faces classified: {len(sand_faces)} Sand, {len(gravel_faces)} Gravel, {len(rock_faces)} Rock")

    # 4. Generate 3D procedural boulders & rocks
    print(f"  -> Procedurally generating {num_rocks} 3D boulders & rock formations...")
    random.seed(seed)
    rock_locations = []

    # Category A: Breakwater toe riprap armor along harbor mole (X in [64, 122], Y in [-5, 36])
    # Protects breakwater foundation from seabed scour
    for _ in range(36):
        # Place boulders along outside and inside toe of harbor mole
        arm = random.choice([1, 2])
        if arm == 1:
            rx = random.uniform(64.0, 121.0)
            ry = random.choice([random.uniform(-6.5, -4.5), random.uniform(0.2, 1.8)])
        else:
            rx = random.choice([random.uniform(113.5, 115.5), random.uniform(120.2, 122.2)])
            ry = random.uniform(-1.0, 36.0)
        radius = random.uniform(1.4, 2.8)
        rock_locations.append((rx, ry, radius, radius * random.uniform(0.7, 1.1), radius * random.uniform(0.6, 0.95)))

    # Category B: Natural reef knoll clusters
    reef_centers = [
        (-150.0, 130.0, 18, 55.0),  # Northwest reef
        (180.0, -170.0, 14, 45.0),  # Southeast shoal
        (50.0, 260.0, 12, 40.0),    # North mound
        (40.0, 38.0, 10, 25.0)      # Cardinal mark knoll
    ]
    for cx, cy, count, spread in reef_centers:
        for _ in range(count):
            angle = random.uniform(0, 2.0 * math.pi)
            dist = random.uniform(2.0, spread)
            rx = cx + math.cos(angle) * dist
            ry = cy + math.sin(angle) * dist
            radius = random.uniform(1.2, 3.8)
            rock_locations.append((rx, ry, radius, radius * random.uniform(0.75, 1.2), radius * random.uniform(0.55, 0.9)))

    # Category C: Scattered solitary boulders & stones across continental shelf
    remaining = max(0, num_rocks - len(rock_locations))
    for _ in range(remaining):
        rx = random.uniform(-half_w + 30.0, half_w - 30.0)
        ry = random.uniform(-half_l + 30.0, half_l - 30.0)
        radius = random.uniform(1.0, 3.5)
        rock_locations.append((rx, ry, radius, radius * random.uniform(0.8, 1.2), radius * random.uniform(0.6, 0.95)))

    # Append rock geometry to vertices and rock_faces
    for idx_rock, (rx, ry, r_x, r_y, r_z) in enumerate(rock_locations):
        z_bed = compute_bathymetry(rx, ry, base_depth)
        # Embed bottom third of rock into seabed
        cz = z_bed + r_z * 0.35

        r_verts, r_faces = generate_rock_mesh(rx, ry, cz, r_x, r_y, r_z, seed=seed + idx_rock * 17)

        v_offset = len(all_verts) + 1
        for vx, vy, vz in r_verts:
            all_verts.append((vx, vy, vz))
            # Triplanar / spherical UV
            dx_r, dy_r, dz_r = vx - rx, vy - ry, vz - cz
            r_dist = math.sqrt(dx_r * dx_r + dy_r * dy_r + dz_r * dz_r) + 1e-6
            u_r = math.atan2(dy_r, dx_r) / (2.0 * math.pi) + 0.5
            v_r = (dz_r / r_dist) * 0.5 + 0.5
            all_uvs.append((u_r * 2.5, v_r * 2.5))
            all_normals.append((dx_r / r_dist, dy_r / r_dist, dz_r / r_dist))

        for f0, f1, f2 in r_faces:
            rock_faces.append((v_offset + f0, v_offset + f1, v_offset + f2))

    # 5. Write Wavefront OBJ file
    print(f"  -> Writing Wavefront OBJ ({len(all_verts)} vertices, {len(sand_faces) + len(gravel_faces) + len(rock_faces)} faces)...")
    with open(obj_path, "w") as f:
        f.write("# Wavefront OBJ Procedural Seafloor\n")
        f.write(f"mtllib {mtl_filename}\n\n")

        # Write vertices
        for vx, vy, vz in all_verts:
            f.write(f"v {vx:.4f} {vy:.4f} {vz:.4f}\n")

        # Write UVs
        for u, v in all_uvs:
            f.write(f"vt {u:.4f} {v:.4f}\n")

        # Write normals
        for nx, ny, nz in all_normals:
            f.write(f"vn {nx:.4f} {ny:.4f} {nz:.4f}\n")

        # Write Sand Faces
        f.write("\nusemtl Seafloor_Sand\ns 1\n")
        for i0, i1, i2 in sand_faces:
            f.write(f"f {i0}/{i0}/{i0} {i1}/{i1}/{i1} {i2}/{i2}/{i2}\n")

        # Write Gravel Faces
        f.write("\nusemtl Seafloor_Gravel\ns 1\n")
        for i0, i1, i2 in gravel_faces:
            f.write(f"f {i0}/{i0}/{i0} {i1}/{i1}/{i1} {i2}/{i2}/{i2}\n")

        # Write Rock Faces
        f.write("\nusemtl Seafloor_Rock\ns 1\n")
        for i0, i1, i2 in rock_faces:
            f.write(f"f {i0}/{i0}/{i0} {i1}/{i1}/{i1} {i2}/{i2}/{i2}\n")

    print(f"  -> Seafloor OBJ successfully written to: {obj_path}")


def write_seafloor_sdf(model_dir, model_name="seafloor"):
    """Writes the SDF 1.9 file for the seafloor model (strictly visual only, no collisions)."""
    sdf_content = f"""<?xml version="1.0" ?>
<sdf version="1.9">
  <model name="{model_name}">
    <static>true</static>
    <link name="seafloor_link">
      <!-- High-Fidelity Photorealistic Visual Mesh (Zero Collision Overhead) -->
      <visual name="seafloor_visual">
        <pose>0 0 0 0 0 0</pose>
        <geometry>
          <mesh>
            <uri>model://{model_name}/meshes/{model_name}.obj</uri>
          </mesh>
        </geometry>
      </visual>
    </link>
  </model>
</sdf>
"""
    with open(os.path.join(model_dir, "model.sdf"), "w") as f:
        f.write(sdf_content)


def write_model_config(model_dir, model_name="seafloor"):
    """Writes the model.config file for Gazebo Sim."""
    config_content = f"""<?xml version="1.0" ?>
<model>
  <name>{model_name}</name>
  <version>1.0</version>
  <sdf version="1.9">model.sdf</sdf>
  <author>
    <name>Ocean Regatta Team</name>
    <email>regatta@ocean.org</email>
  </author>
  <description>
    Realistic procedural seafloor with natural bathymetry, rippled sand dunes,
    gravel beds, and 3D scattered rock formations. Visual only, no collision.
  </description>
</model>
"""
    with open(os.path.join(model_dir, "model.config"), "w") as f:
        f.write(config_content)


def update_world_sdf(world_file, model_name="seafloor"):
    """
    Checks if model://seafloor is included in world_file;
    if not, cleanly injects the <include> block right after the waves model.
    """
    if not os.path.exists(world_file):
        print(f"Warning: World file {world_file} does not exist. Skipping update.")
        return False

    with open(world_file, "r") as f:
        content = f.read()

    include_uri = f"<uri>model://{model_name}</uri>"
    if include_uri in content:
        print(f"  -> Model '{model_name}' already included in {world_file}")
        return True

    include_block = f"""
    <!-- Procedural Seafloor (Sand and Rocks) -->
    <include>
      <uri>model://{model_name}</uri>
      <name>{model_name}</name>
      <pose>0 0 0 0 0 0</pose>
    </include>
"""

    # Inject right after </include> of the waves model or right before BlueBoat
    target_marker = "</include>\n\n    <!-- BlueBoat USV Model -->"
    if target_marker in content:
        content = content.replace(target_marker, f"</include>\n{include_block}\n    <!-- BlueBoat USV Model -->")
    elif "<name>waves</name>" in content:
        # Find closing tag of waves include
        pos_waves = content.find("<name>waves</name>")
        pos_close = content.find("</include>", pos_waves)
        if pos_close != -1:
            end_pos = pos_close + len("</include>")
            content = content[:end_pos] + "\n" + include_block + content[end_pos:]
        else:
            # Fallback: right before </world>
            content = content.replace("</world>", f"{include_block}\n  </world>")
    else:
        content = content.replace("</world>", f"{include_block}\n  </world>")

    with open(world_file, "w") as f:
        f.write(content)

    print(f"  -> Successfully added '{model_name}' to {world_file}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate realistic procedural seafloor for Gazebo Sim.")
    parser.add_argument("--output-dir", type=str, default="models/seafloor",
                        help="Path to output model directory (default: models/seafloor)")
    parser.add_argument("--model-name", type=str, default="seafloor",
                        help="Model name (default: seafloor)")
    parser.add_argument("--width", type=float, default=1000.0,
                        help="Seafloor width along X in meters (default: 1000.0)")
    parser.add_argument("--length", type=float, default=1000.0,
                        help="Seafloor length along Y in meters (default: 1000.0)")
    parser.add_argument("--grid-res", type=int, default=121,
                        help="Bathymetric grid resolution (default: 121)")
    parser.add_argument("--base-depth", type=float, default=16.2,
                        help="Base depth below waterline in meters (default: 16.2)")
    parser.add_argument("--num-rocks", type=int, default=120,
                        help="Number of 3D boulders & rock formations (default: 120)")
    parser.add_argument("--tex-size", type=int, default=512,
                        help="Texture resolution in pixels (default: 512)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for procedural generation (default: 42)")
    parser.add_argument("--update-world", action="store_true", default=True,
                        help="Automatically update evaluation_world.sdf and practice_world.sdf")
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    model_dir = os.path.abspath(os.path.join(repo_root, args.output_dir))
    meshes_dir = os.path.join(model_dir, "meshes")
    tex_dir = os.path.join(meshes_dir, "textures")

    print(f"=== [1/4] Generating Procedural Textures ({args.tex_size}x{args.tex_size}) ===")
    generate_textures(tex_dir, size=args.tex_size, seed=args.seed)

    print(f"\n=== [2/4] Generating Material Library & 3D Bathymetry Mesh ===")
    mtl_filename = f"{args.model_name}.mtl"
    obj_filename = f"{args.model_name}.obj"
    write_seafloor_mtl(os.path.join(meshes_dir, mtl_filename))
    generate_seafloor_mesh(
        os.path.join(meshes_dir, obj_filename),
        mtl_filename,
        width=args.width,
        length=args.length,
        grid_res=args.grid_res,
        base_depth=args.base_depth,
        num_rocks=args.num_rocks,
        seed=args.seed
    )

    print(f"\n=== [3/4] Writing SDF 1.9 & Model Config (Visual-Only) ===")
    write_seafloor_sdf(model_dir, model_name=args.model_name)
    write_model_config(model_dir, model_name=args.model_name)

    if args.update_world:
        print(f"\n=== [4/4] Updating World SDF Files ===")
        eval_world = os.path.join(repo_root, "worlds", "evaluation_world.sdf")
        practice_world = os.path.join(repo_root, "worlds", "practice_world.sdf")
        update_world_sdf(eval_world, model_name=args.model_name)
        update_world_sdf(practice_world, model_name=args.model_name)

    print(f"\n=== Seafloor generation complete! Model located at: {model_dir} ===")


if __name__ == "__main__":
    main()

