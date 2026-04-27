"""Mesh-level symmetry operators for My Simp (cut half / add mirror modifier)."""

import bpy


class WPT_OT_CutHalfMesh(bpy.types.Operator):
    """Cut the mesh in half along the chosen axis for symmetrical weight painting"""
    bl_idname = "wpt.cut_half_mesh"
    bl_label = "Cut Half"
    bl_description = "Cut the mesh in half for symmetrical weight painting"
    bl_options = {"REGISTER", "UNDO"}

    axis: bpy.props.EnumProperty(
        name="Mirror Axis",
        items=[
            ('X', "X-Axis", "Cut along X axis (keep +X side)"),
            ('Y', "Y-Axis", "Cut along Y axis (keep +Y side)"),
            ('Z', "Z-Axis", "Cut along Z axis (keep +Z side)"),
        ],
        default='X',
    )

    keep_positive: bpy.props.BoolProperty(
        name="Keep Positive Side",
        description="Keep the positive side of the axis (+X, +Y or +Z)",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "axis")
        layout.prop(self, "keep_positive")
        layout.label(text="Warning: This is a destructive operation.", icon='ERROR')
        layout.label(text="Make a backup of your model first.")

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh")
            return {'CANCELLED'}

        original_mode = obj.mode
        bpy.ops.object.mode_set(mode='EDIT')
        axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[self.axis]
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.context.tool_settings.mesh_select_mode = (True, True, True)
        bpy.ops.mesh.bisect(
            plane_co=(0, 0, 0),
            plane_no=(
                1 if axis_idx == 0 else 0,
                1 if axis_idx == 1 else 0,
                1 if axis_idx == 2 else 0,
            ),
            clear_inner=not self.keep_positive,
            clear_outer=self.keep_positive,
        )
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode=original_mode)

        side = 'positive' if self.keep_positive else 'negative'
        self.report({'INFO'}, f"Cut mesh along {self.axis}-axis, keeping {side} side")
        return {'FINISHED'}


class WPT_OT_AddMirror(bpy.types.Operator):
    """Add a mirror modifier to the mesh for symmetrical weight painting"""
    bl_idname = "wpt.add_mirror"
    bl_label = "Add Mirror"
    bl_description = "Add a mirror modifier to the mesh for symmetrical weight painting"
    bl_options = {"REGISTER", "UNDO"}

    axis: bpy.props.EnumProperty(
        name="Mirror Axis",
        items=[
            ('X', "X-Axis", "Mirror along X axis"),
            ('Y', "Y-Axis", "Mirror along Y axis"),
            ('Z', "Z-Axis", "Mirror along Z axis"),
        ],
        default='X',
    )

    mirror_weights: bpy.props.BoolProperty(
        name="Mirror Weights",
        description="Also mirror vertex weights across the selected axis",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "axis")
        layout.prop(self, "mirror_weights")

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh")
            return {'CANCELLED'}

        for mod in obj.modifiers:
            if mod.type == 'MIRROR':
                self.report({'WARNING'}, "Mirror modifier already exists. Adding another one.")
                break

        mirror = obj.modifiers.new(name="Mirror", type='MIRROR')
        if self.axis == 'X':
            mirror.use_axis = (True, False, False)
        elif self.axis == 'Y':
            mirror.use_axis = (False, True, False)
        else:
            mirror.use_axis = (False, False, True)
        mirror.use_mirror_vertex_groups = self.mirror_weights

        if len(obj.modifiers) > 1:
            for _ in range(len(obj.modifiers) - 1):
                bpy.ops.object.modifier_move_up(modifier="Mirror")

        weight_note = ' with weight mirroring' if self.mirror_weights else ''
        self.report({'INFO'}, f"Added mirror modifier along {self.axis}-axis{weight_note}")
        return {'FINISHED'}


classes = (
    WPT_OT_CutHalfMesh,
    WPT_OT_AddMirror,
)
