from __future__ import annotations

import re


def _cable_clip_script(output: Path, parameters: dict[str, float | str]) -> str:
    inner_diameter = float(parameters.get("inner_diameter_mm") or 4.8)
    wall = float(parameters.get("wall_mm") or 1.4)
    depth = float(parameters.get("depth_mm") or 10.0)
    gap = float(parameters.get("gap_degrees") or 70.0)
    return f"""
import math
from pathlib import Path

import bmesh
import bpy

OUT = Path({str(output)!r})
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

inner_radius = {inner_diameter / 2!r}
wall = {wall!r}
outer_radius = inner_radius + wall
depth = {depth!r}
gap_degrees = {gap!r}
segments = 40
start = math.radians(gap_degrees / 2)
end = math.radians(360 - gap_degrees / 2)

bm = bmesh.new()

def arc(radius, z):
    verts = []
    for i in range(segments):
        angle = start + (end - start) * i / (segments - 1)
        verts.append(bm.verts.new((radius * math.cos(angle), radius * math.sin(angle), z)))
    return verts

bo = arc(outer_radius, 0)
bi = arc(inner_radius, 0)
to = arc(outer_radius, depth)
ti = arc(inner_radius, depth)

for i in range(segments - 1):
    bm.faces.new([bo[i], bo[i + 1], bi[i + 1], bi[i]])
    bm.faces.new([to[i], ti[i], ti[i + 1], to[i + 1]])
    bm.faces.new([bo[i], to[i], to[i + 1], bo[i + 1]])
    bm.faces.new([bi[i + 1], ti[i + 1], ti[i], bi[i]])
bm.faces.new([bo[0], bi[0], ti[0], to[0]])
bm.faces.new([bi[-1], bo[-1], to[-1], ti[-1]])
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

mesh = bpy.data.meshes.new('DeskCableClipMesh')
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new('desk_cable_clip_4_8mm_channel', mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.shade_smooth()

bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 0.001
bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'

bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'desk_cable_clip.blend'))
if hasattr(bpy.ops.wm, 'stl_export'):
    bpy.ops.wm.stl_export(filepath=str(OUT / 'desk_cable_clip.stl'), export_selected_objects=True)
else:
    bpy.ops.export_mesh.stl(filepath=str(OUT / 'desk_cable_clip.stl'), use_selection=True)
"""


def _phone_stand_script(output: Path, parameters: dict[str, float | str]) -> str:
    base_width = float(parameters.get("base_width_mm") or 90.0)
    base_depth = float(parameters.get("base_depth_mm") or 70.0)
    angle = float(parameters.get("back_angle_degrees") or 12.0)
    return f"""
import math
from pathlib import Path

import bpy

OUT = Path({str(output)!r})
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

def cube(name, location, dimensions, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj

cube('phone_stand_base', (0, 0, 2), ({base_width!r}, {base_depth!r}, 4))
cube('phone_stand_back', (0, 22, 28), ({base_width!r}, 5, 55), (math.radians(-{angle!r}), 0, 0))
cube('phone_lip', (0, -28, 8), ({base_width!r}, 8, 10))

bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 0.001
bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'

bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'phone_stand.blend'))
if hasattr(bpy.ops.wm, 'stl_export'):
    bpy.ops.wm.stl_export(filepath=str(OUT / 'phone_stand.stl'))
else:
    bpy.ops.export_mesh.stl(filepath=str(OUT / 'phone_stand.stl'))
"""


def _label_tag_script(output: Path, parameters: dict[str, float | str]) -> str:
    width = float(parameters.get("width_mm") or 60.0)
    height = float(parameters.get("height_mm") or 24.0)
    thickness = float(parameters.get("thickness_mm") or 3.0)
    hole = float(parameters.get("hole_mm") or 5.0)
    return f"""
from pathlib import Path

import bpy

OUT = Path({str(output)!r})
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, {thickness / 2!r}))
tag = bpy.context.object
tag.name = 'label_tag_body'
tag.dimensions = ({width!r}, {height!r}, {thickness!r})
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius={hole / 2!r}, depth={thickness + 2!r}, location=({-width / 2 + 8!r}, 0, {thickness / 2!r}))
hole_obj = bpy.context.object
hole_obj.name = 'label_tag_keyring_hole_cut'
modifier = tag.modifiers.new('keyring_hole', 'BOOLEAN')
modifier.operation = 'DIFFERENCE'
modifier.object = hole_obj
bpy.context.view_layer.objects.active = tag
bpy.ops.object.modifier_apply(modifier=modifier.name)
bpy.data.objects.remove(hole_obj, do_unlink=True)

bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 0.001
bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'

tag.select_set(True)
bpy.context.view_layer.objects.active = tag
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'label_tag.blend'))
if hasattr(bpy.ops.wm, 'stl_export'):
    bpy.ops.wm.stl_export(filepath=str(OUT / 'label_tag.stl'), export_selected_objects=True)
else:
    bpy.ops.export_mesh.stl(filepath=str(OUT / 'label_tag.stl'), use_selection=True)
"""


