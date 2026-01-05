# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

bl_info = {
    "name": "My Simp",
    "author": "Korn Sensei", 
    "description": "Streamlined weight painting tools for character rigging",
    "blender": (3, 0, 0),
    "version": (2, 8, 1),
    "location": "3D Viewport > Sidebar > Weight Paint",
    "warning": "",
    "doc_url": "", 
    "tracker_url": "", 
    "category": "Rigging" 
}

import bpy
import bpy.utils.previews
import os
from mathutils.kdtree import KDTree
from bpy.utils import flip_name
import mathutils
import json
from mathutils import Quaternion, Vector
from bpy.props import FloatProperty, StringProperty, BoolProperty, CollectionProperty, EnumProperty, IntProperty
from bpy.types import PropertyGroup, Panel, Operator  

addon_keymaps = {}
_icons = None

# ===== KEYMAP MANAGEMENT =====

def register_keymaps():
    """Register all keymaps with current preference values"""
    global addon_keymaps
    
    # Clear existing keymaps first
    unregister_keymaps()
    
    wm = bpy.context.window_manager
    if not wm:
        return
        
    kc = wm.keyconfigs.addon
    if not kc:
        return
    
    # Get current preferences
    try:
        preferences = bpy.context.preferences.addons[__name__].preferences
    except:
        return
    
    print("[WPT] Registering keymaps:")
    print(f"[WPT]   panel_shortcut: {preferences.panel_shortcut}")
    print(f"[WPT]   toggle_bones_shortcut: {preferences.toggle_bones_shortcut}")
    print(f"[WPT]   pie_menu_shortcut: {preferences.pie_menu_shortcut}")
    print(f"[WPT]   gradient_toggle_shortcut: {preferences.gradient_toggle_shortcut}")
    
    # Main panel shortcut - register in Window context for global access
    try:
        km_window = kc.keymaps.get('Window') or kc.keymaps.new(name='Window', space_type='EMPTY')
        kmi = km_window.keymap_items.new('wpt.toggle_main_panel', preferences.panel_shortcut, 'PRESS')
        addon_keymaps['main_window'] = (km_window, kmi)
        print(f"[WPT] Registered main panel with key: {preferences.panel_shortcut}")
    except Exception as e:
        print(f"[WPT] ERROR registering main panel: {e}")
        pass
    
    # Also register in 3D View context as backup
    try:
        km_3d = kc.keymaps.get('3D View') or kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi_3d = km_3d.keymap_items.new('wpt.toggle_main_panel', preferences.panel_shortcut, 'PRESS')
        addon_keymaps['main_3d_view'] = (km_3d, kmi_3d)
        print(f"[WPT] Registered 3D View panel with key: {preferences.panel_shortcut}")
    except Exception as e:
        print(f"[WPT] ERROR registering 3D View panel: {e}")
        pass
    
    # Toggle bones overlay - register in Window and 3D View contexts
    try:
        km_window = kc.keymaps.get('Window') or kc.keymaps.new(name='Window', space_type='EMPTY')
        kmi_bones = km_window.keymap_items.new('wpt.toggle_bones_overlay', preferences.toggle_bones_shortcut, 'PRESS')
        addon_keymaps['toggle_bones_window'] = (km_window, kmi_bones)
    except:
        pass
    
    try:
        km_3d = kc.keymaps.get('3D View') or kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi_bones_3d = km_3d.keymap_items.new('wpt.toggle_bones_overlay', preferences.toggle_bones_shortcut, 'PRESS')
        addon_keymaps['toggle_bones_3d_view'] = (km_3d, kmi_bones_3d)
    except:
        pass

    # Weight Paint mode shortcuts
    try:
        km_wp = kc.keymaps.get('Weight Paint') or kc.keymaps.new(name='Weight Paint', space_type='EMPTY')
        
        # Pie menu for brushes in Weight Paint mode
        kmi_pie = km_wp.keymap_items.new('wm.call_menu_pie', preferences.pie_menu_shortcut, 'PRESS', 
                                        ctrl=preferences.pie_menu_ctrl,
                                        alt=preferences.pie_menu_alt, 
                                        shift=preferences.pie_menu_shift)
        kmi_pie.properties.name = 'WPT_MT_brush_pie_menu'
        addon_keymaps['brush_pie'] = (km_wp, kmi_pie)
        
        # Gradient Add/Subtract toggle
        kmi_gradient = km_wp.keymap_items.new('wpt.gradient_add_subtract', preferences.gradient_toggle_shortcut, 'PRESS')
        addon_keymaps['gradient_toggle'] = (km_wp, kmi_gradient)
        
        # Quick mesh switch with U key (in weight paint mode) - after Alt+Q to switch object
        kmi_switch = km_wp.keymap_items.new('wpt.quick_switch_mesh', preferences.quick_switch_mesh_shortcut, 'PRESS', 
                                           ctrl=preferences.quick_switch_mesh_ctrl,
                                           alt=preferences.quick_switch_mesh_alt,
                                           shift=preferences.quick_switch_mesh_shift)
        addon_keymaps['quick_switch_mesh'] = (km_wp, kmi_switch)
        print("[WPT] Registered quick switch mesh with Alt+U in Weight Paint mode")
    except Exception as e:
        print(f"[WPT] ERROR registering quick switch mesh: {e}")
        pass
    
    # Also try registering in 3D View context for weight paint
    try:
        km_3d = kc.keymaps.get('3D View') or kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi_switch_3d = km_3d.keymap_items.new('wpt.quick_switch_mesh', preferences.quick_switch_mesh_shortcut, 'PRESS',
                                              ctrl=preferences.quick_switch_mesh_ctrl,
                                              alt=preferences.quick_switch_mesh_alt,
                                              shift=preferences.quick_switch_mesh_shift)
        addon_keymaps['quick_switch_mesh_3d'] = (km_3d, kmi_switch_3d)
        print("[WPT] Registered quick switch mesh with Alt+U in 3D View")
    except Exception as e:
        print(f"[WPT] ERROR registering quick switch mesh in 3D View: {e}")
    
    # Pose Slider shortcuts - register in Window context for global access
    try:
        km_window = kc.keymaps.get('Window') or kc.keymaps.new(name='Window', space_type='EMPTY')
        
        # X key for slider control
        kmi_pose_slider = km_window.keymap_items.new('pose.activate_slider_control', 'X', 'PRESS')
        addon_keymaps['pose_slider_window'] = (km_window, kmi_pose_slider)
        
        # P key for popup panel
        kmi_pose_popup = km_window.keymap_items.new('pose.popup_panel', 'P', 'PRESS')
        addon_keymaps['pose_popup_window'] = (km_window, kmi_pose_popup)
    except:
        pass
    
    # Also register pose shortcuts in 3D View as backup
    try:
        km_3d = kc.keymaps.get('3D View') or kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        
        # X key for slider control
        kmi_pose_slider_3d = km_3d.keymap_items.new('pose.activate_slider_control', 'X', 'PRESS')
        addon_keymaps['pose_slider_3d'] = (km_3d, kmi_pose_slider_3d)
        
        # P key for popup panel
        kmi_pose_popup_3d = km_3d.keymap_items.new('pose.popup_panel', 'P', 'PRESS')
        addon_keymaps['pose_popup_3d'] = (km_3d, kmi_pose_popup_3d)
    except:
        pass

def unregister_keymaps():
    """Unregister all keymaps - complete cleanup"""
    global addon_keymaps
    
    wm = bpy.context.window_manager
    if not wm:
        return
    
    kc = wm.keyconfigs.addon
    if not kc:
        return
    
    # List of all operator IDs we use
    addon_operator_ids = {
        'wpt.toggle_main_panel',
        'wpt.toggle_bones_overlay',
        'wm.call_menu_pie',
        'wpt.gradient_add_subtract',
        'pose.activate_slider_control',
        'pose.popup_panel'
    }
    
    # First, remove tracked keymaps from addon_keymaps dict
    for key, (km, kmi) in addon_keymaps.items():
        try:
            if km and kmi and kmi in km.keymap_items:
                km.keymap_items.remove(kmi)
        except:
            continue
    
    addon_keymaps.clear()
    
    # Second, do a thorough scan to remove ANY remaining keymap items from our operators
    # This handles legacy keymaps from previous sessions
    for km in kc.keymaps:
        items_to_remove = []
        for kmi in km.keymap_items:
            if kmi.idname in addon_operator_ids:
                items_to_remove.append(kmi)
        
        for kmi in items_to_remove:
            try:
                km.keymap_items.remove(kmi)
            except:
                continue

def update_keymaps(self, context):
    """Update callback for when preferences change"""
    print("[WPT] update_keymaps callback triggered")
    # Use a timer to defer execution since context might be incomplete during property update
    def do_update():
        try:
            register_keymaps()
            print("[WPT] Keymaps updated successfully")
            return None  # Return None to stop the timer
        except Exception as e:
            print(f"[WPT] Error updating keymaps: {e}")
            return None
    
    bpy.app.timers.register(do_update, first_interval=0.01)

# ===== KEY RECORDING OPERATORS =====

