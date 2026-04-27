"""Pose slider system: save/rename/delete/T-pose/reset/apply + modal slider + popup."""

import bpy
from bpy.props import StringProperty

from . import utils


class POSE_OT_save_pose(bpy.types.Operator):
    """Save the current pose"""
    bl_idname = "pose.save_pose"
    bl_label = "Save Current Pose"
    bl_description = "Save the current pose of the active armature"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = utils.get_active_armature(context)
        if not armature:
            self.report({'ERROR'}, "No armature found in scene")
            return {'CANCELLED'}

        props = context.scene.pose_slider_props
        if not props.pose_name or props.pose_name.strip() == "":
            self.report({'ERROR'}, "Please enter a pose name")
            return {'CANCELLED'}

        pose_data = utils.save_current_pose(armature)
        if not pose_data:
            self.report({'ERROR'}, "Failed to save pose")
            return {'CANCELLED'}

        unique_name = utils.get_unique_pose_name(props.pose_name.strip(), context.scene.pose_collection)
        new_pose = context.scene.pose_collection.add()
        new_pose.name = unique_name
        new_pose.pose_data = utils.save_pose_data_to_json(pose_data)
        props.selected_pose = str(len(context.scene.pose_collection) - 1)

        self.report({'INFO'},
                    f"Saved pose: '{unique_name}' ({len(context.scene.pose_collection)} total)")
        return {'FINISHED'}


class POSE_OT_rename_pose(bpy.types.Operator):
    """Rename the selected pose"""
    bl_idname = "pose.rename_pose"
    bl_label = "Rename Pose"
    bl_description = "Rename the selected pose"
    bl_options = {"REGISTER", "UNDO"}

    new_name: StringProperty(name="New Name", default="")

    def invoke(self, context, event):
        props = context.scene.pose_slider_props
        if not context.scene.pose_collection:
            self.report({'ERROR'}, "No poses to rename")
            return {'CANCELLED'}
        selected_index = int(props.selected_pose)
        if selected_index >= len(context.scene.pose_collection):
            self.report({'ERROR'}, "Invalid pose selection")
            return {'CANCELLED'}
        self.new_name = context.scene.pose_collection[selected_index].name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.pose_slider_props
        selected_index = int(props.selected_pose)
        if selected_index >= len(context.scene.pose_collection):
            self.report({'ERROR'}, "Invalid pose selection")
            return {'CANCELLED'}
        unique_name = utils.get_unique_pose_name(self.new_name, context.scene.pose_collection)
        old_name = context.scene.pose_collection[selected_index].name
        context.scene.pose_collection[selected_index].name = unique_name
        self.report({'INFO'}, f"Renamed pose '{old_name}' to '{unique_name}'")
        return {'FINISHED'}


class POSE_OT_delete_pose(bpy.types.Operator):
    """Delete the selected pose"""
    bl_idname = "pose.delete_pose"
    bl_label = "Delete Pose"
    bl_description = "Delete the selected pose"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.pose_slider_props
        if not context.scene.pose_collection:
            self.report({'ERROR'}, "No poses to delete")
            return {'CANCELLED'}
        selected_index = int(props.selected_pose)
        if selected_index >= len(context.scene.pose_collection):
            self.report({'ERROR'}, "Invalid pose selection")
            return {'CANCELLED'}
        pose_name = context.scene.pose_collection[selected_index].name
        context.scene.pose_collection.remove(selected_index)
        self.report({'INFO'}, f"Deleted pose: {pose_name}")
        return {'FINISHED'}


class POSE_OT_generate_t_pose(bpy.types.Operator):
    """Generate a basic T-pose for the active armature"""
    bl_idname = "pose.generate_t_pose"
    bl_label = "Generate T-Pose"
    bl_description = "Generate a basic T-pose for the armature"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.get_active_armature(context) is not None

    def execute(self, context):
        armature_obj = utils.get_active_armature(context)
        if not armature_obj:
            self.report({'ERROR'}, "No armature found")
            return {'CANCELLED'}

        for bone in armature_obj.pose.bones:
            bone.location = (0, 0, 0)
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.rotation_euler = (0, 0, 0)
            bone.scale = (1, 1, 1)

        arm_keywords = ['arm', 'shoulder', 'upperarm', 'upper_arm']
        for bone in armature_obj.pose.bones:
            bone_name_lower = bone.name.lower()
            if any(k in bone_name_lower for k in arm_keywords) and ('left' in bone_name_lower or '.l' in bone_name_lower):
                bone.rotation_euler = (0, 0, 1.5708)
            elif any(k in bone_name_lower for k in arm_keywords) and ('right' in bone_name_lower or '.r' in bone_name_lower):
                bone.rotation_euler = (0, 0, -1.5708)

        self.report({'INFO'}, "Generated T-pose")
        return {'FINISHED'}


