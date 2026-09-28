#!/usr/bin/env python3
"""
Realistic Deep Harbor Wall & Breakwater Generator for Gazebo Sim (Jetty / Harmonic).
Generates high-fidelity 3D models (OBJ + MTL + PNG textures) and SDF 1.9 files
for straight, angled (L-shaped inner & outer/reverted), and modular corner quay walls.

Depth: Default 16.2 m below waterline (exceeds the >= 15 m requirement).
Features:
  - Multi-tier photorealistic textures:
      * Weathered concrete quay deck with paving expansion joints
      * Safety curb with yellow/black hazard striping
      * Precast concrete upper wall with vertical panel joints & rain streaks
      * Waterline / tidal splash zone with green-brown algae patina & barnacle specks
      * Deep submerged concrete wall extending down to -16.2 m
  - Correct normal and CCW winding order on all faces (no inverted / transparent faces)
  - Both inner and outer (reverted / mirrored) L-shaped wall support:
      * 'inner': yellow/black curb & berthing face on the inside of the L (enclosed basin)
      * 'outer': yellow/black curb & berthing face on the outside of the L (outer breakwater/sea mole)
  - Properly oriented emergency rescue ladders and rubber fenders on all arms
  - Collision geometry:
      * Clean analytical box collision shapes for optimal physics and precise
        GPU LiDAR / Ping2 acoustic echosounder reflection at 5.0 m standoff.
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
        raw_lines.append(0)
        start = y * row_bytes
        raw_lines.extend(rgb_data[start : start + row_bytes])
    idat = chunk(b'IDAT', zlib.compress(bytes(raw_lines), 6))
    iend = chunk(b'IEND', b'')
    with open(filename, 'wb') as f:
        f.write(header + ihdr + idat + iend)

def clamp(val, low=0, high=255):
    return max(low, min(high, int(val)))

def generate_textures(tex_dir):
    os.makedirs(tex_dir, exist_ok=True)
    random.seed(42)
    w, h = 256, 256

    # 1. Concrete Deck
    deck_rgb = bytearray(w * h * 3)
    tile_size = 64
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 3
            base = 155 + random.randint(-12, 12)
            is_joint = (x % tile_size in (0, tile_size - 1)) or (y % tile_size in (0, tile_size - 1))
            if is_joint:
                r, g, b = clamp(base - 55), clamp(base - 55), clamp(base - 52)
            else:
                tile_id = (x // tile_size) + (y // tile_size) * 7
                t_offset = ((tile_id * 17) % 25) - 12
                r = clamp(base + t_offset)
                g = clamp(base + t_offset - 2)
                b = clamp(base + t_offset - 4)
            deck_rgb[idx] = r
            deck_rgb[idx+1] = g
            deck_rgb[idx+2] = b
    write_png(os.path.join(tex_dir, "concrete_deck.png"), w, h, deck_rgb)

    # 2. Safety Curb (yellow/black hazard stripes)
    curb_rgb = bytearray(w * h * 3)
    stripe_w = 32
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 3
            diag = (x + y) // stripe_w
            noise = random.randint(-15, 15)
            edge_dist = min(x, w - 1 - x, y, h - 1 - y)
            wear = 0.85 if edge_dist < 4 else 1.0
            if diag % 2 == 0:
                r = clamp((220 + noise) * wear)
                g = clamp((180 + noise) * wear)
                b = clamp((25 + noise // 2) * wear)
            else:
                val = clamp((45 + noise // 2) * wear)
                r, g, b = val, val, clamp(val + 5)
            curb_rgb[idx] = r
            curb_rgb[idx+1] = g
            curb_rgb[idx+2] = b
    write_png(os.path.join(tex_dir, "quay_curb.png"), w, h, curb_rgb)

    # 3. Upper Wall
    wall_upper_rgb = bytearray(w * h * 3)
    panel_w = 64
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 3
            noise = random.randint(-14, 14)
            base = 138 + noise
            if x % panel_w in (0, panel_w - 1):
                base -= 45
            streak = int(math.sin(x * 0.25) * 8 + math.sin(x * 0.05 + y * 0.02) * 12)
            r = clamp(base + streak)
            g = clamp(base + streak - 1)
            b = clamp(base + streak - 3)
            wall_upper_rgb[idx] = r
            wall_upper_rgb[idx+1] = g
            wall_upper_rgb[idx+2] = b
    write_png(os.path.join(tex_dir, "quay_wall_upper.png"), w, h, wall_upper_rgb)

    # 4. Tidal Zone
    tidal_rgb = bytearray(w * h * 3)
    for y in range(h):
        t = y / float(h)
        for x in range(w):
            idx = (y * w + x) * 3
            noise = random.randint(-12, 12)
            wetness = 0.55 + 0.35 * (1.0 - t * 0.7)
            algae_peak = math.exp(-((t - 0.5) ** 2) / 0.06)
            is_barnacle = (random.random() < 0.03 and 0.2 < t < 0.7)
            if is_barnacle:
                r, g, b = 210, 205, 195
            else:
                base_r = int((110 + noise) * wetness)
                base_g = int((115 + noise) * wetness + algae_peak * 38)
                base_b = int((95 + noise) * wetness - algae_peak * 15)
                r = clamp(base_r)
                g = clamp(base_g)
                b = clamp(base_b)
            tidal_rgb[idx] = r
            tidal_rgb[idx+1] = g
            tidal_rgb[idx+2] = b
    write_png(os.path.join(tex_dir, "quay_wall_tidal.png"), w, h, tidal_rgb)

    # 5. Deep Submerged Wall
    submerged_rgb = bytearray(w * h * 3)
    for y in range(h):
        t = y / float(h)
        for x in range(w):
            idx = (y * w + x) * 3
            noise = random.randint(-10, 10)
            shade = 0.65 - 0.25 * t
            r = clamp((60 + noise) * shade)
            g = clamp((75 + noise) * shade)
            b = clamp((82 + noise) * shade)
            submerged_rgb[idx] = r
            submerged_rgb[idx+1] = g
            submerged_rgb[idx+2] = b
    write_png(os.path.join(tex_dir, "quay_wall_submerged.png"), w, h, submerged_rgb)

    # 6. Rubber Fender
    fender_rgb = bytearray(w * h * 3)
    for y in range(h):
        rib = 1.0 if (y % 16 < 8) else 0.82
        for x in range(w):
            idx = (y * w + x) * 3
            noise = random.randint(-6, 6)
            val = clamp((38 + noise) * rib)
            fender_rgb[idx] = val
            fender_rgb[idx+1] = val
            fender_rgb[idx+2] = clamp(val + 3)
    write_png(os.path.join(tex_dir, "fender_rubber.png"), w, h, fender_rgb)

    # 7. Cast Iron Bollard
    bollard_rgb = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 3
            noise = random.randint(-8, 8)
            base = 48 + noise
            if random.random() < 0.02:
                r, g, b = clamp(base + 40), clamp(base + 15), clamp(base - 10)
            else:
                r = clamp(base)
                g = clamp(base)
                b = clamp(base + 2)
            bollard_rgb[idx] = r
            bollard_rgb[idx+1] = g
            bollard_rgb[idx+2] = b
    write_png(os.path.join(tex_dir, "bollard_cast_iron.png"), w, h, bollard_rgb)

    # 8. Safety Ladder
    ladder_rgb = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 3
            noise = random.randint(-12, 12)
            ladder_rgb[idx] = clamp(235 + noise)
            ladder_rgb[idx+1] = clamp(195 + noise)
            ladder_rgb[idx+2] = clamp(30 + noise // 2)
    write_png(os.path.join(tex_dir, "ladder_yellow.png"), w, h, ladder_rgb)


def write_mtl(mtl_path, tex_relative_dir="textures"):
    with open(mtl_path, "w") as f:
        f.write(f"""# Harbor Wall Material Library