class WPT_OT_RecordKey(bpy.types.Operator):
    """Record a key press for shortcut assignment"""
    bl_idname = "wpt.record_key"
    bl_label = "Record Key"
    bl_description = "Press a key to assign it as shortcut"
    bl_options = {"REGISTER", "INTERNAL"}
    
    preference_name: bpy.props.StringProperty(name="Preference Name")
    
    def __init__(self):
        self.recording = False
        self.recorded_key = ""
    
    def modal(self, context, event):
        # Ignore mouse movement and modifier-only presses
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'TIMER'}:
            return {'RUNNING_MODAL'}
        
        # Cancel on ESC or right mouse
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            context.area.header_text_set(None)
            self.report({'INFO'}, "Key recording cancelled")
            return {'CANCELLED'}
        
        # Only capture key press events (not release)
        if event.value == 'PRESS':
            # Skip modifier keys alone
            if event.type in {'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_ALT', 'RIGHT_ALT', 
                             'LEFT_SHIFT', 'RIGHT_SHIFT', 'OSKEY'}:
                return {'RUNNING_MODAL'}
            
            # Record the key
            self.recorded_key = event.type
            
            # Apply to preference
            preferences = context.preferences.addons[__name__].preferences
            old_value = getattr(preferences, self.preference_name, None)
            setattr(preferences, self.preference_name, self.recorded_key)
            new_value = getattr(preferences, self.preference_name, None)
            
            print(f"[WPT] Key Recording: {self.preference_name}")
            print(f"[WPT] Old value: {old_value}, New value: {new_value}")
            
            context.area.header_text_set(None)
            self.report({'INFO'}, f"Key '{self.recorded_key}' assigned")
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
    """Record a key press with modifiers for pie menu shortcut"""
    bl_idname = "wpt.record_modified_key"
    bl_label = "Record Modified Key"
    bl_description = "Press a key combination to assign it as pie menu shortcut"
    bl_options = {"REGISTER", "INTERNAL"}
    
    def __init__(self):
        self.recording = False
        self.recorded_key = ""
        self.recorded_ctrl = False
        self.recorded_alt = False
        self.recorded_shift = False
    
    def modal(self, context, event):
        # Ignore mouse movement
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'TIMER'}:
            return {'RUNNING_MODAL'}
        
        # Cancel on ESC or right mouse
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            context.area.header_text_set(None)
            self.report({'INFO'}, "Key recording cancelled")
            return {'CANCELLED'}
        
        # Only capture key press events (not release)
        if event.value == 'PRESS':
            # Skip modifier keys alone, but record them
            if event.type in {'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_ALT', 'RIGHT_ALT', 
                             'LEFT_SHIFT', 'RIGHT_SHIFT', 'OSKEY'}:
                return {'RUNNING_MODAL'}
            
            # Record the key and current modifier states
            self.recorded_key = event.type
            self.recorded_ctrl = event.ctrl
            self.recorded_alt = event.alt
            self.recorded_shift = event.shift
            
            # Apply to preferences
            preferences = context.preferences.addons[__name__].preferences
            preferences.pie_menu_shortcut = self.recorded_key
            preferences.pie_menu_ctrl = self.recorded_ctrl
            preferences.pie_menu_alt = self.recorded_alt
            preferences.pie_menu_shift = self.recorded_shift
            
            # Build display string
            modifiers = []
            if self.recorded_ctrl:
                modifiers.append("Ctrl")
            if self.recorded_alt:
                modifiers.append("Alt")
            if self.recorded_shift:
                modifiers.append("Shift")
            
            display_key = "+".join(modifiers + [self.recorded_key])
            
            context.area.header_text_set(None)
            self.report({'INFO'}, f"Key combination '{display_key}' assigned")
            return {'FINISHED'}
        
        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set("Press a key combination (with modifiers) to assign (ESC to cancel)")
        return {'RUNNING_MODAL'}

# ===== TOGGLE PANEL OPERATOR =====

class WPT_OT_ToggleMainPanel(bpy.types.Operator):
    """Toggle the main Weight Paint Tools panel"""
    bl_idname = "wpt.toggle_main_panel"
    bl_label = "Toggle Main Panel"
    bl_description = "Toggle the Weight Paint Tools panel visibility"
    
    def execute(self, context):
        # Use Blender's built-in operator to toggle the panel
        try:
            return bpy.ops.wm.call_panel(name='WPT_PT_main_panel')
        except Exception as e:
            self.report({'ERROR'}, f"Failed to toggle panel: {e}")
            return {'FINISHED'}

# ===== ADDON PREFERENCES =====

class WPT_AddonPreferences(bpy.types.AddonPreferences):
    """Preferences for the My Simp addon"""
    bl_idname = __name__
    
    # Shortcut key preferences
    panel_shortcut: bpy.props.StringProperty(
        name="Open Panel",
        description="Shortcut key to open the main panel",
        default="Y",
        update=update_keymaps
    )
    
    toggle_bones_shortcut: bpy.props.StringProperty(
        name="Toggle Bones Overlay",
        description="Shortcut key to toggle bones overlay visibility",
        default="D",
        update=update_keymaps
    )
    
    pie_menu_shortcut: bpy.props.StringProperty(
        name="Brush Pie Menu",
        description="Shortcut key to open the brush pie menu in Weight Paint mode",
        default="Q",
        update=update_keymaps
    )
    
    pie_menu_alt: bpy.props.BoolProperty(
        name="Alt",
        description="Use Alt modifier for pie menu shortcut",
        default=True,
        update=update_keymaps
    )
    
    pie_menu_ctrl: bpy.props.BoolProperty(
        name="Ctrl",
        description="Use Ctrl modifier for pie menu shortcut",
        default=False,
        update=update_keymaps
    )
    
    pie_menu_shift: bpy.props.BoolProperty(
        name="Shift",
        description="Use Shift modifier for pie menu shortcut",
        default=False,
        update=update_keymaps
    )
    
    gradient_toggle_shortcut: bpy.props.StringProperty(
        name="Gradient Add/Subtract",
        description="Shortcut key to toggle gradient tool between add and subtract modes",
        default="E",
        update=update_keymaps
    )
    
    quick_switch_mesh_shortcut: bpy.props.StringProperty(
        name="Quick Switch Mesh",
        description="Shortcut key to confirm object switch after using Alt+Q",
        default="U",
        update=update_keymaps
    )
    
    quick_switch_mesh_alt: bpy.props.BoolProperty(
        name="Alt",
        description="Use Alt modifier for quick switch mesh shortcut",
        default=True,
        update=update_keymaps
    )
    
    quick_switch_mesh_ctrl: bpy.props.BoolProperty(
        name="Ctrl",
        description="Use Ctrl modifier for quick switch mesh shortcut",
        default=False,
        update=update_keymaps
    )
    
    quick_switch_mesh_shift: bpy.props.BoolProperty(
        name="Shift",
        description="Use Shift modifier for quick switch mesh shortcut",
        default=False,
        update=update_keymaps
    )
    
    # Bone collection storage
    stored_bone_collections: bpy.props.StringProperty(
        name="Stored Bone Collections",
        description="Names of stored bone collections (JSON)",
        default="[]"
    )
    
    bone_collection_preset_name: bpy.props.StringProperty(
        name="Preset Name",
        description="Name for the current bone collection preset",
        default="My Preset"
    )
    
    def draw(self, context):
        layout = self.layout
        
        box = layout.box()
        box.label(text="Keyboard Shortcuts:", icon='KEYINGSET')
        
        col = box.column()
        col.label(text="Note: Shortcuts update immediately. No restart required.", icon='INFO')
        col.label(text="Click 'Record' and press the desired key to assign shortcuts.", icon='REC')
        
        # Create a grid layout for shortcuts
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
        
        # Pie menu with modifiers (special case)
        row = grid.row(align=True)
        split = row.split(factor=0.3)
        split.label(text="Brush Pie Menu:")
        sub_col = split.column(align=True)
        
        # Key and modifiers row
        sub_row = sub_col.row(align=True)
        sub_row.prop(self, "pie_menu_shortcut", text="")
        
        # Modifier checkboxes
        mod_row = sub_row.row(align=True)
        mod_row.prop(self, "pie_menu_ctrl", text="Ctrl", toggle=True)
        mod_row.prop(self, "pie_menu_alt", text="Alt", toggle=True)
        mod_row.prop(self, "pie_menu_shift", text="Shift", toggle=True)
        
        # Record button for pie menu
        sub_row.operator("wpt.record_modified_key", text="Record", icon='REC')
        
        # Gradient toggle
        row = grid.row(align=True)
        split = row.split(factor=0.3)
        split.label(text="Gradient Add/Subtract:")
        sub_row = split.row(align=True)
        sub_row.prop(self, "gradient_toggle_shortcut", text="")
        op = sub_row.operator("wpt.record_key", text="Record", icon='REC')
        op.preference_name = "gradient_toggle_shortcut"
        
        # Quick switch mesh with modifiers
        row = grid.row(align=True)
        split = row.split(factor=0.3)
        split.label(text="Quick Switch Mesh:")
        sub_col = split.column(align=True)
        
        # Key and modifiers row
        sub_row = sub_col.row(align=True)
        sub_row.prop(self, "quick_switch_mesh_shortcut", text="")
        
        # Modifier checkboxes
        mod_row = sub_row.row(align=True)
        mod_row.prop(self, "quick_switch_mesh_ctrl", text="Ctrl", toggle=True)
        mod_row.prop(self, "quick_switch_mesh_alt", text="Alt", toggle=True)
        mod_row.prop(self, "quick_switch_mesh_shift", text="Shift", toggle=True)
        
        # Record button for quick switch mesh
        sub_row.operator("wpt.record_modified_key", text="Record", icon='REC')
        
        # Add button to manually refresh keymaps
        layout.separator()
        layout.operator("wpt.refresh_keymaps", text="Refresh Keymaps", icon='FILE_REFRESH')

