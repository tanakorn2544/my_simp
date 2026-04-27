"""Rig / bone visibility / pose-mirror operators for My Simp."""

import json

import bpy
from bpy.props import StringProperty

from . import utils


class WPT_OT_ToggleDeformBones(bpy.types.Operator):
    """Show only deform bones (DEF/Deform collections, with name fallback)"""
    bl_idname = "wpt.toggle_deform_bones"
    bl_label = "Deform Bones Only"
    bl_description = "Show only deform bones (DEF/deform) in the active armature"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        armature_obj = utils.find_armature_for_object(context)
        if not armature_obj:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}

        arm = armature_obj.data
        collections = getattr(arm, "collections_all", None)
        if collections:
            for col in collections:
                col.is_visible = False
            deform_collections = ["DEF", "Deform", "deform"]
            found_any = False
            for col_name in deform_collections:
                if col_name in collections:
                    collections[col_name].is_visible = True
                    found_any = True
            if not found_any:
                self.report({'INFO'}, "No deform bone collections found")
        else:
            deform_keywords = ["DEF", "deform", "Deform"]
            for bone in arm.bones:
                bone.hide = not any(keyword in bone.name for keyword in deform_keywords)
        return {'FINISHED'}


class WPT_OT_ShowAllBones(bpy.types.Operator):
    """Show controller and deform bone collections"""
    bl_idname = "wpt.show_all_bones"
    bl_label = "Show Controller Bones"
    bl_description = "Show controller and deform bone collections (Main, DEF, Deform)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        armature_obj = utils.find_armature_for_object(context)
        if not armature_obj:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}

        arm = armature_obj.data
        collections = getattr(arm, "collections_all", None)
        if collections:
            for col in collections:
                col.is_visible = False
            found_collections = []
            for col in collections:
                col_name = col.name
                is_controller = (
                    "IK" in col_name or
                    "FK" in col_name or
                    "Tweak" in col_name or
                    col_name in {"Root", "Torso", "Fingers", "Face", "Extra"} or
                    ("." in col_name and not col_name.startswith(("MCH", "ORG"))) or
                    col_name in {"Main", "Secondary"}
                )
                is_deform = col_name == "DEF" or "DEF" in col_name
                if is_controller or is_deform:
                    col.is_visible = True
                    found_collections.append(col_name)
            if found_collections:
                self.report({'INFO'},
                            f"Showing collections: {', '.join(found_collections[:5])}"
                            f"{'...' if len(found_collections) > 5 else ''}")
            else:
                for col in collections:
                    col.is_visible = True
                self.report({'INFO'}, "No recognized rig collections found, showing all")
        else:
            controller_keywords = ["IK", "FK", "ctrl", "control", "CON", "DEF", "deform", "Deform"]
            shown_count = 0
            for bone in arm.bones:
                show_bone = any(keyword in bone.name for keyword in controller_keywords)
                bone.hide = not show_bone
                if show_bone:
                    shown_count += 1
            self.report({'INFO'}, f"Showing {shown_count} controller/deform bones")
        return {'FINISHED'}


class WPT_OT_ApplyRestPose(bpy.types.Operator):
    """Apply current pose as the rest pose"""
    bl_idname = "wpt.apply_rest_pose"
    bl_label = "Apply as Rest Pose"
    bl_description = "Apply the current pose as the new rest pose for the active armature"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode != 'POSE':
            return False
        obj = context.active_object
        return obj and obj.type == 'ARMATURE'

    def execute(self, context):
        armature_obj = utils.find_armature_for_object(context)
        if not armature_obj:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}

        prev_active = context.active_object
        prev_mode = context.mode
        context.view_layer.objects.active = armature_obj
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.armature_apply(selected=False)
            bpy.ops.object.mode_set(mode='POSE')
            self.report({'INFO'}, "Rest pose applied successfully")
            return {'FINISHED'}
        except Exception as e:
            try:
                bpy.ops.object.mode_set(mode='POSE' if prev_mode == 'POSE' else 'OBJECT')
            except Exception:
                pass
            self.report({'ERROR'}, f"Failed to apply rest pose: {e}")
            return {'CANCELLED'}
        finally:
            if prev_active and prev_active != armature_obj:
                try:
                    context.view_layer.objects.active = prev_active
                except Exception:
                    pass