newmtl Quay_Deck
Ka 0.6 0.6 0.6
Kd 0.8 0.8 0.8
Ks 0.1 0.1 0.1
Ns 10.0
map_Kd {tex_relative_dir}/concrete_deck.png

newmtl Quay_Curb
Ka 0.6 0.6 0.6
Kd 0.85 0.85 0.85
Ks 0.2 0.2 0.2
Ns 20.0
map_Kd {tex_relative_dir}/quay_curb.png

newmtl Quay_Wall_Upper
Ka 0.5 0.5 0.5
Kd 0.8 0.8 0.8
Ks 0.05 0.05 0.05
Ns 5.0
map_Kd {tex_relative_dir}/quay_wall_upper.png

newmtl Quay_Wall_Tidal
Ka 0.4 0.4 0.4
Kd 0.7 0.7 0.7
Ks 0.25 0.25 0.25
Ns 35.0
map_Kd {tex_relative_dir}/quay_wall_tidal.png

newmtl Quay_Wall_Submerged
Ka 0.3 0.35 0.35
Kd 0.55 0.6 0.62
Ks 0.05 0.05 0.05
Ns 5.0
map_Kd {tex_relative_dir}/quay_wall_submerged.png

newmtl Fender_Rubber
Ka 0.15 0.15 0.15
Kd 0.25 0.25 0.27
Ks 0.1 0.1 0.1
Ns 15.0
map_Kd {tex_relative_dir}/fender_rubber.png

newmtl Bollard_CastIron
Ka 0.2 0.2 0.2
Kd 0.3 0.3 0.32
Ks 0.6 0.6 0.65
Ns 60.0
map_Kd {tex_relative_dir}/bollard_cast_iron.png