# Add operator to manually refresh keymaps
class WPT_OT_RefreshKeymaps(bpy.types.Operator):
    """Refresh addon keymaps"""
    bl_idname = "wpt.refresh_keymaps"
    bl_label = "Refresh Keymaps"
    bl_description = "Manually refresh all addon keyboard shortcuts"
    bl_options = {"REGISTER"}
    
    def execute(self, context):
        register_keymaps()
        self.report({'INFO'}, "Keymaps refreshed successfully")
        return {'FINISHED'}

# ===== OPERATORS =====

class WPT_OT_SetBrushMode(bpy.types.Operator):
    """Set weight paint brush mode"""
    bl_idname = "wpt.set_brush_mode"
    bl_label = "Set Brush Mode"
    bl_description = "Set the weight paint brush and blend mode"
    bl_options = {"REGISTER", "UNDO"}
    
    mode: bpy.props.StringProperty(name="Mode", default="MIX")
    tool: bpy.props.StringProperty(name="Tool", default="builtin_brush.Draw")

    def execute(self, context):
        # Set the tool first
        try:
            bpy.ops.wm.tool_set_by_id(name=self.tool)
        except:
            self.report({'WARNING'}, f"Could not switch to tool: {self.tool}")
            
        # Set blend mode only for Draw brush with valid blend modes
        if (context.mode == 'PAINT_WEIGHT' and 
            self.tool == "builtin_brush.Draw" and 
            self.mode in ['MIX', 'ADD', 'SUB']):
            brush = context.tool_settings.weight_paint.brush
            if brush:
                brush.blend = self.mode
                
        return {'FINISHED'}


class WPT_OT_SetupWeightPaint(bpy.types.Operator):
    """Automatically setup weight painting with the active mesh and armature"""
    bl_idname = "wpt.setup_weight_paint"
    bl_label = "Setup Weight Paint"
    bl_description = "Automatically select armature and mesh, then enter Weight Paint mode"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        mesh_obj = context.active_object
        
        # Find armature - check modifiers first, then scene
        rig = None
        for mod in mesh_obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                rig = mod.object
                break
        
        if not rig:
            rigs = [obj for obj in context.scene.objects if obj.type == 'ARMATURE']
            if not rigs:
                self.report({'ERROR'}, "No armature found in the scene")
                return {'CANCELLED'}
            if len(rigs) > 1:
                self.report({'WARNING'}, "Multiple armatures found. Using the first one")
            rig = rigs[0]

        # Setup selection and mode
        # CRITICAL: Set active object BEFORE selecting, in correct order
        for obj in context.scene.objects:
            obj.select_set(False)
        
        # Set mesh as active FIRST
        context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        rig.select_set(True)

        # Enter Weight Paint mode
        try:
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        except RuntimeError:
            # If context is wrong, try with 3D view override
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    with context.temp_override(area=area):
                        try:
                            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
                        except:
                            pass
                    break
        self.report({'INFO'}, f"Setup complete: '{rig.name}' + '{mesh_obj.name}'")
        return {'FINISHED'}


class WPT_OT_SwitchTool(bpy.types.Operator):
    """Switch between weight paint tools"""
    bl_idname = "wpt.switch_tool"
    bl_label = "Switch Tool"
    bl_description = "Switch to the specified weight paint tool"
    bl_options = {"REGISTER", "UNDO"}
    
    tool_name: bpy.props.StringProperty(default="builtin_brush.Draw")

    def execute(self, context):
        try:
            bpy.ops.wm.tool_set_by_id(name=self.tool_name)
        except:
            self.report({'WARNING'}, f"Could not switch to tool: {self.tool_name}")
        return {'FINISHED'}


class WPT_OT_QuickSwitchMesh(bpy.types.Operator):
    """Switch mesh after using Alt+Q - press U to confirm"""
    bl_idname = "wpt.quick_switch_mesh"
    bl_label = "Confirm Mesh Switch"
    bl_description = "After using Alt+Q to switch object, press U to finalize in weight paint mode"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        # Must be in weight paint mode
        return context.mode == 'PAINT_WEIGHT'

    def execute(self, context):
        print("[DEBUG] WPT_OT_QuickSwitchMesh operator called")
        current_mesh = context.active_object
        if not current_mesh or current_mesh.type != 'MESH':
            self.report({'ERROR'}, "No active mesh")
            return {'CANCELLED'}

        # Find armature from current mesh
        armature = None
        for mod in current_mesh.modifiers:
            if mod.type == 'ARMATURE':
                armature = mod.object
                break

        if not armature:
            self.report({'ERROR'}, "No armature found")
            return {'CANCELLED'}

        try:
            # Save selected bones
            selected_bones = [b.name for b in armature.data.bones if b.select]

            # Go to object mode
            bpy.ops.object.mode_set(mode='OBJECT')

            # Deselect all
            for obj in context.scene.objects:
                obj.select_set(False)

            # Select rig (armature) and mesh, with mesh as active
            armature.select_set(True)
            current_mesh.select_set(True)
            context.view_layer.objects.active = current_mesh

            # Re-enter weight paint mode
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

            # Restore bone selection
            if selected_bones:
                for bone in armature.data.bones:
                    if bone.name in selected_bones:
                        bone.select = True

            self.report({'INFO'}, f"Switched to {current_mesh.name} in weight paint mode")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class WPT_OT_MirrorWeights(bpy.types.Operator):
    """Mirror vertex group weights across the specified axis"""
    bl_idname = "wpt.mirror_weights"
    bl_label = "Mirror Weights"
    bl_description = "Mirror active vertex group weights across the X axis"
    bl_options = {"REGISTER", "UNDO"}

    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[
            ('X', "X-Axis", "Mirror across X axis"),
            ('Y', "Y-Axis", "Mirror across Y axis"),
            ('Z', "Z-Axis", "Mirror across Z axis"),
        ],
        default='X'
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and 
                context.mode == 'PAINT_WEIGHT' and
                obj.vertex_groups.active is not None)

    def execute(self, context):
        obj = context.active_object
        vg_name = obj.vertex_groups.active.name
        prev_mode = obj.mode
        
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.symmetrize_vertex_group(obj, vg_name, self.axis)
            bpy.ops.object.mode_set(mode=prev_mode)
            self.report({'INFO'}, f"Mirrored weights across {self.axis}-axis")
            return {'FINISHED'}
        except Exception as e:
            try:
                bpy.ops.object.mode_set(mode=prev_mode)
            except:
                pass
            self.report({'ERROR'}, f"Failed to mirror weights: {str(e)}")
            return {'CANCELLED'}

    def symmetrize_vertex_group(self, obj, vg_name, axis='X', threshold=0.0001):
        """Mirror vertex group weights using KDTree for vertex matching"""
        vertices = obj.data.vertices
        size = len(vertices)
        kd = KDTree(size)
        
        for i, v in enumerate(vertices):
            kd.insert(v.co, i)
        kd.balance()

        coord_i = 'XYZ'.find(axis)
        vert_map = {}
        
        for vert_idx, vert in enumerate(vertices):
            flipped_co = vert.co.copy()
            flipped_co[coord_i] *= -1
            _opposite_co, opposite_idx, dist = kd.find(flipped_co)
            if dist <= threshold:
                vert_map[vert_idx] = opposite_idx

        vgroup = obj.vertex_groups.get(vg_name)
        if not vgroup:
            return

        opp_name = flip_name(vg_name)
        opp_vgroup = obj.vertex_groups.get(opp_name)
        if not opp_vgroup:
            opp_vgroup = obj.vertex_groups.new(name=opp_name)

        if vgroup != opp_vgroup:
            opp_vgroup.remove(range(len(vertices)))

        # Collect and apply mirrored weights
        dst_weights = {}
        for src_idx, dst_idx in vert_map.items():
            try:
                src_weight = vgroup.weight(src_idx)
                if dst_idx not in dst_weights:
                    dst_weights[dst_idx] = []
                dst_weights[dst_idx].append(src_weight)
            except RuntimeError:
                continue

        for dst_idx, weights in dst_weights.items():
            avg_weight = sum(weights) / len(weights)
            if avg_weight > 0:
                opp_vgroup.add([dst_idx], avg_weight, 'REPLACE')