class WPT_OT_TogglePoseRest(bpy.types.Operator):
    """Toggle armature modifiers on the active rig's deformed meshes (pose vs rest)"""
    bl_idname = "wpt.toggle_pose_rest"
    bl_label = "Toggle Pose/Rest"
    bl_description = "Toggle armature modifiers on meshes deformed by the active rig"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        rig = utils.find_armature_for_object(context)
        if not rig:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}

        meshes_with_armature = []
        for scene_obj in context.scene.objects:
            if scene_obj.type != 'MESH':
                continue
            for mod in scene_obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object == rig:
                    meshes_with_armature.append((scene_obj, mod))
                    break

        if not meshes_with_armature:
            self.report({'WARNING'},
                        f"No meshes deformed by '{rig.name}'")
            return {'CANCELLED'}

        first_mesh, first_mod = meshes_with_armature[0]
        new_state = not first_mod.show_viewport

        for mesh_obj, armature_mod in meshes_with_armature:
            armature_mod.show_viewport = new_state
            armature_mod.show_render = new_state

        n = len(meshes_with_armature)
        verb = "posed" if new_state else "rest"
        self.report({'INFO'}, f"Showing {verb} position on {n} mesh(es) of '{rig.name}'")
        return {'FINISHED'}


class WPT_OT_ToggleBonesOverlay(bpy.types.Operator):
    """Toggle bone overlay visibility in the 3D viewport"""
    bl_idname = "wpt.toggle_bones_overlay"
    bl_label = "Toggle Bones Overlay"
    bl_description = "Toggle visibility of bones in the 3D viewport overlay"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.space_data and hasattr(context.space_data, 'overlay')

    def execute(self, context):
        overlay = context.space_data.overlay
        if hasattr(overlay, 'show_bones'):
            overlay.show_bones = not overlay.show_bones
            state = "ON" if overlay.show_bones else "OFF"
            self.report({'INFO'}, f"Bones overlay: {state}")
        else:
            self.report({'WARNING'}, "Bones overlay not available in this context")
        return {'FINISHED'}


class WPT_OT_SaveBoneCollections(bpy.types.Operator):
    """Save current bone collection visibility state as a named preset"""
    bl_idname = "wpt.save_bone_collections"
    bl_label = "Save Preset"
    bl_description = "Save current bone collection visibility state as a named preset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        armature_obj = utils.find_armature_for_object(context)
        if not armature_obj:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}
        arm = armature_obj.data
        collections = getattr(arm, "collections_all", None)
        if not collections:
            self.report({'WARNING'}, "No bone collections found in armature")
            return {'CANCELLED'}
        visible_collections = [col.name for col in collections if col.is_visible]
        if not visible_collections:
            self.report({'WARNING'}, "No visible bone collections to save")
            return {'CANCELLED'}

        props = context.scene.bone_collection_props
        unique_name = utils.get_unique_pose_name(props.preset_name, context.scene.bone_collection_presets)
        new_preset = context.scene.bone_collection_presets.add()
        new_preset.name = unique_name
        new_preset.collection_data = json.dumps(visible_collections)

        names_preview = ", ".join(visible_collections[:3])
        if len(visible_collections) > 3:
            names_preview += f" and {len(visible_collections) - 3} more"
        self.report({'INFO'}, f"Saved preset '{unique_name}': {names_preview}")
        return {'FINISHED'}


class WPT_OT_RestoreBoneCollections(bpy.types.Operator):
    """Restore the selected bone collection preset"""
    bl_idname = "wpt.restore_bone_collections"
    bl_label = "Load Preset"
    bl_description = "Restore selected bone collection preset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        armature_obj = utils.find_armature_for_object(context)
        if not armature_obj:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}
        arm = armature_obj.data
        collections = getattr(arm, "collections_all", None)
        if not collections:
            self.report({'WARNING'}, "No bone collections found in armature")
            return {'CANCELLED'}

        props = context.scene.bone_collection_props
        if not context.scene.bone_collection_presets:
            self.report({'WARNING'}, "No bone collection presets saved")
            return {'CANCELLED'}

        selected_index = int(props.selected_preset)
        if selected_index < 0 or selected_index >= len(context.scene.bone_collection_presets):
            self.report({'ERROR'}, "Invalid preset selection")
            return {'CANCELLED'}

        preset = context.scene.bone_collection_presets[selected_index]
        try:
            stored_collections = json.loads(preset.collection_data)
        except Exception:
            self.report({'ERROR'}, f"Failed to load preset '{preset.name}'")
            return {'CANCELLED'}

        for col in collections:
            col.is_visible = False
        restored_count = 0
        for col_name in stored_collections:
            if col_name in collections:
                collections[col_name].is_visible = True
                restored_count += 1

        if restored_count == 0:
            self.report({'WARNING'},
                        f"None of the collections in preset '{preset.name}' found in current armature")
            return {'CANCELLED'}
        self.report({'INFO'},
                    f"Loaded preset '{preset.name}': {restored_count}/{len(stored_collections)} collections")
        return {'FINISHED'}