newmtl Safety_Ladder
Ka 0.5 0.4 0.1
Kd 0.9 0.75 0.15
Ks 0.3 0.3 0.3
Ns 30.0
map_Kd {tex_relative_dir}/ladder_yellow.png
""")


class ObjMeshBuilder:
    def __init__(self, mtl_filename):
        self.mtl_filename = mtl_filename
        self.vertices = []
        self.uvs = []
        self.normals = []
        self.faces = []
        self.current_material = None

    def set_material(self, mat_name):
        self.current_material = mat_name

    def add_vertex(self, x, y, z):
        self.vertices.append((x, y, z))
        return len(self.vertices)

    def add_uv(self, u, v):
        self.uvs.append((u, v))
        return len(self.uvs)

    def add_normal(self, nx, ny, nz):
        self.normals.append((nx, ny, nz))
        return len(self.normals)

    def add_face(self, v_vt_vn_list):
        self.faces.append((self.current_material, v_vt_vn_list))

    def add_quad(self, p1, p2, p3, p4, uv1, uv2, uv3, uv4, normal):
        """
        Adds a quad as two triangles with automatic counter-clockwise (CCW) winding.
        Guarantees that the surface normal points outward towards the viewer and is not culled.
        """
        v12 = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        v13 = (p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
        cross_prod = (
            v12[1] * v13[2] - v12[2] * v13[1],
            v12[2] * v13[0] - v12[0] * v13[2],
            v12[0] * v13[1] - v12[1] * v13[0]
        )
        dot_prod = cross_prod[0] * normal[0] + cross_prod[1] * normal[1] + cross_prod[2] * normal[2]

        if dot_prod < 0:
            # Winding order was clockwise; swap to counter-clockwise
            p1, p2, p3, p4 = p1, p4, p3, p2
            uv1, uv2, uv3, uv4 = uv1, uv4, uv3, uv2

        nx, ny, nz = normal
        mag = math.sqrt(nx*nx + ny*ny + nz*nz)
        if mag > 1e-6:
            nx, ny, nz = nx/mag, ny/mag, nz/mag
        n_idx = self.add_normal(nx, ny, nz)

        v1 = self.add_vertex(*p1)
        v2 = self.add_vertex(*p2)
        v3 = self.add_vertex(*p3)
        v4 = self.add_vertex(*p4)

        t1 = self.add_uv(*uv1)
        t2 = self.add_uv(*uv2)
        t3 = self.add_uv(*uv3)
        t4 = self.add_uv(*uv4)

        self.add_face([(v1, t1, n_idx), (v2, t2, n_idx), (v3, t3, n_idx)])
        self.add_face([(v1, t1, n_idx), (v3, t3, n_idx), (v4, t4, n_idx)])

    def add_triangle(self, p1, p2, p3, uv1, uv2, uv3, normal):
        v12 = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        v13 = (p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
        cross_prod = (
            v12[1] * v13[2] - v12[2] * v13[1],
            v12[2] * v13[0] - v12[0] * v13[2],
            v12[0] * v13[1] - v12[1] * v13[0]
        )
        dot_prod = cross_prod[0] * normal[0] + cross_prod[1] * normal[1] + cross_prod[2] * normal[2]

        if dot_prod < 0:
            p2, p3 = p3, p2
            uv2, uv3 = uv3, uv2

        nx, ny, nz = normal
        mag = math.sqrt(nx*nx + ny*ny + nz*nz)
        if mag > 1e-6:
            nx, ny, nz = nx/mag, ny/mag, nz/mag
        n_idx = self.add_normal(nx, ny, nz)
        v1 = self.add_vertex(*p1)
        v2 = self.add_vertex(*p2)
        v3 = self.add_vertex(*p3)
        t1 = self.add_uv(*uv1)
        t2 = self.add_uv(*uv2)
        t3 = self.add_uv(*uv3)
        self.add_face([(v1, t1, n_idx), (v2, t2, n_idx), (v3, t3, n_idx)])

    def add_box(self, x_min, x_max, y_min, y_max, z_min, z_max, u_scale=1.0, v_scale=1.0):
        # Top (+z)
        self.add_quad(
            (x_min, y_min, z_max), (x_max, y_min, z_max), (x_max, y_max, z_max), (x_min, y_max, z_max),
            (0, 0), ((x_max-x_min)*u_scale, 0), ((x_max-x_min)*u_scale, (y_max-y_min)*v_scale), (0, (y_max-y_min)*v_scale),
            (0, 0, 1)
        )
        # Bottom (-z)
        self.add_quad(
            (x_min, y_max, z_min), (x_max, y_max, z_min), (x_max, y_min, z_min), (x_min, y_min, z_min),
            (0, 0), ((x_max-x_min)*u_scale, 0), ((x_max-x_min)*u_scale, (y_max-y_min)*v_scale), (0, (y_max-y_min)*v_scale),
            (0, 0, -1)
        )
        # Front (+y)
        self.add_quad(
            (x_min, y_max, z_min), (x_max, y_max, z_min), (x_max, y_max, z_max), (x_min, y_max, z_max),
            (0, 0), ((x_max-x_min)*u_scale, 0), ((x_max-x_min)*u_scale, (z_max-z_min)*v_scale), (0, (z_max-z_min)*v_scale),
            (0, 1, 0)
        )
        # Back (-y)
        self.add_quad(
            (x_max, y_min, z_min), (x_min, y_min, z_min), (x_min, y_min, z_max), (x_max, y_min, z_max),
            (0, 0), ((x_max-x_min)*u_scale, 0), ((x_max-x_min)*u_scale, (z_max-z_min)*v_scale), (0, (z_max-z_min)*v_scale),
            (0, -1, 0)
        )
        # Left (-x)
        self.add_quad(
            (x_min, y_min, z_min), (x_min, y_max, z_min), (x_min, y_max, z_max), (x_min, y_min, z_max),
            (0, 0), ((y_max-y_min)*u_scale, 0), ((y_max-y_min)*u_scale, (z_max-z_min)*v_scale), (0, (z_max-z_min)*v_scale),
            (-1, 0, 0)
        )
        # Right (+x)
        self.add_quad(
            (x_max, y_max, z_min), (x_max, y_min, z_min), (x_max, y_min, z_max), (x_max, y_max, z_max),
            (0, 0), ((y_max-y_min)*u_scale, 0), ((y_max-y_min)*u_scale, (z_max-z_min)*v_scale), (0, (z_max-z_min)*v_scale),
            (1, 0, 0)
        )

    def add_cylinder(self, cx, cy, z_bottom, z_top, radius, num_sides=12, capped=True):
        angles = [2.0 * math.pi * i / num_sides for i in range(num_sides)]
        for i in range(num_sides):
            i_next = (i + 1) % num_sides
            a1, a2 = angles[i], angles[i_next]
            x1, y1 = cx + radius * math.cos(a1), cy + radius * math.sin(a1)
            x2, y2 = cx + radius * math.cos(a2), cy + radius * math.sin(a2)
            nx = math.cos((a1 + a2) / 2.0)
            ny = math.sin((a1 + a2) / 2.0)

            v1 = (x1, y1, z_bottom)
            v2 = (x2, y2, z_bottom)
            v3 = (x2, y2, z_top)
            v4 = (x1, y1, z_top)

            u1 = i / float(num_sides)
            u2 = (i + 1) / float(num_sides)
            self.add_quad(v1, v2, v3, v4, (u1, 0), (u2, 0), (u2, 1), (u1, 1), (nx, ny, 0))

        if capped:
            v_center_top = (cx, cy, z_top)
            v_center_bot = (cx, cy, z_bottom)
            t_center = (0.5, 0.5)
            for i in range(num_sides):
                i_next = (i + 1) % num_sides
                a1, a2 = angles[i], angles[i_next]
                va = (cx + radius * math.cos(a1), cy + radius * math.sin(a1), z_top)
                vb = (cx + radius * math.cos(a2), cy + radius * math.sin(a2), z_top)
                ta = (0.5 + 0.5 * math.cos(a1), 0.5 + 0.5 * math.sin(a1))
                tb = (0.5 + 0.5 * math.cos(a2), 0.5 + 0.5 * math.sin(a2))
                self.add_triangle(v_center_top, va, vb, t_center, ta, tb, (0, 0, 1))

                va_b = (cx + radius * math.cos(a1), cy + radius * math.sin(a1), z_bottom)
                vb_b = (cx + radius * math.cos(a2), cy + radius * math.sin(a2), z_bottom)
                self.add_triangle(v_center_bot, vb_b, va_b, t_center, tb, ta, (0, 0, -1))

    def add_arch_fender(self, cx, cy, z_center, radius=0.30, length=1.2, orientation='y+', num_sides=8):
        """
        Semi-cylindrical marine rubber arch fender.
        orientation='y+': mounted on wall facing +y (Arm 1 inner)
        orientation='y-': mounted on wall facing -y (Arm 1 outer)
        orientation='x-': mounted on wall facing -x (Arm 2 inner)
        orientation='x+': mounted on wall facing +x (Arm 2 outer)
        """
        z_bottom = z_center - length / 2.0
        z_top = z_center + length / 2.0
        angles = [-math.pi / 2.0 + math.pi * i / num_sides for i in range(num_sides + 1)]

        for i in range(num_sides):
            a1, a2 = angles[i], angles[i+1]
            am = (a1 + a2) / 2.0

            if orientation == 'y+':
                p1 = (cx + radius * math.sin(a1), cy + radius * math.cos(a1), z_bottom)
                p2 = (cx + radius * math.sin(a2), cy + radius * math.cos(a2), z_bottom)
                p3 = (cx + radius * math.sin(a2), cy + radius * math.cos(a2), z_top)
                p4 = (cx + radius * math.sin(a1), cy + radius * math.cos(a1), z_top)
                normal = (math.sin(am), math.cos(am), 0)
            elif orientation == 'y-':
                p1 = (cx + radius * math.sin(a1), cy - radius * math.cos(a1), z_bottom)
                p2 = (cx + radius * math.sin(a2), cy - radius * math.cos(a2), z_bottom)
                p3 = (cx + radius * math.sin(a2), cy - radius * math.cos(a2), z_top)
                p4 = (cx + radius * math.sin(a1), cy - radius * math.cos(a1), z_top)
                normal = (math.sin(am), -math.cos(am), 0)
            elif orientation == 'x-':
                p1 = (cx - radius * math.cos(a1), cy + radius * math.sin(a1), z_bottom)
                p2 = (cx - radius * math.cos(a2), cy + radius * math.sin(a2), z_bottom)
                p3 = (cx - radius * math.cos(a2), cy + radius * math.sin(a2), z_top)
                p4 = (cx - radius * math.cos(a1), cy + radius * math.sin(a1), z_top)
                normal = (-math.cos(am), math.sin(am), 0)
            else: # 'x+'
                p1 = (cx + radius * math.cos(a1), cy + radius * math.sin(a1), z_bottom)
                p2 = (cx + radius * math.cos(a2), cy + radius * math.sin(a2), z_bottom)
                p3 = (cx + radius * math.cos(a2), cy + radius * math.sin(a2), z_top)
                p4 = (cx + radius * math.cos(a1), cy + radius * math.sin(a1), z_top)
                normal = (math.cos(am), math.sin(am), 0)

            t1 = (i / float(num_sides), 0)
            t2 = ((i + 1) / float(num_sides), 0)
            t3 = ((i + 1) / float(num_sides), 1)
            t4 = (i / float(num_sides), 1)
            self.add_quad(p1, p2, p3, p4, t1, t2, t3, t4, normal)

        # End caps
        for i in range(num_sides):
            a1, a2 = angles[i], angles[i+1]
            if orientation == 'y+':
                va_t = (cx + radius * math.sin(a1), cy + radius * math.cos(a1), z_top)
                vb_t = (cx + radius * math.sin(a2), cy + radius * math.cos(a2), z_top)
                va_b = (cx + radius * math.sin(a1), cy + radius * math.cos(a1), z_bottom)
                vb_b = (cx + radius * math.sin(a2), cy + radius * math.cos(a2), z_bottom)
            elif orientation == 'y-':
                va_t = (cx + radius * math.sin(a1), cy - radius * math.cos(a1), z_top)
                vb_t = (cx + radius * math.sin(a2), cy - radius * math.cos(a2), z_top)
                va_b = (cx + radius * math.sin(a1), cy - radius * math.cos(a1), z_bottom)
                vb_b = (cx + radius * math.sin(a2), cy - radius * math.cos(a2), z_bottom)
            elif orientation == 'x-':
                va_t = (cx - radius * math.cos(a1), cy + radius * math.sin(a1), z_top)
                vb_t = (cx - radius * math.cos(a2), cy + radius * math.sin(a2), z_top)
                va_b = (cx - radius * math.cos(a1), cy + radius * math.sin(a1), z_bottom)
                vb_b = (cx - radius * math.cos(a2), cy + radius * math.sin(a2), z_bottom)
            else: # 'x+'
                va_t = (cx + radius * math.cos(a1), cy + radius * math.sin(a1), z_top)
                vb_t = (cx + radius * math.cos(a2), cy + radius * math.sin(a2), z_top)
                va_b = (cx + radius * math.cos(a1), cy + radius * math.sin(a1), z_bottom)
                vb_b = (cx + radius * math.cos(a2), cy + radius * math.sin(a2), z_bottom)

            vc_t = (cx, cy, z_top)
            vc_b = (cx, cy, z_bottom)
            self.add_triangle(vc_t, va_t, vb_t, (0.5, 0.5), (0.5, 1.0), (1.0, 1.0), (0, 0, 1))
            self.add_triangle(vc_b, vb_b, va_b, (0.5, 0.5), (1.0, 1.0), (0.5, 1.0), (0, 0, -1))

    def add_bollard(self, cx, cy, z_base):
        self.add_cylinder(cx, cy, z_base, z_base + 0.08, radius=0.35, num_sides=12, capped=True)
        self.add_cylinder(cx, cy, z_base + 0.08, z_base + 0.55, radius=0.22, num_sides=12, capped=False)
        self.add_cylinder(cx, cy, z_base + 0.55, z_base + 0.68, radius=0.29, num_sides=12, capped=True)
        self.add_box(cx - 0.38, cx + 0.38, cy - 0.08, cy + 0.08, z_base + 0.36, z_base + 0.44)

    def add_ladder(self, cx, cy, z_top, z_bottom, orientation='y+', width=0.55):
        """
        Emergency safety rescue ladder with horizontal rungs and vertical side rails.
        orientation='y+': mounted on wall facing +y (Arm 1 inner)
        orientation='y-': mounted on wall facing -y (Arm 1 outer)
        orientation='x-': mounted on wall facing -x (Arm 2 inner)
        orientation='x+': mounted on wall facing +x (Arm 2 outer)
        """
        half_w = width / 2.0
        rail_t = 0.04
        rung_spacing = 0.30
        num_rungs = int((z_top - z_bottom) / rung_spacing)

        if orientation == 'y+':
            self.add_box(cx - half_w - rail_t, cx - half_w, cy - 0.05, cy + 0.02, z_bottom, z_top + 0.4)
            self.add_box(cx + half_w, cx + half_w + rail_t, cy - 0.05, cy + 0.02, z_bottom, z_top + 0.4)
            for r in range(num_rungs):
                rz = z_bottom + (r + 0.5) * rung_spacing
                self.add_box(cx - half_w, cx + half_w, cy - 0.03, cy + 0.01, rz - 0.018, rz + 0.018)
        elif orientation == 'y-':
            self.add_box(cx - half_w - rail_t, cx - half_w, cy - 0.02, cy + 0.05, z_bottom, z_top + 0.4)
            self.add_box(cx + half_w, cx + half_w + rail_t, cy - 0.02, cy + 0.05, z_bottom, z_top + 0.4)
            for r in range(num_rungs):
                rz = z_bottom + (r + 0.5) * rung_spacing
                self.add_box(cx - half_w, cx + half_w, cy - 0.01, cy + 0.03, rz - 0.018, rz + 0.018)
        elif orientation == 'x-':
            self.add_box(cx - 0.02, cx + 0.05, cy - half_w - rail_t, cy - half_w, z_bottom, z_top + 0.4)
            self.add_box(cx - 0.02, cx + 0.05, cy + half_w, cy + half_w + rail_t, z_bottom, z_top + 0.4)
            for r in range(num_rungs):
                rz = z_bottom + (r + 0.5) * rung_spacing
                self.add_box(cx - 0.01, cx + 0.03, cy - half_w, cy + half_w, rz - 0.018, rz + 0.018)
        else: # 'x+'
            self.add_box(cx - 0.05, cx + 0.02, cy - half_w - rail_t, cy - half_w, z_bottom, z_top + 0.4)
            self.add_box(cx - 0.05, cx + 0.02, cy + half_w, cy + half_w + rail_t, z_bottom, z_top + 0.4)
            for r in range(num_rungs):
                rz = z_bottom + (r + 0.5) * rung_spacing
                self.add_box(cx - 0.03, cx + 0.01, cy - half_w, cy + half_w, rz - 0.018, rz + 0.018)

    def export(self, filepath):
        with open(filepath, "w") as f:
            f.write(f"# Wavefront OBJ Harbor Wall\nmtllib {self.mtl_filename}\n\n")
            for x, y, z in self.vertices:
                f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
            f.write("\n")
            for u, v in self.uvs:
                f.write(f"vt {u:.4f} {v:.4f}\n")
            f.write("\n")
            for nx, ny, nz in self.normals:
                f.write(f"vn {nx:.4f} {ny:.4f} {nz:.4f}\n")
            f.write("\n")

            current_mat = None
            for mat, f_list in self.faces:
                if mat != current_mat:
                    f.write(f"usemtl {mat}\n")
                    current_mat = mat
                face_str = " ".join([f"{v}/{vt}/{vn}" for v, vt, vn in f_list])
                f.write(f"f {face_str}\n")


def generate_straight_wall(output_dir, length=55.0, width=4.5, depth=16.2, deck_h=1.8, curb_h=2.0, model_name="harbor_wall_straight"):
    model_dir = os.path.join(output_dir, model_name)
    meshes_dir = os.path.join(model_dir, "meshes")
    tex_dir = os.path.join(meshes_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    generate_textures(tex_dir)
    mtl_name = f"{model_name}.mtl"
    write_mtl(os.path.join(meshes_dir, mtl_name))

    builder = ObjMeshBuilder(mtl_name)

    x_min = -length / 2.0
    x_max = length / 2.0
    y_min = -width
    y_max = 0.0
    z_bot = -depth
    z_tidal_bot = -1.5
    z_tidal_top = 0.6
    cw = 0.35

    # 1. Deck
    builder.set_material("Quay_Deck")
    builder.add_quad(
        (x_min, y_min, deck_h), (x_max, y_min, deck_h), (x_max, y_max - cw, deck_h), (x_min, y_max - cw, deck_h),
        (0, 0), (length / 4.0, 0), (length / 4.0, (width - cw) / 4.0), (0, (width - cw) / 4.0),
        (0, 0, 1)
    )

    # 2. Curb
    builder.set_material("Quay_Curb")
    builder.add_quad(
        (x_min, y_max - cw, curb_h), (x_max, y_max - cw, curb_h), (x_max, y_max, curb_h), (x_min, y_max, curb_h),
        (0, 0), (length / 2.0, 0), (length / 2.0, cw), (0, cw),
        (0, 0, 1)
    )
    builder.add_quad(
        (x_max, y_max - cw, deck_h), (x_min, y_max - cw, deck_h), (x_min, y_max - cw, curb_h), (x_max, y_max - cw, curb_h),
        (0, 0), (length / 2.0, 0), (length / 2.0, curb_h - deck_h), (0, curb_h - deck_h),
        (0, -1, 0)
    )

    # 3. Waterfront Quay Wall Face (y = 0, facing +y)
    builder.set_material("Quay_Wall_Upper")
    builder.add_quad(
        (x_min, y_max, z_tidal_top), (x_max, y_max, z_tidal_top), (x_max, y_max, curb_h), (x_min, y_max, curb_h),
        (0, 0), (length / 5.0, 0), (length / 5.0, (curb_h - z_tidal_top) / 1.5), (0, (curb_h - z_tidal_top) / 1.5),
        (0, 1, 0)
    )
    builder.set_material("Quay_Wall_Tidal")
    builder.add_quad(
        (x_min, y_max, z_tidal_bot), (x_max, y_max, z_tidal_bot), (x_max, y_max, z_tidal_top), (x_min, y_max, z_tidal_top),
        (0, 0), (length / 4.0, 0), (length / 4.0, 1.0), (0, 1.0),
        (0, 1, 0)
    )
    builder.set_material("Quay_Wall_Submerged")
    builder.add_quad(
        (x_min, y_max, z_bot), (x_max, y_max, z_bot), (x_max, y_max, z_tidal_bot), (x_min, y_max, z_tidal_bot),
        (0, 0), (length / 6.0, 0), (length / 6.0, (z_tidal_bot - z_bot) / 4.0), (0, (z_tidal_bot - z_bot) / 4.0),
        (0, 1, 0)
    )

    # 4. Rear, Side, and Seabed Faces
    builder.add_quad(
        (x_max, y_min, z_bot), (x_min, y_min, z_bot), (x_min, y_min, deck_h), (x_max, y_min, deck_h),
        (0, 0), (length / 6.0, 0), (length / 6.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0),
        (0, -1, 0)
    )
    builder.add_quad(
        (x_min, y_min, z_bot), (x_min, y_max, z_bot), (x_min, y_max, curb_h), (x_min, y_min, deck_h),
        (0, 0), (width / 4.0, 0), (width / 4.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0),
        (-1, 0, 0)
    )
    builder.add_quad(
        (x_max, y_max, z_bot), (x_max, y_min, z_bot), (x_max, y_min, deck_h), (x_max, y_max, curb_h),
        (0, 0), (width / 4.0, 0), (width / 4.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0),
        (1, 0, 0)
    )
    builder.add_quad(
        (x_min, y_max, z_bot), (x_min, y_min, z_bot), (x_max, y_min, z_bot), (x_max, y_max, z_bot),
        (0, 0), (width / 4.0, 0), (length / 4.0, width / 4.0), (0, length / 4.0),
        (0, 0, -1)
    )

    # 5. Fenders
    builder.set_material("Fender_Rubber")
    fender_spacing = 11.0
    num_fenders = max(1, int(length / fender_spacing))
    fender_xs = [x_min + (i + 0.5) * (length / num_fenders) for i in range(num_fenders)]
    for fx in fender_xs:
        builder.add_arch_fender(fx, y_max, z_center=0.0, radius=0.30, length=1.2, orientation='y+')

    # 6. Bollards
    builder.set_material("Bollard_CastIron")
    bollard_spacing = 11.0
    num_bollards = max(1, int(length / bollard_spacing))
    bollard_xs = [x_min + (i + 0.5) * (length / num_bollards) for i in range(num_bollards)]
    for bx in bollard_xs:
        builder.add_bollard(bx, y_max - 0.65, z_base=deck_h)

    # 7. Ladders
    builder.set_material("Safety_Ladder")
    ladder_xs = [x_min + length * 0.25, x_min + length * 0.75]
    for lx in ladder_xs:
        builder.add_ladder(lx, y_max, z_top=deck_h, z_bottom=-1.2, orientation='y+')

    obj_path = os.path.join(meshes_dir, f"{model_name}.obj")
    builder.export(obj_path)

    write_straight_sdf(model_dir, model_name, length, width, depth, deck_h, curb_h)
    write_model_config(model_dir, model_name, f"Realistic deep harbor wall ({model_name}, depth >= 15m) with deck, fenders, bollards, and ladders.")
    print(f"Generated {model_name} successfully at {model_dir}")


def generate_l_shape_wall(output_dir, length1=55.0, length2=35.0, width=4.5, depth=16.2, deck_h=1.8, curb_h=2.0, curb_side="inner", model_name="harbor_wall_l_shape"):
    """
    Generates an L-shaped harbor wall / breakwater with a seamless continuous 90-degree corner.
    curb_side='inner':
      - Yellow/black hazard curb and berthing face on the inside of the L (enclosed harbor basin).
      - Arm 1 berthing face at y=0 facing +y, Arm 2 berthing face at x=length1-width facing -x.
    curb_side='outer':
      - Yellow/black hazard curb and berthing face on the outside of the L (outer breakwater/sea mole).
      - Arm 1 berthing face at y=-width facing -y, Arm 2 berthing face at x=length1 facing +x.
      - Corner curb wraps around the outer corner (length1, -width).
    """
    model_dir = os.path.join(output_dir, model_name)
    meshes_dir = os.path.join(model_dir, "meshes")
    tex_dir = os.path.join(meshes_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    generate_textures(tex_dir)
    mtl_name = f"{model_name}.mtl"
    write_mtl(os.path.join(meshes_dir, mtl_name))

    builder = ObjMeshBuilder(mtl_name)

    z_bot = -depth
    z_tidal_bot = -1.5
    z_tidal_top = 0.6
    cw = 0.35 # curb width

    xc = length1 - width # Inner corner X (e.g. 50.5m)
    fender_spacing = 11.0
    bollard_spacing = 11.0

    if curb_side == "inner":
        # ==========================================================
        # INNER L-SHAPED QUAY (Berthing face & curb on the inside)
        # ==========================================================
        builder.set_material("Quay_Curb")
        # Arm 1 Curb Top (along y=0, x in [0, xc])
        builder.add_quad(
            (0.0, -cw, curb_h), (xc, -cw, curb_h), (xc, 0.0, curb_h), (0.0, 0.0, curb_h),
            (0, 0), (xc / 2.0, 0), (xc / 2.0, cw), (0, cw),
            (0, 0, 1)
        )
        # Corner Curb Top: x in [xc, xc+cw], y in [-cw, 0]
        builder.add_quad(
            (xc, -cw, curb_h), (xc + cw, -cw, curb_h), (xc + cw, 0.0, curb_h), (xc, 0.0, curb_h),
            (0, 0), (cw, 0), (cw, cw), (0, cw),
            (0, 0, 1)
        )
        # Arm 2 Curb Top (along x=xc, y in [0, length2])
        builder.add_quad(
            (xc, 0.0, curb_h), (xc + cw, 0.0, curb_h), (xc + cw, length2, curb_h), (xc, length2, curb_h),
            (0, 0), (cw, 0), (cw, length2 / 2.0), (0, length2 / 2.0),
            (0, 0, 1)
        )
        # Curb Deck Steps
        builder.add_quad(
            (xc + cw, -cw, deck_h), (0.0, -cw, deck_h), (0.0, -cw, curb_h), (xc + cw, -cw, curb_h),
            (0, 0), ((xc + cw) / 2.0, 0), ((xc + cw) / 2.0, curb_h - deck_h), (0, curb_h - deck_h),
            (0, -1, 0)
        )
        builder.add_quad(
            (xc + cw, length2, deck_h), (xc + cw, -cw, deck_h), (xc + cw, -cw, curb_h), (xc + cw, length2, curb_h),
            (0, 0), ((length2 + cw) / 2.0, 0), ((length2 + cw) / 2.0, curb_h - deck_h), (0, curb_h - deck_h),
            (1, 0, 0)
        )

        # Deck
        builder.set_material("Quay_Deck")
        builder.add_quad(
            (0.0, -width, deck_h), (xc + cw, -width, deck_h), (xc + cw, -cw, deck_h), (0.0, -cw, deck_h),
            (0, 0), ((xc + cw) / 4.0, 0), ((xc + cw) / 4.0, (width - cw) / 4.0), (0, (width - cw) / 4.0),
            (0, 0, 1)
        )
        builder.add_quad(
            (xc + cw, -cw, deck_h), (length1, -cw, deck_h), (length1, length2, deck_h), (xc + cw, length2, deck_h),
            (0, 0), ((width - cw) / 4.0, 0), ((width - cw) / 4.0, (length2 + cw) / 4.0), (0, (length2 + cw) / 4.0),
            (0, 0, 1)
        )
        builder.add_quad(
            (xc + cw, -width, deck_h), (length1, -width, deck_h), (length1, -cw, deck_h), (xc + cw, -cw, deck_h),
            (0, 0), ((width - cw) / 4.0, 0), ((width - cw) / 4.0, (width - cw) / 4.0), (0, (width - cw) / 4.0),
            (0, 0, 1)
        )

        # Arm 1 Waterfront Quay Wall (y = 0, facing +y)
        builder.set_material("Quay_Wall_Upper")
        builder.add_quad((0.0, 0.0, z_tidal_top), (xc, 0.0, z_tidal_top), (xc, 0.0, curb_h), (0.0, 0.0, curb_h),
                         (0, 0), (xc / 5.0, 0), (xc / 5.0, (curb_h - z_tidal_top) / 1.5), (0, (curb_h - z_tidal_top) / 1.5), (0, 1, 0))
        builder.set_material("Quay_Wall_Tidal")
        builder.add_quad((0.0, 0.0, z_tidal_bot), (xc, 0.0, z_tidal_bot), (xc, 0.0, z_tidal_top), (0.0, 0.0, z_tidal_top),
                         (0, 0), (xc / 4.0, 0), (xc / 4.0, 1.0), (0, 1.0), (0, 1, 0))
        builder.set_material("Quay_Wall_Submerged")
        builder.add_quad((0.0, 0.0, z_bot), (xc, 0.0, z_bot), (xc, 0.0, z_tidal_bot), (0.0, 0.0, z_tidal_bot),
                         (0, 0), (xc / 6.0, 0), (xc / 6.0, (z_tidal_bot - z_bot) / 4.0), (0, (z_tidal_bot - z_bot) / 4.0), (0, 1, 0))

        # Arm 2 Waterfront Quay Wall (x = xc, facing -x)
        builder.set_material("Quay_Wall_Upper")
        builder.add_quad((xc, length2, z_tidal_top), (xc, 0.0, z_tidal_top), (xc, 0.0, curb_h), (xc, length2, curb_h),
                         (0, 0), (length2 / 5.0, 0), (length2 / 5.0, (curb_h - z_tidal_top) / 1.5), (0, (curb_h - z_tidal_top) / 1.5), (-1, 0, 0))
        builder.set_material("Quay_Wall_Tidal")
        builder.add_quad((xc, length2, z_tidal_bot), (xc, 0.0, z_tidal_bot), (xc, 0.0, z_tidal_top), (xc, length2, z_tidal_top),
                         (0, 0), (length2 / 4.0, 0), (length2 / 4.0, 1.0), (0, 1.0), (-1, 0, 0))
        builder.set_material("Quay_Wall_Submerged")
        builder.add_quad((xc, length2, z_bot), (xc, 0.0, z_bot), (xc, 0.0, z_tidal_bot), (xc, length2, z_tidal_bot),
                         (0, 0), (length2 / 6.0, 0), (length2 / 6.0, (z_tidal_bot - z_bot) / 4.0), (0, (z_tidal_bot - z_bot) / 4.0), (-1, 0, 0))

        # Outer Back Walls
        builder.add_quad((length1, -width, z_bot), (0.0, -width, z_bot), (0.0, -width, deck_h), (length1, -width, deck_h),
                         (0, 0), (length1 / 6.0, 0), (length1 / 6.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0), (0, -1, 0))
        builder.add_quad((length1, -width, z_bot), (length1, length2, z_bot), (length1, length2, deck_h), (length1, -width, deck_h),
                         (0, 0), ((length2 + width) / 6.0, 0), ((length2 + width) / 6.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0), (1, 0, 0))
        builder.add_quad((0.0, -width, z_bot), (0.0, 0.0, z_bot), (0.0, 0.0, curb_h), (0.0, -width, deck_h),
                         (0, 0), (width / 4.0, 0), (width / 4.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0), (-1, 0, 0))
        builder.add_quad((xc, length2, z_bot), (length1, length2, z_bot), (length1, length2, deck_h), (xc, length2, curb_h),
                         (0, 0), (width / 4.0, 0), (width / 4.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0), (0, 1, 0))
        builder.add_quad((0.0, 0.0, z_bot), (0.0, -width, z_bot), (xc, -width, z_bot), (xc, 0.0, z_bot),
                         (0, 0), (width / 4.0, 0), (xc / 4.0, width / 4.0), (0, xc / 4.0), (0, 0, -1))
        builder.add_quad((xc, length2, z_bot), (xc, -width, z_bot), (length1, -width, z_bot), (length1, length2, z_bot),
                         (0, 0), (width / 4.0, 0), ((length2 + width) / 4.0, width / 4.0), (0, (length2 + width) / 4.0), (0, 0, -1))

        # Equipment
        builder.set_material("Fender_Rubber")
        num_f1 = max(1, int((xc - 4.0) / fender_spacing))
        for i in range(num_f1):
            builder.add_arch_fender(5.0 + i * fender_spacing, 0.0, z_center=0.0, radius=0.30, length=1.2, orientation='y+')
        num_f2 = max(1, int((length2 - 4.0) / fender_spacing))
        for i in range(num_f2):
            builder.add_arch_fender(xc, 5.0 + i * fender_spacing, z_center=0.0, radius=0.30, length=1.2, orientation='x-')

        builder.set_material("Bollard_CastIron")
        num_b1 = max(1, int((xc - 4.0) / bollard_spacing))
        for i in range(num_b1):
            builder.add_bollard(5.0 + i * bollard_spacing, -0.65, z_base=deck_h)
        num_b2 = max(1, int((length2 - 4.0) / bollard_spacing))
        for i in range(num_b2):
            builder.add_bollard(xc + 0.65, 5.0 + i * bollard_spacing, z_base=deck_h)

        builder.set_material("Safety_Ladder")
        builder.add_ladder(xc * 0.45, 0.0, z_top=deck_h, z_bottom=-1.2, orientation='y+')
        builder.add_ladder(xc, length2 * 0.5, z_top=deck_h, z_bottom=-1.2, orientation='x-')

    else:
        # ==========================================================
        # OUTER (REVERTED / MIRRORED) L-SHAPED QUAY
        # Berthing face & yellow/black curb along the outer perimeter:
        # Arm 1 outer face at y=-width, Arm 2 outer face at x=length1,
        # wrapping around the outer corner (length1, -width).
        # ==========================================================
        builder.set_material("Quay_Curb")

        # Arm 1 Outer Curb Top (along y = -width, x in [0, length1 - cw])
        builder.add_quad(
            (0.0, -width, curb_h), (length1 - cw, -width, curb_h), (length1 - cw, -width + cw, curb_h), (0.0, -width + cw, curb_h),
            (0, 0), ((length1 - cw) / 2.0, 0), ((length1 - cw) / 2.0, cw), (0, cw),
            (0, 0, 1)
        )
        # Outer Corner Curb Top (at (length1, -width): x in [length1 - cw, length1], y in [-width, -width + cw])
        builder.add_quad(
            (length1 - cw, -width, curb_h), (length1, -width, curb_h), (length1, -width + cw, curb_h), (length1 - cw, -width + cw, curb_h),
            (0, 0), (cw, 0), (cw, cw), (0, cw),
            (0, 0, 1)
        )
        # Arm 2 Outer Curb Top (along x = length1, y in [-width + cw, length2])
        builder.add_quad(
            (length1 - cw, -width + cw, curb_h), (length1, -width + cw, curb_h), (length1, length2, curb_h), (length1 - cw, length2, curb_h),
            (0, 0), (cw, 0), (cw, (length2 + width - cw) / 2.0), (0, (length2 + width - cw) / 2.0),
            (0, 0, 1)
        )
        # Curb Deck Steps
        builder.add_quad(
            (0.0, -width + cw, deck_h), (length1 - cw, -width + cw, deck_h), (length1 - cw, -width + cw, curb_h), (0.0, -width + cw, curb_h),
            (0, 0), ((length1 - cw) / 2.0, 0), ((length1 - cw) / 2.0, curb_h - deck_h), (0, curb_h - deck_h),
            (0, 1, 0)
        )
        builder.add_quad(
            (length1 - cw, -width + cw, deck_h), (length1 - cw, length2, deck_h), (length1 - cw, length2, curb_h), (length1 - cw, -width + cw, curb_h),
            (0, 0), ((length2 + width - cw) / 2.0, 0), ((length2 + width - cw) / 2.0, curb_h - deck_h), (0, curb_h - deck_h),
            (-1, 0, 0)
        )

        # Deck
        builder.set_material("Quay_Deck")
        builder.add_quad(
            (0.0, -width + cw, deck_h), (xc, -width + cw, deck_h), (xc, 0.0, deck_h), (0.0, 0.0, deck_h),
            (0, 0), (xc / 4.0, 0), (xc / 4.0, (width - cw) / 4.0), (0, (width - cw) / 4.0),
            (0, 0, 1)
        )
        builder.add_quad(
            (xc, 0.0, deck_h), (length1 - cw, 0.0, deck_h), (length1 - cw, length2, deck_h), (xc, length2, deck_h),
            (0, 0), ((width - cw) / 4.0, 0), ((width - cw) / 4.0, length2 / 4.0), (0, length2 / 4.0),
            (0, 0, 1)
        )
        builder.add_quad(
            (xc, -width + cw, deck_h), (length1 - cw, -width + cw, deck_h), (length1 - cw, 0.0, deck_h), (xc, 0.0, deck_h),
            (0, 0), ((width - cw) / 4.0, 0), ((width - cw) / 4.0, (width - cw) / 4.0), (0, (width - cw) / 4.0),
            (0, 0, 1)
        )

        # Arm 1 Outer Waterfront Quay Wall (y = -width, facing -y)
        builder.set_material("Quay_Wall_Upper")
        builder.add_quad((length1, -width, z_tidal_top), (0.0, -width, z_tidal_top), (0.0, -width, curb_h), (length1, -width, curb_h),
                         (0, 0), (length1 / 5.0, 0), (length1 / 5.0, (curb_h - z_tidal_top) / 1.5), (0, (curb_h - z_tidal_top) / 1.5), (0, -1, 0))
        builder.set_material("Quay_Wall_Tidal")
        builder.add_quad((length1, -width, z_tidal_bot), (0.0, -width, z_tidal_bot), (0.0, -width, z_tidal_top), (length1, -width, z_tidal_top),
                         (0, 0), (length1 / 4.0, 0), (length1 / 4.0, 1.0), (0, 1.0), (0, -1, 0))
        builder.set_material("Quay_Wall_Submerged")
        builder.add_quad((length1, -width, z_bot), (0.0, -width, z_bot), (0.0, -width, z_tidal_bot), (length1, -width, z_tidal_bot),
                         (0, 0), (length1 / 6.0, 0), (length1 / 6.0, (z_tidal_bot - z_bot) / 4.0), (0, (z_tidal_bot - z_bot) / 4.0), (0, -1, 0))

        # Arm 2 Outer Waterfront Quay Wall (x = length1, facing +x)
        builder.set_material("Quay_Wall_Upper")
        builder.add_quad((length1, -width, z_tidal_top), (length1, length2, z_tidal_top), (length1, length2, curb_h), (length1, -width, curb_h),
                         (0, 0), ((length2 + width) / 5.0, 0), ((length2 + width) / 5.0, (curb_h - z_tidal_top) / 1.5), (0, (curb_h - z_tidal_top) / 1.5), (1, 0, 0))
        builder.set_material("Quay_Wall_Tidal")
        builder.add_quad((length1, -width, z_tidal_bot), (length1, length2, z_tidal_bot), (length1, length2, z_tidal_top), (length1, -width, z_tidal_top),
                         (0, 0), ((length2 + width) / 4.0, 0), ((length2 + width) / 4.0, 1.0), (0, 1.0), (1, 0, 0))
        builder.set_material("Quay_Wall_Submerged")
        builder.add_quad((length1, -width, z_bot), (length1, length2, z_bot), (length1, length2, z_tidal_bot), (length1, -width, z_tidal_bot),
                         (0, 0), ((length2 + width) / 6.0, 0), ((length2 + width) / 6.0, (z_tidal_bot - z_bot) / 4.0), (0, (z_tidal_bot - z_bot) / 4.0), (1, 0, 0))

        # Inner Back Walls (facing +y on Arm 1, facing -x on Arm 2)
        builder.add_quad((0.0, 0.0, z_bot), (xc, 0.0, z_bot), (xc, 0.0, deck_h), (0.0, 0.0, deck_h),
                         (0, 0), (xc / 6.0, 0), (xc / 6.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0), (0, 1, 0))
        builder.add_quad((xc, length2, z_bot), (xc, 0.0, z_bot), (xc, 0.0, deck_h), (xc, length2, deck_h),
                         (0, 0), (length2 / 6.0, 0), (length2 / 6.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0), (-1, 0, 0))

        # End Caps & Seabed Bottom
        builder.add_quad((0.0, -width, z_bot), (0.0, 0.0, z_bot), (0.0, 0.0, deck_h), (0.0, -width, curb_h),
                         (0, 0), (width / 4.0, 0), (width / 4.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0), (-1, 0, 0))
        builder.add_quad((xc, length2, z_bot), (length1, length2, z_bot), (length1, length2, curb_h), (xc, length2, deck_h),
                         (0, 0), (width / 4.0, 0), (width / 4.0, (deck_h - z_bot) / 4.0), (0, (deck_h - z_bot) / 4.0), (0, 1, 0))
        builder.add_quad((0.0, 0.0, z_bot), (0.0, -width, z_bot), (xc, -width, z_bot), (xc, 0.0, z_bot),
                         (0, 0), (width / 4.0, 0), (xc / 4.0, width / 4.0), (0, xc / 4.0), (0, 0, -1))
        builder.add_quad((xc, length2, z_bot), (xc, -width, z_bot), (length1, -width, z_bot), (length1, length2, z_bot),
                         (0, 0), (width / 4.0, 0), ((length2 + width) / 4.0, width / 4.0), (0, (length2 + width) / 4.0), (0, 0, -1))

        # Outer Equipment: Fenders, Bollards, Ladders
        builder.set_material("Fender_Rubber")
        num_f1 = max(1, int((length1 - 4.0) / fender_spacing))
        for i in range(num_f1):
            builder.add_arch_fender(5.0 + i * fender_spacing, -width, z_center=0.0, radius=0.30, length=1.2, orientation='y-')
        num_f2 = max(1, int((length2 + width - 4.0) / fender_spacing))
        for i in range(num_f2):
            builder.add_arch_fender(length1, -width + 5.0 + i * fender_spacing, z_center=0.0, radius=0.30, length=1.2, orientation='x+')

        builder.set_material("Bollard_CastIron")
        num_b1 = max(1, int((length1 - 4.0) / bollard_spacing))
        for i in range(num_b1):
            builder.add_bollard(5.0 + i * bollard_spacing, -width + 0.65, z_base=deck_h)
        num_b2 = max(1, int((length2 + width - 4.0) / bollard_spacing))
        for i in range(num_b2):
            builder.add_bollard(length1 - 0.65, -width + 5.0 + i * bollard_spacing, z_base=deck_h)

        builder.set_material("Safety_Ladder")
        builder.add_ladder(length1 * 0.45, -width, z_top=deck_h, z_bottom=-1.2, orientation='y-')
        builder.add_ladder(length1, length2 * 0.5, z_top=deck_h, z_bottom=-1.2, orientation='x+')

    obj_path = os.path.join(meshes_dir, f"{model_name}.obj")
    builder.export(obj_path)

    write_l_shape_sdf(model_dir, model_name, length1, length2, width, depth, deck_h, curb_h)
    desc_side = "outer/mirrored" if curb_side == "outer" else "inner"
    write_model_config(model_dir, model_name, f"Realistic deep harbor wall ({model_name}, {desc_side} curb version, depth >= 15m) with perpendicular quay arms, continuous curb, fenders, bollards, and ladders.")
    print(f"Generated {model_name} successfully at {model_dir}")


def write_straight_sdf(model_dir, model_name, length, width, depth, deck_h, curb_h):
    sdf_path = os.path.join(model_dir, "model.sdf")
    total_height = depth + curb_h
    center_z = (curb_h - depth) / 2.0
    center_y = -width / 2.0

    sdf_content = f"""<?xml version="1.0" ?>