class POSE_OT_reset_to_restpose(bpy.types.Operator):
    """Reset all bones to rest pose"""
    bl_idname = "pose.reset_to_restpose"
    bl_label = "Reset to Rest"
    bl_description = "Reset all bones to rest pose"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.get_active_armature(context) is not None

    def execute(self, context):
        armature_obj = utils.get_active_armature(context)
        if not armature_obj:
            self.report({'ERROR'}, "No armature found")
            return {'CANCELLED'}
        for bone in armature_obj.pose.bones:
            bone.location = (0, 0, 0)
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.rotation_euler = (0, 0, 0)
            bone.scale = (1, 1, 1)
        context.scene.pose_slider_props.pose_factor = 0.0
        self.report({'INFO'}, "Reset to rest pose")
        return {'FINISHED'}


class POSE_OT_apply_full_pose(bpy.types.Operator):
    """Apply the selected pose at 100% strength"""
    bl_idname = "pose.apply_full_pose"
    bl_label = "Apply Full Pose"
    bl_description = "Apply the selected pose at 100% strength"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (utils.get_active_armature(context) is not None
                and context.scene.pose_collection)

    def execute(self, context):
        props = context.scene.pose_slider_props
        if not context.scene.pose_collection:
            self.report({'ERROR'}, "No saved poses")
            return {'CANCELLED'}
        selected_index = int(props.selected_pose)
        if selected_index >= len(context.scene.pose_collection):
            self.report({'ERROR'}, "Invalid pose selection")
            return {'CANCELLED'}
        props.pose_factor = 1.0
        pose_name = context.scene.pose_collection[selected_index].name
        self.report({'INFO'}, f"Applied pose: {pose_name}")
        return {'FINISHED'}


class POSE_OT_modal_slider(bpy.types.Operator):
    """Drag-mouse modal pose blend control"""
    bl_idname = "pose.modal_slider"
    bl_label = "Pose Slider Control"
    bl_description = "Control pose blending with mouse movement"
    bl_options = {"REGISTER", "UNDO"}

    initial_mouse_x: bpy.props.IntProperty(options={'HIDDEN', 'SKIP_SAVE'})
    initial_factor: bpy.props.FloatProperty(options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return (utils.get_active_armature(context) is not None
                and context.scene.pose_collection)

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            delta = event.mouse_x - self.initial_mouse_x
            factor = max(0.0, min(1.0, self.initial_factor + (delta / 200.0)))
            context.scene.pose_slider_props.pose_factor = factor
            context.area.header_text_set(f"Pose Factor: {factor:.2f} (ESC/RMB: Cancel, LMB/Enter: Confirm)")
        elif event.type in {'LEFTMOUSE', 'RET'} and event.value == 'PRESS':
            context.area.header_text_set(None)
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            context.scene.pose_slider_props.pose_factor = self.initial_factor
            context.area.header_text_set(None)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if not context.scene.pose_collection:
            self.report({'ERROR'}, "No saved poses")
            return {'CANCELLED'}
        self.initial_mouse_x = event.mouse_x
        self.initial_factor = context.scene.pose_slider_props.pose_factor
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set("Move mouse to adjust pose factor (ESC/RMB: Cancel, LMB/Enter: Confirm)")
        return {'RUNNING_MODAL'}


class POSE_OT_activate_slider_control(bpy.types.Operator):
    """Activate the modal pose-slider control"""
    bl_idname = "pose.activate_slider_control"
    bl_label = "Activate Slider Control"
    bl_description = "Activate modal pose slider control with mouse"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.pose.modal_slider('INVOKE_DEFAULT')
        return {'FINISHED'}


def draw_pose_blend(layout, context, *, with_management):
    """Pose-blend block: pose dropdown + factor + reset/apply.

    with_management adds rename/delete buttons next to the dropdown.
    """
    props = context.scene.pose_slider_props
    row = layout.row(align=True)
    row.prop(props, "selected_pose", text="")
    if with_management:
        row.operator("pose.rename_pose", text="", icon='GREASEPENCIL')
        row.operator("pose.delete_pose", text="", icon='X')

    layout.prop(props, "pose_factor", text="Factor", slider=True)

    row = layout.row(align=True)
    row.operator("pose.reset_to_restpose", text="Reset")
    row.operator("pose.apply_full_pose", text="Apply Full" if with_management else "Apply")


class POSE_OT_popup_panel(bpy.types.Operator):
    """Show pose slider as a floating popup"""
    bl_idname = "pose.popup_panel"
    bl_label = "Pose Slider Panel"
    bl_description = "Show pose slider popup panel"
    bl_options = {"REGISTER"}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Pose Slider", icon='ARMATURE_DATA')
        if context.scene.pose_collection:
            draw_pose_blend(layout, context, with_management=False)
        else:
            layout.label(text="No saved poses", icon='INFO')


classes = (
    POSE_OT_save_pose,
    POSE_OT_rename_pose,
    POSE_OT_delete_pose,
    POSE_OT_generate_t_pose,
    POSE_OT_reset_to_restpose,
    POSE_OT_apply_full_pose,
    POSE_OT_modal_slider,
    POSE_OT_activate_slider_control,
    POSE_OT_popup_panel,
)
