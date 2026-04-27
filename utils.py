"""Shared utility helpers for the My Simp addon."""

import json
import re

from mathutils import Quaternion, Vector


def get_active_armature(context):
    """Return the most relevant armature for the current context.

    Tries: the active object, the active object's data (armature), selected
    objects, the WP-active mesh's armature modifier, and finally any armature
    in the scene. Returns None if nothing usable found.
    """
    obj = context.active_object
    if obj and obj.type == 'ARMATURE':
        return obj
    if obj and hasattr(obj, 'data') and hasattr(obj.data, 'bones'):
        return obj
    for o in context.selected_objects:
        if o.type == 'ARMATURE':
            return o
    if context.mode == 'PAINT_WEIGHT':
        obj = context.active_object
        if obj and obj.type == 'MESH':
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    return mod.object
    for o in context.scene.objects:
        if o.type == 'ARMATURE':
            return o
    return None


def find_armature_for_object(context):
    """Find an armature relative to a mesh or armature active object.

    Used by operators that work on bone visibility / pose: prefers the active
    armature, then a mesh's armature modifier, then the mesh's parent, then
    any armature in the scene.
    """
    obj = context.active_object
    if obj and obj.type == 'ARMATURE':
        return obj
    if obj and obj.type == 'MESH':
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                return mod.object
        if obj.parent and obj.parent.type == 'ARMATURE':
            return obj.parent
    for scene_obj in context.scene.objects:
        if scene_obj.type == 'ARMATURE':
            return scene_obj
    return None


def is_rigify_or_autopro_rig(armature):
    """Heuristic check for a Rigify or Auto-Rig Pro rig."""
    if not armature or armature.type != 'ARMATURE':
        return False
    rigify_patterns = ['DEF-', 'MCH-', 'ORG-', 'spine', 'spine.001', 'spine.002']
    autopro_patterns = ['Root', 'Hips', 'Spine', 'Chest', 'Neck', 'Head']
    bone_names = [bone.name for bone in armature.data.bones]
    rigify_count = sum(1 for pattern in rigify_patterns if any(pattern in name for name in bone_names))
    if rigify_count >= 3:
        return True
    autopro_count = sum(1 for pattern in autopro_patterns if pattern in bone_names)
    if autopro_count >= 4:
        return True
    return False


def get_unique_pose_name(base_name, pose_collection):
    """Generate a unique name like 'Foo.001' if base_name already exists in the collection."""
    existing_names = [pose.name for pose in pose_collection]
    if base_name not in existing_names:
        return base_name

    match = re.match(r"(.+)\.(\d{3})$", base_name)
    if match:
        base = match.group(1)
        num = int(match.group(2))
    else:
        base = base_name
        num = 0

    while True:
        num += 1
        new_name = f"{base}.{num:03d}"
        if new_name not in existing_names:
            return new_name


# ===== Pose data serialisation =====

def save_current_pose(armature):
    """Serialise the armature's current pose into a dict."""
    if not armature or armature.type != 'ARMATURE':
        return None
    pose_data = {}
    for bone in armature.pose.bones:
        bone_data = {
            'location': list(bone.location),
            'scale': list(bone.scale),
            'rotation_mode': bone.rotation_mode,
        }
        if bone.rotation_mode == 'QUATERNION':
            bone_data['rotation_quaternion'] = list(bone.rotation_quaternion)
        else:
            bone_data['rotation_euler'] = list(bone.rotation_euler)
        pose_data[bone.name] = bone_data
    return pose_data


def load_pose_data_from_json(json_string):
    if not json_string:
        return None
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        return None


def save_pose_data_to_json(pose_data):
    if not pose_data:
        return ""
    try:
        return json.dumps(pose_data)
    except Exception:
        return ""


def apply_pose(armature, pose_data, factor=1.0):
    """Blend a stored pose onto the armature, lerped from rest by `factor`."""
    if not armature or not pose_data:
        return
    for bone_name, bone_data in pose_data.items():
        if bone_name not in armature.pose.bones:
            continue
        bone = armature.pose.bones[bone_name]
        target_loc = Vector(bone_data['location'])
        rest_loc = Vector((0, 0, 0))
        bone.location = rest_loc.lerp(target_loc, factor)

        if bone_data['rotation_mode'] == 'QUATERNION' and 'rotation_quaternion' in bone_data:
            target_rot = Quaternion(bone_data['rotation_quaternion'])
            rest_rot = Quaternion((1, 0, 0, 0))
            bone.rotation_quaternion = rest_rot.slerp(target_rot, factor)
        elif 'rotation_euler' in bone_data:
            target_rot = bone_data['rotation_euler']
            rest_euler = [0, 0, 0]
            for i in range(3):
                bone.rotation_euler[i] = rest_euler[i] * (1 - factor) + target_rot[i] * factor

        target_scale = Vector(bone_data['scale'])
        rest_scale = Vector((1, 1, 1))
        bone.scale = rest_scale.lerp(target_scale, factor)


def update_pose_blend(self, context):
    """Property update callback for pose slider — re-applies blended pose.

    Do NOT call context.view_layer.update() here: this runs inside a property
    update callback (during depsgraph evaluation), and forcing another update
    causes re-entrant evaluation crashes. Blender will redraw next frame.
    """
    if not context.scene.pose_collection:
        return
    selected_index = int(self.selected_pose) if self.selected_pose else 0
    if selected_index >= len(context.scene.pose_collection):
        return
    armature_obj = get_active_armature(context)
    if not armature_obj:
        return
    pose_data_str = context.scene.pose_collection[selected_index].pose_data
    pose_data = load_pose_data_from_json(pose_data_str)
    if pose_data:
        apply_pose(armature_obj, pose_data, self.pose_factor)