<sdf version="1.9">
  <model name="{model_name}">
    <static>true</static>
    <link name="quay_link">
      <!-- Main Analytical Collision Box (Guarantees zero physics glitches and sharp Ping2 GPU LiDAR returns) -->
      <collision name="quay_collision">
        <pose>0.0 {center_y:.4f} {center_z:.4f} 0 0 0</pose>
        <geometry>
          <box>
            <size>{length:.4f} {width:.4f} {total_height:.4f}</size>
          </box>
        </geometry>
        <surface>
          <friction>
            <ode>
              <mu>0.9</mu>
              <mu2>0.9</mu2>
            </ode>
          </friction>
          <contact>
            <ode>
              <kp>10000000.0</kp>
              <kd>1.0</kd>
            </ode>
          </contact>
        </surface>
      </collision>

      <!-- High-Fidelity Photorealistic Visual Mesh -->
      <visual name="quay_visual">
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
    with open(sdf_path, "w") as f:
        f.write(sdf_content)


def write_l_shape_sdf(model_dir, model_name, length1, length2, width, depth, deck_h, curb_h):
    sdf_path = os.path.join(model_dir, "model.sdf")
    total_height = depth + curb_h
    center_z = (curb_h - depth) / 2.0

    xc = length1 - width
    # Arm 1: x in [0, xc], y in [-width, 0]
    arm1_len = xc
    arm1_cx = arm1_len / 2.0
    arm1_cy = -width / 2.0

    # Arm 2: x in [xc, length1], y in [-width, length2]
    arm2_len_y = length2 + width
    arm2_cx = xc + width / 2.0
    arm2_cy = (length2 - width) / 2.0

    sdf_content = f"""<?xml version="1.0" ?>
<sdf version="1.9">
  <model name="{model_name}">
    <static>true</static>
    <link name="quay_link">
      <!-- Arm 1 Collision (Along X) -->
      <collision name="arm1_collision">
        <pose>{arm1_cx:.4f} {arm1_cy:.4f} {center_z:.4f} 0 0 0</pose>
        <geometry>
          <box>
            <size>{arm1_len:.4f} {width:.4f} {total_height:.4f}</size>
          </box>
        </geometry>
        <surface>
          <friction>
            <ode>
              <mu>0.9</mu>
              <mu2>0.9</mu2>
            </ode>
          </friction>
        </surface>
      </collision>

      <!-- Arm 2 Collision (Along Y) -->
      <collision name="arm2_collision">
        <pose>{arm2_cx:.4f} {arm2_cy:.4f} {center_z:.4f} 0 0 0</pose>
        <geometry>
          <box>
            <size>{width:.4f} {arm2_len_y:.4f} {total_height:.4f}</size>
          </box>
        </geometry>
        <surface>
          <friction>
            <ode>
              <mu>0.9</mu>
              <mu2>0.9</mu2>
            </ode>
          </friction>
        </surface>
      </collision>

      <!-- High-Fidelity Photorealistic Visual Mesh -->
      <visual name="quay_visual">
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
    with open(sdf_path, "w") as f:
        f.write(sdf_content)


def write_model_config(model_dir, model_name, description):
    config_path = os.path.join(model_dir, "model.config")
    config_content = f"""<?xml version="1.0"?>