class WPT_OT_ToggleDeformBones(bpy.types.Operator):
    """Toggle visibility of deform bones only"""
    bl_idname = "wpt.toggle_deform_bones"
    bl_label = "Deform Bones Only"
    bl_description = "Show only deform bones (DEF/deform) in the active armature"
    bl_options = {"REGISTER", "UNDO"}

    def find_armature(self, context):
        """Find armature from active object, modifiers, parent, or scene"""
        obj = context.active_object
        
        # If active object is armature, use it
        if obj and obj.type == 'ARMATURE':
            return obj
            
        # If active object is mesh, check its armature modifier
        if obj and obj.type == 'MESH':
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    return mod.object
            
            # Check if mesh is parented to armature
            if obj.parent and obj.parent.type == 'ARMATURE':
                return obj.parent
        
        # Fallback: find any armature in scene
        for scene_obj in context.scene.objects:
            if scene_obj.type == 'ARMATURE':
                return scene_obj
                
        return None

    def execute(self, context):
        # Find armature - check active object, modifiers, parent, or scene
        armature_obj = self.find_armature(context)
        if not armature_obj:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}
            
        arm = armature_obj.data
        collections = getattr(arm, "collections_all", None)
        
        if collections:
            # Hide all collections first
            for col in collections:
                col.is_visible = False
            # Show DEF (Rigify) and Deform (Auto-Rig Pro) collections
            deform_collections = ["DEF", "Deform", "deform"]
            found_any = False
            for col_name in deform_collections:
                if col_name in collections:
                    collections[col_name].is_visible = True
                    found_any = True
            
            if not found_any:
                self.report({'INFO'}, "No deform bone collections found")
        else:
            # Fallback: hide bones by name
            deform_keywords = ["DEF", "deform", "Deform"]
            for bone in arm.bones:
                bone.hide = not any(keyword in bone.name for keyword in deform_keywords)
                
        return {'FINISHED'}


class WPT_OT_ShowAllBones(bpy.types.Operator):
    """Show controller and deform bones only"""
    bl_idname = "wpt.show_all_bones"
    bl_label = "Show Controller Bones"
    bl_description = "Show controller and deform bone collections (Main, DEF, Deform)"
    bl_options = {"REGISTER", "UNDO"}

    def find_armature(self, context):
        """Find armature from active object, modifiers, parent, or scene"""
        obj = context.active_object
        
        # If active object is armature, use it
        if obj and obj.type == 'ARMATURE':
            return obj
            
        # If active object is mesh, check its armature modifier
        if obj and obj.type == 'MESH':
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    return mod.object
            
            # Check if mesh is parented to armature
            if obj.parent and obj.parent.type == 'ARMATURE':
                return obj.parent
        
        # Fallback: find any armature in scene
        for scene_obj in context.scene.objects:
            if scene_obj.type == 'ARMATURE':
                return scene_obj
                
        return None

    def execute(self, context):
        # Find armature - check active object, modifiers, parent, or scene
        armature_obj = self.find_armature(context)
        if not armature_obj:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}
        
        arm = armature_obj.data
        collections = getattr(arm, "collections_all", None)
        
        if collections:
            # Hide all collections first
            for col in collections:
                col.is_visible = False
            
            found_collections = []
            
            # Show all collections that contain controller bones
            # Look for collections with IK, FK, Tweak, or other controller keywords
            for col in collections:
                col_name = col.name
                # Check if it's a controller collection (not MCH, ORG, or DEF only)
                is_controller = (
                    "IK" in col_name or
                    "FK" in col_name or 
                    "Tweak" in col_name or
                    col_name in ["Root", "Torso", "Fingers", "Face", "Extra"] or
                    ("." in col_name and not col_name.startswith(("MCH", "ORG"))) or
                    col_name in ["Main", "Secondary"]  # Auto-Rig Pro
                )
                
                # Always show DEF collections for deform bones
                is_deform = col_name == "DEF" or "DEF" in col_name
                
                if is_controller or is_deform:
                    col.is_visible = True
                    found_collections.append(col_name)
            
            if found_collections:
                self.report({'INFO'}, f"Showing collections: {', '.join(found_collections[:5])}{'...' if len(found_collections) > 5 else ''}")
            else:
                # Fallback: show all collections if no recognized ones found
                for col in collections:
                    col.is_visible = True
                self.report({'INFO'}, "No recognized rig collections found, showing all")
        else:
            # Fallback: show controller bones by name for older rigs
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
    """Apply current pose as rest pose"""
    bl_idname = "wpt.apply_rest_pose"
    bl_label = "Apply as Rest Pose"
    bl_description = "Apply the current pose as the new rest pose for the active armature"
    bl_options = {"REGISTER", "UNDO"}

    def find_armature(self, context):
        """Find armature from active object, modifiers, parent, or scene"""
        obj = context.active_object
        
        # If active object is armature, use it
        if obj and obj.type == 'ARMATURE':
            return obj
            
        # If active object is mesh, check its armature modifier
        if obj and obj.type == 'MESH':
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    return mod.object
            
            # Check if mesh is parented to armature
            if obj.parent and obj.parent.type == 'ARMATURE':
                return obj.parent
        
        # Fallback: find any armature in scene
        for scene_obj in context.scene.objects:
            if scene_obj.type == 'ARMATURE':
                return scene_obj
                
        return None

    @classmethod
    def poll(cls, context):
        # Must be in pose mode, and have access to an armature
        if context.mode != 'POSE':
            return False
        obj = context.active_object
        return obj and obj.type == 'ARMATURE'

    def execute(self, context):
        armature_obj = self.find_armature(context)
        if not armature_obj:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}
            
        try:
            # Make sure armature is active for the operation
            prev_active = context.active_object
            context.view_layer.objects.active = armature_obj
            
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.armature_apply(selected=False)
            bpy.ops.object.mode_set(mode='POSE')
            
            # Restore previous active object if it was different
            if prev_active != armature_obj:
                context.view_layer.objects.active = prev_active
                
            self.report({'INFO'}, "Rest pose applied successfully")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to apply rest pose: {str(e)}")
            return {'CANCELLED'}


class WPT_OT_TogglePoseRest(bpy.types.Operator):
    """Toggle between posed mesh (armature modifier on) and rest position (armature modifier off) for all meshes"""
    bl_idname = "wpt.toggle_pose_rest"
    bl_label = "Toggle Pose/Rest"
    bl_description = "Toggle armature modifiers on all meshes to switch between posed and rest position"
    bl_options = {"REGISTER", "UNDO"}

    def find_all_meshes_with_armature(self, context):
        """Find all mesh objects with armature modifiers"""
        meshes_with_armature = []
        
        for scene_obj in context.scene.objects:
            if scene_obj.type == 'MESH':
                for mod in scene_obj.modifiers:
                    if mod.type == 'ARMATURE':
                        meshes_with_armature.append((scene_obj, mod))
                        break  # Only need the first armature modifier per mesh
                        
        return meshes_with_armature

    def execute(self, context):
        meshes_with_armature = self.find_all_meshes_with_armature(context)
        
        if not meshes_with_armature:
            self.report({'WARNING'}, "No meshes with armature modifiers found")
            return {'CANCELLED'}

        # Determine current state based on first mesh
        first_mesh, first_mod = meshes_with_armature[0]
        current_state = first_mod.show_viewport
        new_state = not current_state
        
        # Apply the same toggle to all meshes
        affected_count = 0
        for mesh_obj, armature_mod in meshes_with_armature:
            armature_mod.show_viewport = new_state
            armature_mod.show_render = new_state
            affected_count += 1
        
        if new_state:
            self.report({'INFO'}, f"Showing posed position for {affected_count} mesh(es) (armature modifiers ON)")
        else:
            self.report({'INFO'}, f"Showing rest position for {affected_count} mesh(es) (armature modifiers OFF)")
            
        return {'FINISHED'}


class WPT_OT_GradientAddSubtract(bpy.types.Operator):
    """Switch to gradient tool with add/subtract mode"""
    bl_idname = "wpt.gradient_add_subtract"
    bl_label = "Gradient Add/Subtract"
    bl_description = "Switch to gradient tool and toggle between add and subtract modes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == 'PAINT_WEIGHT'

    def execute(self, context):
        # Switch to gradient tool
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.gradient")
        except:
            self.report({'WARNING'}, "Could not switch to gradient tool")
            return {'CANCELLED'}
        
        # Get current brush settings
        brush = context.tool_settings.weight_paint.brush
        if not brush:
            self.report({'WARNING'}, "No brush found")
            return {'CANCELLED'}
        
        # Toggle between ADD and SUB modes
        if brush.blend == 'ADD':
            brush.blend = 'SUB'
            mode_name = "Subtract"
        else:
            brush.blend = 'ADD'
            mode_name = "Add"
        
        self.report({'INFO'}, f"Gradient tool: {mode_name} mode")
        return {'FINISHED'}


class WPT_OT_ToggleBonesOverlay(bpy.types.Operator):
    """Toggle bone overlay visibility"""
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
    """Save current bone collection visibility state as named preset"""
    bl_idname = "wpt.save_bone_collections"
    bl_label = "Save Preset"
    bl_description = "Save current bone collection visibility state as a named preset"
    bl_options = {"REGISTER", "UNDO"}

    def find_armature(self, context):
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

    def execute(self, context):
        armature_obj = self.find_armature(context)
        if not armature_obj:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}
        arm = armature_obj.data
        collections = getattr(arm, "collections_all", None)
        if not collections:
            self.report({'WARNING'}, "No bone collections found in armature")
            return {'CANCELLED'}
        visible_collections = []
        for col in collections:
            if col.is_visible:
                visible_collections.append(col.name)
        if not visible_collections:
            self.report({'WARNING'}, "No visible bone collections to save")
            return {'CANCELLED'}
        
        # Get unique preset name
        props = context.scene.bone_collection_props
        unique_name = get_unique_pose_name(props.preset_name, context.scene.bone_collection_presets)
        
        # Save to scene collection
        new_preset = context.scene.bone_collection_presets.add()
        new_preset.name = unique_name
        import json
        new_preset.collection_data = json.dumps(visible_collections)
        
        collection_names = ", ".join(visible_collections[:3])
        if len(visible_collections) > 3:
            collection_names += f" and {len(visible_collections) - 3} more"
        self.report({'INFO'}, f"Saved preset '{unique_name}': {collection_names}")
        return {'FINISHED'}


