"""Addon preferences and the key-recording / panel-toggle helper operators."""

import bpy

from .keymaps import register_keymaps, update_keymaps


class WPT_OT_RecordKey(bpy.types.Operator):
    """Record a key press for shortcut assignment"""
    bl_idname = "wpt.record_key"
    bl_label = "Record Key"
    bl_description = "Press a key to assign it as shortcut"
    bl_options = {"REGISTER", "INTERNAL"}

    preference_name: bpy.props.StringProperty(name="Preference Name")

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'TIMER'}:
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            context.area.header_text_set(None)
            self.report({'INFO'}, "Key recording cancelled")
            return {'CANCELLED'}
        if event.value == 'PRESS':
            if event.type in {'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_ALT', 'RIGHT_ALT',
                              'LEFT_SHIFT', 'RIGHT_SHIFT', 'OSKEY'}:
                return {'RUNNING_MODAL'}
            preferences = context.preferences.addons[__package__].preferences
            setattr(preferences, self.preference_name, event.type)
            context.area.header_text_set(None)
            self.report({'INFO'}, f"Key '{event.type}' assigned")
            return {'FINISHED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if not self.preference_name:
            self.report({'ERROR'}, "No preference name specified")
            return {'CANCELLED'}
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set("Press a key to assign (ESC to cancel)")
        return {'RUNNING_MODAL'}


class WPT_OT_RecordModifiedKey(bpy.types.Operator):
    """Record a key press with modifiers for pie / quick-switch shortcut"""
    bl_idname = "wpt.record_modified_key"
    bl_label = "Record Modified Key"
    bl_description = "Press a key combination to assign it as a shortcut"
    bl_options = {"REGISTER", "INTERNAL"}

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'TIMER'}:
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            context.area.header_text_set(None)
            self.report({'INFO'}, "Key recording cancelled")
            return {'CANCELLED'}
        if event.value == 'PRESS':
            if event.type in {'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_ALT', 'RIGHT_ALT',
                              'LEFT_SHIFT', 'RIGHT_SHIFT', 'OSKEY'}:
                return {'RUNNING_MODAL'}

            preferences = context.preferences.addons[__package__].preferences
            preferences.pie_menu_shortcut = event.type
            preferences.pie_menu_ctrl = event.ctrl
            preferences.pie_menu_alt = event.alt
            preferences.pie_menu_shift = event.shift

            modifiers = []
            if event.ctrl:
                modifiers.append("Ctrl")
            if event.alt:
                modifiers.append("Alt")
            if event.shift:
                modifiers.append("Shift")
            display_key = "+".join(modifiers + [event.type])

            context.area.header_text_set(None)
            self.report({'INFO'}, f"Key combination '{display_key}' assigned")
            return {'FINISHED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set("Press a key combination (with modifiers) to assign (ESC to cancel)")
        return {'RUNNING_MODAL'}


class WPT_OT_ToggleMainPanel(bpy.types.Operator):
    """Toggle the main Weight Paint Tools panel as a popup"""
    bl_idname = "wpt.toggle_main_panel"
    bl_label = "Toggle Main Panel"
    bl_description = "Toggle the Weight Paint Tools panel visibility"

    def execute(self, context):
        try:
            return bpy.ops.wm.call_panel(name='WPT_PT_main_panel')
        except Exception as e:
            self.report({'ERROR'}, f"Failed to toggle panel: {e}")
            return {'FINISHED'}


class WPT_OT_RefreshKeymaps(bpy.types.Operator):
    """Manually re-register all addon keymaps"""
    bl_idname = "wpt.refresh_keymaps"
    bl_label = "Refresh Keymaps"
    bl_description = "Manually refresh all addon keyboard shortcuts"
    bl_options = {"REGISTER"}

    def execute(self, context):
        register_keymaps()
        self.report({'INFO'}, "Keymaps refreshed successfully")
        return {'FINISHED'}


class WPT_AddonPreferences(bpy.types.AddonPreferences):
    """Preferences for the My Simp addon"""
    bl_idname = __package__

    panel_shortcut: bpy.props.StringProperty(
        name="Open Panel",
        description="Shortcut key to open the main panel",
        default="Y",
        update=update_keymaps,
    )
    toggle_bones_shortcut: bpy.props.StringProperty(
        name="Toggle Bones Overlay",
        description="Shortcut key to toggle bones overlay visibility",
        default="D",
        update=update_keymaps,
    )
    pie_menu_shortcut: bpy.props.StringProperty(
        name="Brush Pie Menu",
        description="Shortcut key to open the brush pie menu in Weight Paint mode",
        default="Q",
        update=update_keymaps,
    )
    pie_menu_alt: bpy.props.BoolProperty(name="Alt", default=True, update=update_keymaps)
    pie_menu_ctrl: bpy.props.BoolProperty(name="Ctrl", default=False, update=update_keymaps)
    pie_menu_shift: bpy.props.BoolProperty(name="Shift", default=False, update=update_keymaps)
    gradient_toggle_shortcut: bpy.props.StringProperty(
        name="Gradient Add/Subtract",
        description="Shortcut key to toggle gradient tool between add and subtract modes",
        default="E",
        update=update_keymaps,
    )
    quick_switch_mesh_shortcut: bpy.props.StringProperty(
        name="Quick Switch Mesh",
        description="Shortcut key to confirm object switch after using Alt+Q",
        default="U",
        update=update_keymaps,
    )
    quick_switch_mesh_alt: bpy.props.BoolProperty(name="Alt", default=True, update=update_keymaps)
    quick_switch_mesh_ctrl: bpy.props.BoolProperty(name="Ctrl", default=False, update=update_keymaps)
    quick_switch_mesh_shift: bpy.props.BoolProperty(name="Shift", default=False, update=update_keymaps)

    stored_bone_collections: bpy.props.StringProperty(
        name="Stored Bone Collections",
        description="Names of stored bone collections (JSON)",
        default="[]",
    )
    bone_collection_preset_name: bpy.props.StringProperty(
        name="Preset Name",
        description="Name for the current bone collection preset",
        default="My Preset",
    )

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Keyboard Shortcuts:", icon='KEYINGSET')
        col = box.column()
        col.label(text="Note: Shortcuts update immediately. No restart required.", icon='INFO')
        col.label(text="Click 'Record' and press the desired key to assign shortcuts.", icon='REC')

        grid = box.grid_flow(row_major=True, columns=1, even_columns=True)

        # Panel shortcut
        row = grid.row(align=True)
        split = row.split(factor=0.3)
        split.label(text="Open Panel:")
        sub_row = split.row(align=True)
        sub_row.prop(self, "panel_shortcut", text="")
        op = sub_row.operator("wpt.record_key", text="Record", icon='REC')
        op.preference_name = "panel_shortcut"

        # Toggle bones overlay
        row = grid.row(align=True)
        split = row.split(factor=0.3)
        split.label(text="Toggle Bones Overlay:")
        sub_row = split.row(align=True)
        sub_row.prop(self, "toggle_bones_shortcut", text="")
        op = sub_row.operator("wpt.record_key", text="Record", icon='REC')
        op.preference_name = "toggle_bones_shortcut"

        # Pie menu (with modifiers)
        row = grid.row(align=True)
        split = row.split(factor=0.3)
        split.label(text="Brush Pie Menu:")
        sub_col = split.column(align=True)
        sub_row = sub_col.row(align=True)
        sub_row.prop(self, "pie_menu_shortcut", text="")
        mod_row = sub_row.row(align=True)
        mod_row.prop(self, "pie_menu_ctrl", text="Ctrl", toggle=True)
        mod_row.prop(self, "pie_menu_alt", text="Alt", toggle=True)
        mod_row.prop(self, "pie_menu_shift", text="Shift", toggle=True)
        sub_row.operator("wpt.record_modified_key", text="Record", icon='REC')

        # Gradient toggle
        row = grid.row(align=True)
        split = row.split(factor=0.3)
        split.label(text="Gradient Add/Subtract:")
        sub_row = split.row(align=True)
        sub_row.prop(self, "gradient_toggle_shortcut", text="")
        op = sub_row.operator("wpt.record_key", text="Record", icon='REC')
        op.preference_name = "gradient_toggle_shortcut"

        # Quick switch mesh
        row = grid.row(align=True)
        split = row.split(factor=0.3)
        split.label(text="Quick Switch Mesh:")
        sub_col = split.column(align=True)
        sub_row = sub_col.row(align=True)
        sub_row.prop(self, "quick_switch_mesh_shortcut", text="")
        mod_row = sub_row.row(align=True)
        mod_row.prop(self, "quick_switch_mesh_ctrl", text="Ctrl", toggle=True)
        mod_row.prop(self, "quick_switch_mesh_alt", text="Alt", toggle=True)
        mod_row.prop(self, "quick_switch_mesh_shift", text="Shift", toggle=True)
        sub_row.operator("wpt.record_modified_key", text="Record", icon='REC')

        layout.separator()
        layout.operator("wpt.refresh_keymaps", text="Refresh Keymaps", icon='FILE_REFRESH')


classes = (
    WPT_OT_RecordKey,
    WPT_OT_RecordModifiedKey,
    WPT_OT_ToggleMainPanel,
    WPT_OT_RefreshKeymaps,
    WPT_AddonPreferences,
)
