# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

bl_info = {
    "name": "My Simp",
    "author": "Korn Sensei",
    "description": "Streamlined weight painting tools for character rigging",
    "blender": (3, 0, 0),
    "version": (2, 8, 2),
    "location": "3D Viewport > Sidebar > Weight Paint",
    "warning": "",
    "doc_url": "",
    "tracker_url": "",
    "category": "Rigging",
}

import bpy

from . import (
    keymaps,
    ops_paint,
    ops_pose_slider,
    ops_rig,
    ops_symmetry,
    panels,
    preferences,
    properties,
)


# Aggregate every registerable class. Order matters for two reasons:
#   1. PropertyGroups must register before any PointerProperty(type=...) set below
#      uses them. We register PropertyGroups first via `properties.classes`.
#   2. AddonPreferences must register before keymap registration reads its values.
classes = (
    *properties.classes,
    *preferences.classes,
    *ops_paint.classes,
    *ops_rig.classes,
    *ops_symmetry.classes,
    *ops_pose_slider.classes,
    *panels.classes,
)


def register():
    panels.load_tab_icons()

    for cls in classes:
        bpy.utils.register_class(cls)

    # Scene-level properties
    bpy.types.Scene.pose_slider_props = bpy.props.PointerProperty(type=properties.PoseSliderProperties)
    bpy.types.Scene.pose_collection = bpy.props.CollectionProperty(type=properties.PoseData)
    bpy.types.Scene.bone_collection_props = bpy.props.PointerProperty(type=properties.BoneCollectionProperties)
    bpy.types.Scene.bone_collection_presets = bpy.props.CollectionProperty(type=properties.BoneCollectionPreset)
    bpy.types.Scene.wpt_smooth = bpy.props.PointerProperty(type=properties.WPT_SmoothSettings)

    # WindowManager-level (per-session, not saved with file)
    bpy.types.WindowManager.wpt_auto_follow_active_mesh = bpy.props.BoolProperty(
        name="Auto-Follow Active Mesh",
        description="Automatically re-enter Weight Paint with armature setup when the active mesh changes",
        default=False,
    )
    bpy.types.WindowManager.wpt_active_tab = bpy.props.EnumProperty(
        name="Active Tab",
        description="Currently selected tab in the My Simp panel",
        items=panels.make_active_tab_items(),
        default='PAINT',
    )

    # Keymaps + auto-follow infrastructure
    keymaps.register_keymaps()
    keymaps.register_msgbus()
    if keymaps.load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(keymaps.load_post_handler)


def unregister():
    if keymaps.load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(keymaps.load_post_handler)
    keymaps.unregister_msgbus()
    keymaps.unregister_keymaps()

    panels.free_tab_icons()

    # Scene properties
    for attr in ('pose_slider_props', 'pose_collection',
                 'bone_collection_props', 'bone_collection_presets',
                 'wpt_smooth'):
        try:
            delattr(bpy.types.Scene, attr)
        except AttributeError:
            pass

    # WindowManager properties
    for attr in ('wpt_auto_follow_active_mesh', 'wpt_active_tab'):
        try:
            delattr(bpy.types.WindowManager, attr)
        except AttributeError:
            pass

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