class WPT_OT_RestoreBoneCollections(bpy.types.Operator):
    """Restore selected bone collection preset"""
    bl_idname = "wpt.restore_bone_collections"
    bl_label = "Load Preset"
    bl_description = "Restore selected bone collection preset"
    bl_options = {"REGISTER", "UNDO"}

    def find_armature(self, context):
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

    def execute(self, context):
        armature_obj = self.find_armature(context)
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
        import json
        try:
            stored_collections = json.loads(preset.collection_data)
        except:
            self.report({'ERROR'}, f"Failed to load preset '{preset.name}'")
            return {'CANCELLED'}
        
        # Hide all collections first
        for col in collections:
            col.is_visible = False
        
        # Show only stored collections
        restored_count = 0
        for col_name in stored_collections:
            if col_name in collections:
                collections[col_name].is_visible = True
                restored_count += 1
        
        if restored_count == 0:
            self.report({'WARNING'}, f"None of the collections in preset '{preset.name}' found in current armature")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Loaded preset '{preset.name}': {restored_count}/{len(stored_collections)} collections")
        return {'FINISHED'}


class WPT_OT_RenameBoneCollectionPreset(bpy.types.Operator):
    """Rename a bone collection preset"""
    bl_idname = "wpt.rename_bone_collection_preset"
    bl_label = "Rename Preset"
    bl_description = "Rename the selected bone collection preset"
    bl_options = {"REGISTER", "UNDO"}
    
    new_name: StringProperty(
        name="New Name",
        description="New name for the preset",
        default=""
    )
    
    def invoke(self, context, event):
        props = context.scene.bone_collection_props
        if not context.scene.bone_collection_presets:
            self.report({'ERROR'}, "No presets to rename")
            return {'CANCELLED'}
        
        selected_index = int(props.selected_preset)
        if selected_index < 0 or selected_index >= len(context.scene.bone_collection_presets):
            self.report({'ERROR'}, "Invalid preset selection")
            return {'CANCELLED'}
        
        # Set the default new name to the current name
        self.new_name = context.scene.bone_collection_presets[selected_index].name
        
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        props = context.scene.bone_collection_props
        selected_index = int(props.selected_preset)
        
        if selected_index < 0 or selected_index >= len(context.scene.bone_collection_presets):
            self.report({'ERROR'}, "Invalid preset selection")
            return {'CANCELLED'}
        
        # Get unique name
        unique_name = get_unique_pose_name(self.new_name, context.scene.bone_collection_presets)
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
        
        # Reset the selected preset if needed
        if len(context.scene.bone_collection_presets) > 0:
            props.selected_preset = "0"
        
        self.report({'INFO'}, f"Deleted preset '{preset_name}'")
        return {'FINISHED'}


class WPT_OT_CutHalfMesh(bpy.types.Operator):
    """Cut the mesh in half along the X-axis for symmetrical weight painting"""
    bl_idname = "wpt.cut_half_mesh"
    bl_label = "Cut Half"
    bl_description = "Cut the mesh in half along the X-axis for symmetrical weight painting"
    bl_options = {"REGISTER", "UNDO"}

    axis: bpy.props.EnumProperty(
        name="Mirror Axis",
        items=[
            ('X', "X-Axis", "Cut along X axis (keep +X side)"),
            ('Y', "Y-Axis", "Cut along Y axis (keep +Y side)"),
            ('Z', "Z-Axis", "Cut along Z axis (keep +Z side)"),
        ],
        default='X'
    )
    
    keep_positive: bpy.props.BoolProperty(
        name="Keep Positive Side",
        description="Keep the positive side of the axis (+X, +Y or +Z)",
        default=True
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
        
        # Store original mode
        original_mode = obj.mode
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Get desired axis index (0=X, 1=Y, 2=Z)
        axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[self.axis]
        
        # Create the selection
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.context.tool_settings.mesh_select_mode = (True, True, True)
        bpy.ops.mesh.bisect(plane_co=(0, 0, 0), 
                           plane_no=(1 if axis_idx == 0 else 0, 
                                    1 if axis_idx == 1 else 0, 
                                    1 if axis_idx == 2 else 0), 
                           clear_inner=not self.keep_positive, 
                           clear_outer=self.keep_positive)
        
        # Apply the cut
        bpy.ops.mesh.select_all(action='DESELECT')
        
        # Return to original mode
        bpy.ops.object.mode_set(mode=original_mode)
        
        self.report({'INFO'}, f"Cut mesh along {self.axis}-axis, keeping {'positive' if self.keep_positive else 'negative'} side")
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
        default='X'
    )
    
    mirror_weights: bpy.props.BoolProperty(
        name="Mirror Weights",
        description="Also mirror vertex weights across the selected axis",
        default=True
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
        
        # Check if mirror already exists
        for mod in obj.modifiers:
            if mod.type == 'MIRROR':
                self.report({'WARNING'}, "Mirror modifier already exists. Adding another one.")
                break
        
        # Add mirror modifier
        mirror = obj.modifiers.new(name="Mirror", type='MIRROR')
        
        # Set axis
        if self.axis == 'X':
            mirror.use_axis[0] = True
            mirror.use_axis[1] = False
            mirror.use_axis[2] = False
        elif self.axis == 'Y':
            mirror.use_axis[0] = False
            mirror.use_axis[1] = True
            mirror.use_axis[2] = False
        else:  # Z
            mirror.use_axis[0] = False
            mirror.use_axis[1] = False
            mirror.use_axis[2] = True
            
        # Set mirror weights
        mirror.use_mirror_vertex_groups = self.mirror_weights
        
        # Move mirror to the top of the stack (before armature)
        if len(obj.modifiers) > 1:
            for i in range(len(obj.modifiers)-1):
                bpy.ops.object.modifier_move_up(modifier="Mirror")
        
        self.report({'INFO'}, f"Added mirror modifier along {self.axis}-axis{' with weight mirroring' if self.mirror_weights else ''}")
        return {'FINISHED'}
        

# ===== PIE MENU =====

class WPT_MT_BrushPieMenu(bpy.types.Menu):
    """Weight Paint Brush Pie Menu"""
    bl_label = "Weight Paint Brushes"
    bl_idname = "WPT_MT_brush_pie_menu"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        
        # Draw brush (MIX mode) - WEST
        op = pie.operator("wpt.set_brush_mode", text="Draw", icon='BRUSH_DATA')
        op.mode = "MIX"
        op.tool = "builtin_brush.Draw"
        
        # Add brush - EAST
        op = pie.operator("wpt.set_brush_mode", text="Add", icon='ADD')
        op.mode = "ADD"
        op.tool = "builtin_brush.Draw"
        
        # Subtract brush - SOUTH
        op = pie.operator("wpt.set_brush_mode", text="Subtract", icon='REMOVE')
        op.mode = "SUB"
        op.tool = "builtin_brush.Draw"
        
        # Smooth brush - NORTH
        op = pie.operator("wpt.switch_tool", text="Smooth", icon='MOD_SMOOTH')
        op.tool_name = "builtin_brush.Smooth"
        
        # Blur brush - NORTH-WEST
        op = pie.operator("wpt.switch_tool", text="Blur", icon='MATSHADERBALL')
        op.tool_name = "builtin_brush.Blur"
        
        # Average brush - NORTH-EAST  
        op = pie.operator("wpt.switch_tool", text="Average", icon='FORCE_HARMONIC')
        op.tool_name = "builtin_brush.Average"
        
        # Gradient tool - SOUTH-WEST
        op = pie.operator("wpt.switch_tool", text="Gradient", icon='IPO_LINEAR')
        op.tool_name = "builtin.gradient"
        
        # Sample weight - SOUTH-EAST
        pie.operator("paint.weight_sample", text="Sample Weight", icon='EYEDROPPER')


# ===== UI PANELS =====


class WPT_OT_FloodSmooth(bpy.types.Operator):
    """Flood smooth weights on selected vertices"""
    bl_idname = "wpt.flood_smooth"
    bl_label = "Flood Smooth"
    bl_options = {'REGISTER', 'UNDO'}
    
    iterations: bpy.props.IntProperty(
        name="Iterations", 
        default=5, 
        min=1, 
        description="Number of smoothing iterations"
    )
    strength: bpy.props.FloatProperty(
        name="Strength", 
        default=1.0, 
        min=0.0, 
        max=1.0, 
        description="Smoothing strength"
    )
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and 
                context.mode == 'PAINT_WEIGHT')
    
    def execute(self, context):
        obj = context.active_object
        
        # Ensure paint mask is enabled to respect selection
        original_mask_mode = obj.data.use_paint_mask_vertex
        obj.data.use_paint_mask_vertex = True
        
        try:
            bpy.ops.object.vertex_group_smooth(
                group_select_mode='ALL',
                repeat=self.iterations,
                factor=self.strength
            )
            self.report({'INFO'}, f"Flood Smoothed (Iter: {self.iterations})")
        except Exception as e:
            self.report({'ERROR'}, f"Flood Smooth Failed: {str(e)}")
            return {'CANCELLED'}
        finally:
            # Restore original mask mode (optional, generally keeping it on is helpful)
            # obj.data.use_paint_mask_vertex = original_mask_mode 
            # Commented out: User likely wants to keep the mask on if they are working with selection
            pass
            
        return {'FINISHED'}