class WPT_OT_RenameBoneCollectionPreset(bpy.types.Operator):
    """Rename a bone collection preset"""
    bl_idname = "wpt.rename_bone_collection_preset"
    bl_label = "Rename Preset"
    bl_description = "Rename the selected bone collection preset"
    bl_options = {"REGISTER", "UNDO"}

    new_name: StringProperty(name="New Name", default="")

    def invoke(self, context, event):
        props = context.scene.bone_collection_props
        if not context.scene.bone_collection_presets:
            self.report({'ERROR'}, "No presets to rename")
            return {'CANCELLED'}
        selected_index = int(props.selected_preset)
        if selected_index < 0 or selected_index >= len(context.scene.bone_collection_presets):
            self.report({'ERROR'}, "Invalid preset selection")
            return {'CANCELLED'}
        self.new_name = context.scene.bone_collection_presets[selected_index].name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.bone_collection_props
        selected_index = int(props.selected_preset)
        if selected_index < 0 or selected_index >= len(context.scene.bone_collection_presets):
            self.report({'ERROR'}, "Invalid preset selection")
            return {'CANCELLED'}
        unique_name = utils.get_unique_pose_name(self.new_name, context.scene.bone_collection_presets)
        old_name = context.scene.bone_collection_presets[selected_index].name
        context.scene.bone_collection_presets[selected_index].name = unique_name
        self.report({'INFO'}, f"Renamed preset '{old_name}' to '{unique_name}'")
        return {'FINISHED'}


class WPT_OT_DeleteBoneCollectionPreset(bpy.types.Operator):
    """Delete a bone collection preset"""
    bl_idname = "wpt.delete_bone_collection_preset"
    bl_label = "Delete Preset"
    bl_description = "Delete the selected bone collection preset"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.bone_collection_props
        if not context.scene.bone_collection_presets:
            self.report({'ERROR'}, "No presets to delete")
            return {'CANCELLED'}
        selected_index = int(props.selected_preset)
        if selected_index < 0 or selected_index >= len(context.scene.bone_collection_presets):
            self.report({'ERROR'}, "Invalid preset selection")
            return {'CANCELLED'}
        preset_name = context.scene.bone_collection_presets[selected_index].name
        context.scene.bone_collection_presets.remove(selected_index)
        if len(context.scene.bone_collection_presets) > 0:
            props.selected_preset = "0"
        self.report({'INFO'}, f"Deleted preset '{preset_name}'")
        return {'FINISHED'}


class WPT_OT_PoseMirror(bpy.types.Operator):
    """Copy selected bones' pose to their .L/.R counterparts (X-axis flipped)"""
    bl_idname = "wpt.pose_mirror"
    bl_label = "Mirror Pose"
    bl_description = "Copy pose data from selected bones to their .L/.R/_L/_R/Left/Right counterparts (X-axis flipped)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE'
                and context.active_object
                and context.active_object.type == 'ARMATURE')

    def execute(self, context):
        rig = context.active_object
        selected_names = [pb.name for pb in rig.pose.bones if pb.bone.select]
        if not selected_names:
            self.report({'WARNING'}, "Select bones to mirror first")
            return {'CANCELLED'}
        try:
            bpy.ops.pose.copy()
            bpy.ops.pose.select_mirror(extend=False)
            bpy.ops.pose.paste(flipped=True)
            for pb in rig.pose.bones:
                pb.bone.select = pb.name in selected_names
        except RuntimeError as e:
            self.report({'ERROR'}, f"Mirror failed: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Mirrored {len(selected_names)} bone(s)")
        return {'FINISHED'}


classes = (
    WPT_OT_ToggleDeformBones,
    WPT_OT_ShowAllBones,
    WPT_OT_ApplyRestPose,
    WPT_OT_TogglePoseRest,
    WPT_OT_ToggleBonesOverlay,
    WPT_OT_SaveBoneCollections,
    WPT_OT_RestoreBoneCollections,
    WPT_OT_RenameBoneCollectionPreset,
    WPT_OT_DeleteBoneCollectionPreset,
    WPT_OT_PoseMirror,
)