def _wall_hook_script(output: Path, parameters: dict[str, float | str]) -> str:
    plate_width = float(parameters.get("plate_width_mm") or 35.0)
    plate_height = float(parameters.get("plate_height_mm") or 55.0)
    hook_depth = float(parameters.get("hook_depth_mm") or 28.0)
    thickness = float(parameters.get("thickness_mm") or 5.0)
    return f"""
from pathlib import Path

import bpy

OUT = Path({str(output)!r})
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

def cube(name, location, dimensions):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj

cube('wall_hook_mounting_plate', (0, 0, {thickness / 2!r}), ({plate_width!r}, {thickness!r}, {plate_height!r}))
cube('wall_hook_arm', (0, {-hook_depth / 2!r}, {plate_height * 0.42!r}), ({plate_width * 0.55!r}, {hook_depth!r}, {thickness!r}))
cube('wall_hook_lip', (0, {-hook_depth!r}, {plate_height * 0.5!r}), ({plate_width * 0.55!r}, {thickness!r}, {thickness * 2!r}))

bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 0.001
bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'

bpy.ops.object.select_all(action='SELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'wall_hook.blend'))
if hasattr(bpy.ops.wm, 'stl_export'):
    bpy.ops.wm.stl_export(filepath=str(OUT / 'wall_hook.stl'), export_selected_objects=True)
else:
    bpy.ops.export_mesh.stl(filepath=str(OUT / 'wall_hook.stl'), use_selection=True)
"""


def _organizer_tray_script(output: Path, parameters: dict[str, float | str]) -> str:
    width = float(parameters.get("width_mm") or 100.0)
    depth = float(parameters.get("depth_mm") or 70.0)
    height = float(parameters.get("height_mm") or 18.0)
    wall = float(parameters.get("wall_mm") or 2.0)
    return f"""
from pathlib import Path

import bpy

OUT = Path({str(output)!r})
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

def cube(name, location, dimensions):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj

cube('organizer_tray_floor', (0, 0, {wall / 2!r}), ({width!r}, {depth!r}, {wall!r}))
cube('organizer_tray_back_wall', (0, {depth / 2 - wall / 2!r}, {height / 2!r}), ({width!r}, {wall!r}, {height!r}))
cube('organizer_tray_front_wall', (0, {-depth / 2 + wall / 2!r}, {height / 2!r}), ({width!r}, {wall!r}, {height!r}))
cube('organizer_tray_left_wall', ({-width / 2 + wall / 2!r}, 0, {height / 2!r}), ({wall!r}, {depth!r}, {height!r}))
cube('organizer_tray_right_wall', ({width / 2 - wall / 2!r}, 0, {height / 2!r}), ({wall!r}, {depth!r}, {height!r}))

bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 0.001
bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'

bpy.ops.object.select_all(action='SELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'organizer_tray.blend'))
if hasattr(bpy.ops.wm, 'stl_export'):
    bpy.ops.wm.stl_export(filepath=str(OUT / 'organizer_tray.stl'), export_selected_objects=True)
else:
    bpy.ops.export_mesh.stl(filepath=str(OUT / 'organizer_tray.stl'), use_selection=True)
"""


def _number_before(text: str, markers: tuple[str, ...]) -> float | None:
    for marker in markers:
        match = re.search(rf"(\d+(?:\.\d+)?)\s*{re.escape(marker)}", text)
        if match:
            return float(match.group(1))
    return None


def _number_after(text: str, markers: tuple[str, ...]) -> float | None:
    for marker in markers:
        match = re.search(rf"{re.escape(marker)}\D{{0,12}}(\d+(?:\.\d+)?)\s*mm", text)
        if match:
            return float(match.group(1))
    return None