class WPT_PT_MainPanel(bpy.types.Panel):
    """Main weight paint tools panel"""
    bl_label = 'Weight Paint Tools'
    bl_idname = 'WPT_PT_main_panel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Weight Paint'
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return True

    def draw_header(self, context):
        layout = self.layout
        layout.label(icon='MOD_VERTEX_WEIGHT')

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        # Setup section (Restored to main panel)
        box = layout.box()
        box.label(text="Setup", icon='SETTINGS')
        
        if obj and obj.type == 'MESH':
            # Fast access to weight paint setup
            box.operator('wpt.setup_weight_paint', icon='MOD_ARMATURE')
            
            # Symmetry Tool - Compacted
            box.separator()
            row = box.row(align=True)
            row.label(text="Symmetry:", icon='MOD_MIRROR')
            row.operator("wpt.cut_half_mesh", text="Cut Half", icon='SCULPTMODE_HLT')
            row.operator("wpt.add_mirror", text="Add Mirror", icon='MOD_MIRROR')
        else:
            box.label(text="Select a mesh object", icon='INFO')

        # Note: Paint tools and bone tools are now in separate sub-panels


class WPT_PT_PaintTools(bpy.types.Panel):
    """Weight paint tools sub-panel"""
    bl_label = 'Paint Tools'
    bl_idname = 'WPT_PT_paint_tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Weight Paint'
    bl_parent_id = 'WPT_PT_main_panel'
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return context.mode == 'PAINT_WEIGHT'

    def draw(self, context):
        layout = self.layout
        
        # Quick tool switches
        row = layout.row(align=True)
        op = row.operator('wpt.switch_tool', text='Draw', icon='BRUSH_DATA')
        op.tool_name = "builtin_brush.Draw"
        op = row.operator('wpt.switch_tool', text='Gradient', icon='IPO_LINEAR')
        op.tool_name = "builtin.gradient"
        
        # Weight value
        scene = context.scene
        if hasattr(scene.tool_settings, 'unified_paint_settings'):
            layout.prop(scene.tool_settings.unified_paint_settings, 'weight', 
                       text='Weight', slider=True)
        
        layout.separator()
        row = layout.row(align=True)
        row.operator("wpt.flood_smooth", text="Flood Smooth Selection", icon='BRUSH_BLUR')
        
        # Mirror weights
        layout.separator()
        col = layout.column(align=True)
        col.label(text="Mirror Weights:")
        row = col.row(align=True)
        
        for axis in ['X', 'Y', 'Z']:
            op = row.operator('wpt.mirror_weights', text=axis)
            op.axis = axis
            
        # Brush Pie Menu hint
        layout.separator()
        layout.label(text="Press Q for brush menu", icon='INFO')


class WPT_PT_BoneTools(bpy.types.Panel):
    """Bone visibility tools sub-panel"""
    bl_label = 'Bone Visibility'
    bl_idname = 'WPT_PT_bone_tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Weight Paint'
    bl_parent_id = 'WPT_PT_main_panel'
    bl_order = 2

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            return False
        # Works with armatures directly or meshes that have armature modifiers/parents
        if obj.type == 'ARMATURE':
            return True
        if obj.type == 'MESH':
            # Check for armature modifier
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    return True
            # Check for armature parent
            if obj.parent and obj.parent.type == 'ARMATURE':
                return True
        # Fallback: check if any armature exists in scene
        return any(scene_obj.type == 'ARMATURE' for scene_obj in context.scene.objects)

    def draw(self, context):
        layout = self.layout
        
        # Bone visibility controls
        row = layout.row(align=True)
        row.operator("wpt.toggle_deform_bones", text="Deform Only", icon='BONE_DATA')
        row.operator("wpt.show_all_bones", text="Show All", icon='GROUP_BONE')
        
        # Collection presets
        box = layout.box()
        box.label(text="Collection Presets:", icon='PRESET')
        
        props = context.scene.bone_collection_props
        
        # Preset name input
        box.prop(props, "preset_name", text="Name")
        
        # Save preset button
        box.operator("wpt.save_bone_collections", icon='ADD')
        
        # Preset management
        if context.scene.bone_collection_presets:
            box.separator()
            
            # Preset selector and controls
            row = box.row(align=True)
            row.prop(props, "selected_preset", text="")
            row.operator("wpt.rename_bone_collection_preset", text="", icon='GREASEPENCIL')
            row.operator("wpt.delete_bone_collection_preset", text="", icon='X')
            
            # Load preset button
            box.operator("wpt.restore_bone_collections", icon='IMPORT')
            
            # Info
            box.label(text=f"Total Presets: {len(context.scene.bone_collection_presets)}", icon='INFO')
        else:
            box.label(text="No presets saved", icon='INFO')
        
        # Rest pose tools
        if context.mode == 'POSE':
            layout.separator()
            layout.operator('wpt.apply_rest_pose', icon='ARMATURE_DATA')
        
        # Toggle pose/rest
        layout.separator()
        layout.operator("wpt.toggle_pose_rest", text="Toggle Pose/Rest", icon='MODIFIER_ON')


class WPT_PT_DisplayOptions(bpy.types.Panel):
    """Display options sub-panel"""
    bl_label = 'Display Options'
    bl_idname = 'WPT_PT_display_options'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Weight Paint'
    bl_parent_id = 'WPT_PT_main_panel'
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        
        # Vertex group selection
        if context.mode == 'PAINT_WEIGHT':
            scene = context.scene
            layout.prop(scene.tool_settings, 'vertex_group_user', 
                       text="Restrict to Group")
        
        # Overlay options
        if hasattr(context, 'space_data') and hasattr(context.space_data, 'overlay'):
            overlay = context.space_data.overlay
            layout.prop(overlay, 'show_wireframes', text="Show Wireframe")

        # Show Bones in Front
        armature = get_active_armature(context)
        if armature:
            layout.prop(armature, 'show_in_front', text="Show Bones In Front")


# ===== POSE SLIDER FUNCTIONALITY =====

class PoseData(PropertyGroup):
    """Property group for storing pose data"""
    name: StringProperty(name="Pose Name")
    pose_data: StringProperty(name="Pose Data")

class BoneCollectionPreset(PropertyGroup):
    """Property group for storing bone collection preset data"""
    name: StringProperty(name="Preset Name")
    collection_data: StringProperty(name="Collection Data")

class PoseSliderProperties(PropertyGroup):
    """Properties for the pose slider"""
    pose_factor: FloatProperty(
        name="Pose Factor",
        description="Blend between rest pose (0.0) and selected pose (1.0)",
        default=0.0,
        min=0.0,
        max=1.0,
        update=lambda self, context: update_pose_blend(self, context)
    )
    
    pose_name: StringProperty(
        name="Pose Name",
        description="Name for the new pose",
        default="NewPose"
    )
    
    selected_pose: EnumProperty(
        name="Selected Pose",
        description="Select the pose to blend with",
        items=lambda self, context: [(str(i), pose.name, "") for i, pose in enumerate(context.scene.pose_collection)],
        update=lambda self, context: update_pose_blend(self, context)
    )
    
    rename_index: IntProperty(
        name="Rename Index",
        description="Index of pose to rename",
        default=-1
    )

class BoneCollectionProperties(PropertyGroup):
    """Properties for bone collection presets"""
    preset_name: StringProperty(
        name="Preset Name",
        description="Name for the new bone collection preset",
        default="New Preset"
    )
    
    selected_preset: EnumProperty(
        name="Selected Preset",
        description="Select the bone collection preset to load",
        items=lambda self, context: [(str(i), preset.name, "") for i, preset in enumerate(context.scene.bone_collection_presets)]
    )

# ===== POSE SLIDER HELPER FUNCTIONS =====

def get_unique_pose_name(base_name, pose_collection):
    """Generate a unique pose name by adding .001, .002, etc if needed"""
    # Check if the base name already exists
    existing_names = [pose.name for pose in pose_collection]
    
    if base_name not in existing_names:
        return base_name
    
    # Extract base name and number if it already has a suffix
    import re
    match = re.match(r"(.+)\.(\d{3})$", base_name)
    if match:
        base = match.group(1)
        num = int(match.group(2))
    else:
        base = base_name
        num = 0
    
    # Find the next available number
    while True:
        num += 1
        new_name = f"{base}.{num:03d}"
        if new_name not in existing_names:
            return new_name