<model>
  <name>{model_name}</name>
  <version>1.0</version>
  <sdf version="1.9">model.sdf</sdf>
  <author>
    <name>Ocean Regatta Organizers</name>
    <email>organizers@ocean-regatta.org</email>
  </author>
  <description>
    {description}
  </description>
</model>
"""
    with open(config_path, "w") as f:
        f.write(config_content)


def main():
    parser = argparse.ArgumentParser(description="Generate realistic harbor wall models for Gazebo Sim.")
    parser.add_argument("--type", choices=["straight", "l_shape", "l_shape_outer", "corner", "all"], default="all",
                        help="Type of model to generate: straight, l_shape, l_shape_outer, corner, or all (default: all)")
    parser.add_argument("--curb-side", choices=["inner", "outer"], default="inner",
                        help="Side for the yellow safety curb on L-shaped walls: 'inner' (basin) or 'outer' (breakwater) (default: inner)")
    parser.add_argument("--output-dir", default="models", help="Output directory (default: models)")
    parser.add_argument("--depth", type=float, default=16.2, help="Depth below waterline in meters (default: 16.2, must be >= 15.0)")
    parser.add_argument("--width", type=float, default=4.5, help="Width of the quay deck in meters (default: 4.5)")
    parser.add_argument("--length", type=float, default=55.0, help="Main arm length in meters (default: 55.0)")
    parser.add_argument("--length2", type=float, default=35.0, help="Return arm length for L-shape in meters (default: 35.0)")
    parser.add_argument("--deck-height", type=float, default=1.8, help="Deck height above waterline (default: 1.8)")
    parser.add_argument("--name", default=None, help="Custom model name (optional)")

    args = parser.parse_args()

    if args.depth < 15.0:
        print(f"Warning: Depth {args.depth}m is less than recommended 15.0m. Using requested value.")

    os.makedirs(args.output_dir, exist_ok=True)

    if args.type in ("straight", "all"):
        name = args.name if (args.name and args.type == "straight") else "harbor_wall_straight"
        generate_straight_wall(args.output_dir, length=args.length, width=args.width,
                               depth=args.depth, deck_h=args.deck_height, model_name=name)

    if args.type in ("l_shape", "all"):
        name = args.name if (args.name and args.type == "l_shape") else "harbor_wall_l_shape"
        curb_side = args.curb_side if args.type == "l_shape" else "inner"
        generate_l_shape_wall(args.output_dir, length1=args.length, length2=args.length2,
                              width=args.width, depth=args.depth, deck_h=args.deck_height,
                              curb_side=curb_side, model_name=name)

    if args.type in ("l_shape_outer", "all"):
        name = args.name if (args.name and args.type == "l_shape_outer") else "harbor_wall_l_shape_outer"
        generate_l_shape_wall(args.output_dir, length1=args.length, length2=args.length2,
                              width=args.width, depth=args.depth, deck_h=args.deck_height,
                              curb_side="outer", model_name=name)

    if args.type in ("corner", "all"):
        name = args.name if (args.name and args.type == "corner") else "harbor_wall_corner"
        generate_l_shape_wall(args.output_dir, length1=12.0, length2=12.0,
                              width=args.width, depth=args.depth, deck_h=args.deck_height,
                              curb_side="inner", model_name=name)

    print("\nGeneration complete!")

if __name__ == "__main__":
    main()