def get_active_armature(context):
    """Get the active armature object regardless of current mode"""
    obj = context.active_object
    if obj and obj.type == 'ARMATURE':
        return obj
    if obj and hasattr(obj, 'data') and hasattr(obj.data, 'bones'):
        return obj
    for obj in context.selected_objects:
        if obj.type == 'ARMATURE':
            return obj
    if context.mode == 'PAINT_WEIGHT':
        obj = context.active_object
        if obj and obj.type == 'MESH':
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    return mod.object
    for obj in context.scene.objects:
        if obj.type == 'ARMATURE':
            return obj
    return None

def store_pose_data(armature_obj):
    """Store current pose data as JSON string"""
    pose_data = {}
    for bone in armature_obj.pose.bones:
        pose_data[bone.name] = {
            'location': list(bone.location),
            'rotation_quaternion': list(bone.rotation_quaternion) if bone.rotation_mode == 'QUATERNION' else None,
            'rotation_euler': list(bone.rotation_euler) if bone.rotation_mode != 'QUATERNION' else None,
            'scale': list(bone.scale),
            'rotation_mode': bone.rotation_mode
        }
    return json.dumps(pose_data)

def apply_pose_data(armature_obj, pose_data_json, factor=1.0):
    """Apply stored pose data with optional blending factor"""
    try:
        pose_data = json.loads(pose_data_json)
    except:
        return False
    
    for bone_name, bone_data in pose_data.items():
        if bone_name in armature_obj.pose.bones:
            bone = armature_obj.pose.bones[bone_name]
            
            # Store original transform for blending
            orig_loc = bone.location.copy()
            orig_rot_quat = bone.rotation_quaternion.copy() if bone.rotation_mode == 'QUATERNION' else None
            orig_rot_euler = bone.rotation_euler.copy() if bone.rotation_mode != 'QUATERNION' else None
            orig_scale = bone.scale.copy()
            
            # Set target values
            if bone_data.get('rotation_mode'):
                bone.rotation_mode = bone_data['rotation_mode']
            
            target_loc = Vector(bone_data['location'])
            target_scale = Vector(bone_data['scale'])
            
            if bone.rotation_mode == 'QUATERNION' and bone_data.get('rotation_quaternion'):
                target_rot = Quaternion(bone_data['rotation_quaternion'])
                # Blend rotations using slerp for quaternions
                bone.rotation_quaternion = orig_rot_quat.slerp(target_rot, factor)
            elif bone.rotation_mode != 'QUATERNION' and bone_data.get('rotation_euler'):
                target_rot = Vector(bone_data['rotation_euler'])
                bone.rotation_euler = orig_rot_euler.lerp(target_rot, factor)
            
            # Blend location and scale
            bone.location = orig_loc.lerp(target_loc, factor)
            bone.scale = orig_scale.lerp(target_scale, factor)
    
    return True

def is_rigify_or_autopro_rig(armature):
    """Check if the armature is a Rigify or Auto Pro rig"""
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

def save_current_pose(armature):
    """Save the current pose of the armature"""
    if not armature or armature.type != 'ARMATURE':
        return None
    pose_data = {}
    for bone in armature.pose.bones:
        bone_data = {
            'location': list(bone.location),
            'scale': list(bone.scale),
            'rotation_mode': bone.rotation_mode
        }
        if bone.rotation_mode == 'QUATERNION':
            bone_data['rotation_quaternion'] = list(bone.rotation_quaternion)
        else:
            bone_data['rotation_euler'] = list(bone.rotation_euler)
        pose_data[bone.name] = bone_data
    return pose_data

def load_pose_data_from_json(json_string):
    """Load pose data from JSON string"""
    if not json_string:
        return None
    try:
        return json.loads(json_string)
    except json.JSONDecodeError:
        return None

def save_pose_data_to_json(pose_data):
    """Save pose data to JSON string"""
    if not pose_data:
        return ""
    try:
        return json.dumps(pose_data)
    except:
        return ""

def apply_pose(armature, pose_data, factor=1.0):
    """Apply pose data to armature with blending factor"""
    if not armature or not pose_data:
        return
    for bone_name, bone_data in pose_data.items():
        if bone_name in armature.pose.bones:
            bone = armature.pose.bones[bone_name]
            target_loc = Vector(bone_data['location'])
            rest_loc = Vector((0, 0, 0))
            blended_loc = rest_loc.lerp(target_loc, factor)
            bone.location = blended_loc
            if bone_data['rotation_mode'] == 'QUATERNION' and 'rotation_quaternion' in bone_data:
                target_rot = Quaternion(bone_data['rotation_quaternion'])
                rest_rot = Quaternion((1, 0, 0, 0))
                current_rot = rest_rot.slerp(target_rot, factor)
                bone.rotation_quaternion = current_rot
            elif 'rotation_euler' in bone_data:
                target_rot = bone_data['rotation_euler']
                rest_euler = [0, 0, 0]
                for i in range(3):
                    bone.rotation_euler[i] = rest_euler[i] * (1 - factor) + target_rot[i] * factor
            target_scale = Vector(bone_data['scale'])
            rest_scale = Vector((1, 1, 1))
            blended_scale = rest_scale.lerp(target_scale, factor)
            bone.scale = blended_scale

def update_pose_blend(self, context):
    """Update pose blending when slider changes"""
    if not context.scene.pose_collection:
        return
    
    selected_index = int(self.selected_pose) if self.selected_pose else 0
    if selected_index >= len(context.scene.pose_collection):
        return
    
    armature_obj = get_active_armature(context)
    if not armature_obj:
        return
    
    # Get pose data and apply it
    pose_data_str = context.scene.pose_collection[selected_index].pose_data
    pose_data = load_pose_data_from_json(pose_data_str)
    if pose_data:
        apply_pose(armature_obj, pose_data, self.pose_factor)
        context.view_layer.update()

# ===== POSE SLIDER OPERATORS =====

class POSE_OT_save_pose(bpy.types.Operator):
    """Save the current pose"""
    bl_idname = "pose.save_pose"
    bl_label = "Save Current Pose"
    bl_description = "Save the current pose of the active armature"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        armature = get_active_armature(context)
        if not armature:
            self.report({'ERROR'}, "No armature found in scene")
            return {'CANCELLED'}
        
        props = context.scene.pose_slider_props
        
        # Validate pose name
        if not props.pose_name or props.pose_name.strip() == "":
            self.report({'ERROR'}, "Please enter a pose name")
            return {'CANCELLED'}
        
        # Get pose data using the save_current_pose function
        pose_data = save_current_pose(armature)
        if pose_data:
            # Get unique name
            unique_name = get_unique_pose_name(props.pose_name.strip(), context.scene.pose_collection)
            
            # Create new pose entry
            new_pose = context.scene.pose_collection.add()
            new_pose.name = unique_name
            new_pose.pose_data = save_pose_data_to_json(pose_data)
            
            # Update the selected pose to the newly saved one
            props.selected_pose = str(len(context.scene.pose_collection) - 1)
            
            self.report({'INFO'}, f"Saved pose: '{unique_name}' ({len(context.scene.pose_collection)} total)")
        else:
            self.report({'ERROR'}, "Failed to save pose")
            return {'CANCELLED'}
        return {'FINISHED'}

class POSE_OT_rename_pose(bpy.types.Operator):
    """Rename a saved pose"""
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
        
        unique_name = get_unique_pose_name(self.new_name, context.scene.pose_collection)
        old_name = context.scene.pose_collection[selected_index].name
        context.scene.pose_collection[selected_index].name = unique_name
        
        self.report({'INFO'}, f"Renamed pose '{old_name}' to '{unique_name}'")
        return {'FINISHED'}

class POSE_OT_delete_pose(bpy.types.Operator):
    """Delete a saved pose"""
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
    """Generate T-Pose"""
    bl_idname = "pose.generate_t_pose"
    bl_label = "Generate T-Pose"
    bl_description = "Generate a basic T-pose for the armature"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return get_active_armature(context) is not None
    
    def execute(self, context):
        armature_obj = get_active_armature(context)
        if not armature_obj:
            self.report({'ERROR'}, "No armature found")
            return {'CANCELLED'}
        
        # Reset all bones first
        for bone in armature_obj.pose.bones:
            bone.location = (0, 0, 0)
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.rotation_euler = (0, 0, 0)
            bone.scale = (1, 1, 1)
        
        # Apply T-pose logic for common bone names
        arm_keywords = ['arm', 'shoulder', 'upperarm', 'upper_arm']
        for bone in armature_obj.pose.bones:
            bone_name_lower = bone.name.lower()
            
            # Left arm bones
            if any(keyword in bone_name_lower for keyword in arm_keywords) and ('left' in bone_name_lower or '.l' in bone_name_lower):
                bone.rotation_euler = (0, 0, 1.5708)  # 90 degrees in Z
            
            # Right arm bones  
            elif any(keyword in bone_name_lower for keyword in arm_keywords) and ('right' in bone_name_lower or '.r' in bone_name_lower):
                bone.rotation_euler = (0, 0, -1.5708)  # -90 degrees in Z
        
        self.report({'INFO'}, "Generated T-pose")
        return {'FINISHED'}

class POSE_OT_reset_to_restpose(bpy.types.Operator):
    """Reset to rest pose"""
    bl_idname = "pose.reset_to_restpose"
    bl_label = "Reset to Rest"
    bl_description = "Reset all bones to rest pose"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return get_active_armature(context) is not None
    
    def execute(self, context):
        armature_obj = get_active_armature(context)
        if not armature_obj:
            self.report({'ERROR'}, "No armature found")
            return {'CANCELLED'}
        
        for bone in armature_obj.pose.bones:
            bone.location = (0, 0, 0)
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.rotation_euler = (0, 0, 0)
            bone.scale = (1, 1, 1)
        
        # Reset slider
        context.scene.pose_slider_props.pose_factor = 0.0
        
        self.report({'INFO'}, "Reset to rest pose")
        return {'FINISHED'}

class POSE_OT_apply_full_pose(bpy.types.Operator):
    """Apply selected pose at 100%"""
    bl_idname = "pose.apply_full_pose"
    bl_label = "Apply Full Pose"
    bl_description = "Apply the selected pose at 100% strength"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return (get_active_armature(context) is not None and 
                context.scene.pose_collection)
    
    def execute(self, context):
        props = context.scene.pose_slider_props
        
        if not context.scene.pose_collection:
            self.report({'ERROR'}, "No saved poses")
            return {'CANCELLED'}
        
        selected_index = int(props.selected_pose)
        if selected_index >= len(context.scene.pose_collection):
            self.report({'ERROR'}, "Invalid pose selection")
            return {'CANCELLED'}
        
        # Set slider to 100% and trigger update
        props.pose_factor = 1.0
        
        pose_name = context.scene.pose_collection[selected_index].name
        self.report({'INFO'}, f"Applied pose: {pose_name}")
        return {'FINISHED'}

class POSE_OT_modal_slider(bpy.types.Operator):
    """Modal pose slider control"""
    bl_idname = "pose.modal_slider"
    bl_label = "Pose Slider Control"
    bl_description = "Control pose blending with mouse movement"
    bl_options = {"REGISTER", "UNDO"}
    
    def __init__(self):
        self.initial_mouse_x = 0
        self.initial_factor = 0.0
        
    @classmethod
    def poll(cls, context):
        return (get_active_armature(context) is not None and 
                context.scene.pose_collection)
    
    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Calculate factor based on mouse movement
            delta = event.mouse_x - self.initial_mouse_x
            factor = self.initial_factor + (delta / 200.0)  # Sensitivity adjustment
            factor = max(0.0, min(1.0, factor))  # Clamp to 0-1
            
            context.scene.pose_slider_props.pose_factor = factor
            context.area.header_text_set(f"Pose Factor: {factor:.2f} (ESC/RMB: Cancel, LMB/Enter: Confirm)")
            
        elif event.type in {'LEFTMOUSE', 'RET'} and event.value == 'PRESS':
            context.area.header_text_set(None)
            return {'FINISHED'}
            
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            # Cancel - restore original factor
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
    """Activate pose slider control"""
    bl_idname = "pose.activate_slider_control"
    bl_label = "Activate Slider Control"
    bl_description = "Activate modal pose slider control with mouse"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        bpy.ops.pose.modal_slider('INVOKE_DEFAULT')
        return {'FINISHED'}

class POSE_OT_popup_panel(bpy.types.Operator):
    """Show pose slider popup panel"""
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
        props = context.scene.pose_slider_props
        
        layout.label(text="Pose Slider", icon='ARMATURE_DATA')
        
        if context.scene.pose_collection:
            layout.prop(props, "selected_pose", text="Pose")
            layout.prop(props, "pose_factor", text="Factor", slider=True)
            
            row = layout.row(align=True)
            row.operator("pose.reset_to_restpose", text="Reset")
            row.operator("pose.apply_full_pose", text="Apply")
        else:
            layout.label(text="No saved poses", icon='INFO')

class WPT_PT_PoseSliderPanel(bpy.types.Panel):
    """Panel for pose slider controls integrated with My Simp"""
    bl_label = "Pose Slider"
    bl_idname = "WPT_PT_pose_slider"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Weight Paint'
    bl_parent_id = 'WPT_PT_main_panel'
    bl_order = 4
    
    @classmethod
    def poll(cls, context):
        # Show panel if there's any armature in the scene
        return any(obj.type == 'ARMATURE' for obj in context.scene.objects)
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.pose_slider_props
        armature = get_active_armature(context)
        
        if not armature:
            layout.label(text="No armature found", icon='ERROR')
            layout.label(text="Select an armature")
            return
        
        # Show current armature info
        layout.label(text=f"Armature: {armature.name}", icon='ARMATURE_DATA')
        
        # Rig detection
        if is_rigify_or_autopro_rig(armature):
            layout.label(text="✓ Compatible Rig Detected", icon='CHECKMARK')
        else:
            layout.label(text="⚠ Will work with any rig", icon='INFO')
        
        # Save pose section
        layout.label(text="Pose Management:", icon='POSE_HLT')
        row = layout.row(align=True)
        row.prop(props, "pose_name", text="")
        row.operator("pose.save_pose", text="Save", icon='ADD')
        
        # Quick pose generation
        row = layout.row(align=True)
        row.operator("pose.generate_t_pose", text="T-Pose", icon='OUTLINER_OB_ARMATURE')
        row.operator("pose.reset_to_restpose", text="Reset", icon='ARMATURE_DATA')
        
        # Pose management section
        if context.scene.pose_collection:
            layout.separator()
            
            # Pose selector and controls
            row = layout.row(align=True)
            row.prop(props, "selected_pose", text="")
            row.operator("pose.rename_pose", text="", icon='GREASEPENCIL')
            row.operator("pose.delete_pose", text="", icon='X')
            
            # Pose slider
            row = layout.row(align=True)
            row.prop(props, "pose_factor", text="Factor", slider=True)
            
            # Pose blending controls
            row = layout.row(align=True)
            row.operator("pose.reset_to_restpose", text="Reset")
            row.operator("pose.apply_full_pose", text="Apply Full")
            
        else:
            layout.separator()
            layout.label(text="No poses saved. Pose armature & Save.", icon='INFO')
        
        # Mouse control hint
        layout.separator()
        layout.label(text="Hold X + Move Mouse to blend", icon='MOUSE_MMB')
# ===== REGISTRATION =====

classes = [
    WPT_AddonPreferences,
    WPT_OT_RefreshKeymaps,
    WPT_OT_RecordKey,
    WPT_OT_RecordModifiedKey,
    WPT_OT_ToggleMainPanel,
    WPT_OT_SetBrushMode,
    WPT_OT_SetupWeightPaint,
    WPT_OT_SwitchTool,
    WPT_OT_QuickSwitchMesh,
    WPT_OT_MirrorWeights,
    WPT_OT_ToggleDeformBones,
    WPT_OT_ShowAllBones,
    WPT_OT_SaveBoneCollections,
    WPT_OT_RestoreBoneCollections,
    WPT_OT_RenameBoneCollectionPreset,
    WPT_OT_DeleteBoneCollectionPreset,
    WPT_OT_ApplyRestPose,
    WPT_OT_TogglePoseRest,
    WPT_OT_GradientAddSubtract,
    WPT_OT_ToggleBonesOverlay,
    WPT_OT_CutHalfMesh,
    WPT_OT_AddMirror,
    WPT_OT_FloodSmooth,
    WPT_MT_BrushPieMenu,
    WPT_PT_MainPanel,
    WPT_PT_PaintTools,
    WPT_PT_BoneTools,
    WPT_PT_DisplayOptions,
    # Pose Slider classes
    PoseData,
    BoneCollectionPreset,
    PoseSliderProperties,
    BoneCollectionProperties,
    POSE_OT_save_pose,
    POSE_OT_rename_pose,
    POSE_OT_delete_pose,
    POSE_OT_generate_t_pose,
    POSE_OT_reset_to_restpose,
    POSE_OT_apply_full_pose,
    POSE_OT_modal_slider,
    POSE_OT_activate_slider_control,
    POSE_OT_popup_panel,
    WPT_PT_PoseSliderPanel,
]

def register():
    global _icons
   
    _icons = bpy.utils.previews.new()
    
    for cls in classes:
        bpy.utils.register_class(cls)
    
       
    # Register keymap with user preferences
    register_keymaps()
    
    # Register pose slider properties
    bpy.types.Scene.pose_slider_props = bpy.props.PointerProperty(type=PoseSliderProperties)
    bpy.types.Scene.pose_collection = bpy.props.CollectionProperty(type=PoseData)
    
    # Register bone collection preset properties
    bpy.types.Scene.bone_collection_props = bpy.props.PointerProperty(type=BoneCollectionProperties)
    bpy.types.Scene.bone_collection_presets = bpy.props.CollectionProperty(type=BoneCollectionPreset)

def unregister():
    global _icons
    if _icons:
        bpy.utils.previews.remove(_icons)
    
    # Unregister pose slider properties
    del bpy.types.Scene.pose_slider_props
    del bpy.types.Scene.pose_collection
    
    # Unregister bone collection preset properties
    del bpy.types.Scene.bone_collection_props
    del bpy.types.Scene.bone_collection_presets
    
    # Unregister keymap
    unregister_keymaps()
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()