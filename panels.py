"""Tab-rail main panel + brush pie menu + draw helpers for My Simp."""

import os

import bpy
import bpy.utils.previews
import numpy as np

from . import utils
from .ops_pose_slider import draw_pose_blend


# Module-level previews collection for colored tab icons.
_icons = None


# (tab_id, display_label, blender_icon, hover_description)
_WPT_TABS = (
    ('PAINT',   'Paint',   'BRUSH_DATA',     'Setup, brushes, weight slider, mirror weights, vertex influence inspector'),
    ('SMOOTH',  'Smooth',  'BRUSH_BLUR',     'Smart smooth & sharpen on selected verts, plus cleanup batch ops'),
    ('RIG',     'Rig',     'ARMATURE_DATA',  'Bone visibility, collection presets, pose save/blend/mirror'),
    ('TOOLS',   'Tools',   'TOOL_SETTINGS',  'Mesh symmetry (cut/mirror) and viewport display options'),
)


def _wpt_tab_meta(tab_id):
    for tid, label, icon, desc in _WPT_TABS:
        if tid == tab_id:
            return label, icon, desc
    return tab_id, 'NONE', ''


def load_tab_icons():
    """Initialise the previews collection and load tab badge PNGs from icons/."""
    global _icons
    _icons = bpy.utils.previews.new()

    icon_dir = os.path.join(os.path.dirname(__file__), 'icons')
    for tab_id, _label, _builtin, _desc in _WPT_TABS:
        png_path = os.path.join(icon_dir, f'tab_{tab_id.lower()}.png')
        if os.path.exists(png_path) and tab_id not in _icons:
            try:
                _icons.load(tab_id, png_path, 'IMAGE')
            except Exception as e:
                print(f"[WPT] Failed to load tab icon {png_path}: {e}")


def free_tab_icons():
    global _icons
    if _icons:
        bpy.utils.previews.remove(_icons)
        _icons = None


# ===== Operators ===========================================================

class WPT_OT_SetActiveTab(bpy.types.Operator):
    """Switch the active tab in the My Simp panel"""
    bl_idname = "wpt.set_active_tab"
    bl_label = "Set Active Tab"
    bl_options = {'INTERNAL'}

    tab: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, properties):
        label, _icon, desc = _wpt_tab_meta(properties.tab)
        return f"{label} — {desc}" if desc else label

    def execute(self, context):
        context.window_manager.wpt_active_tab = self.tab
        return {'FINISHED'}


class WPT_MT_BrushPieMenu(bpy.types.Menu):
    """Weight Paint Brush Pie Menu"""
    bl_label = "Weight Paint Brushes"
    bl_idname = "WPT_MT_brush_pie_menu"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        op = pie.operator("wpt.set_brush_mode", text="Draw", icon='BRUSH_DATA')
        op.mode = "MIX"
        op.tool = "builtin_brush.Draw"

        op = pie.operator("wpt.set_brush_mode", text="Add", icon='ADD')
        op.mode = "ADD"
        op.tool = "builtin_brush.Draw"

        op = pie.operator("wpt.set_brush_mode", text="Subtract", icon='REMOVE')
        op.mode = "SUB"
        op.tool = "builtin_brush.Draw"

        op = pie.operator("wpt.switch_tool", text="Smooth", icon='MOD_SMOOTH')
        op.tool_name = "builtin_brush.Smooth"

        op = pie.operator("wpt.switch_tool", text="Blur", icon='MATSHADERBALL')
        op.tool_name = "builtin_brush.Blur"

        op = pie.operator("wpt.switch_tool", text="Average", icon='FORCE_HARMONIC')
        op.tool_name = "builtin_brush.Average"

        op = pie.operator("wpt.switch_tool", text="Gradient", icon='IPO_LINEAR')
        op.tool_name = "builtin.gradient"

        pie.operator("paint.weight_sample", text="Sample Weight", icon='EYEDROPPER')


# ===== Inspector helpers ===================================================

def _get_inspect_vertex_index(context):
    """Return (mesh_obj, vertex_index). vertex_index is None if nothing is selected.

    Reads selection from any source: bmesh active in Edit, vertex .select state,
    or polygon .select state. No mask flag required.

    Uses numpy.foreach_get for vertex/poly selection scans so this stays O(n)
    in C rather than a Python loop on every panel redraw.
    """
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return None, None

    if context.mode == 'EDIT_MESH':
        try:
            import bmesh
            bm = bmesh.from_edit_mesh(obj.data)
            if bm.select_history:
                elem = bm.select_history.active
                if isinstance(elem, bmesh.types.BMVert):
                    return obj, elem.index
            for v in bm.verts:
                if v.select:
                    return obj, v.index
        except Exception:
            pass
        return obj, None

    mesh = obj.data

    n_verts = len(mesh.vertices)
    if n_verts:
        sel = np.empty(n_verts, dtype=bool)
        mesh.vertices.foreach_get('select', sel)
        if sel.any():
            return obj, int(np.argmax(sel))

    n_polys = len(mesh.polygons)
    if n_polys:
        psel = np.empty(n_polys, dtype=bool)
        mesh.polygons.foreach_get('select', psel)
        if psel.any():
            poly = mesh.polygons[int(np.argmax(psel))]
            if poly.vertices:
                return obj, poly.vertices[0]

    return obj, None


def _draw_influence_inspector(layout, context):
    """Show vertex group weights at the selected vertex with a quick 'select bone' shortcut."""
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return
    if context.mode not in {'EDIT_MESH', 'PAINT_WEIGHT'}:
        return

    _obj, vert_idx = _get_inspect_vertex_index(context)

    layout.separator()
    layout.label(text="Vertex Influences:", icon='VERTEXSEL')

    if vert_idx is None:
        layout.label(text="Select a vertex (Edit mode or paint mask)", icon='INFO')
        return

    rig = None
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            rig = mod.object
            break

    influences = []
    for vg in obj.vertex_groups:
        try:
            w = vg.weight(vert_idx)
        except RuntimeError:
            continue
        if w > 0.001:
            influences.append((vg.name, w))
    influences.sort(key=lambda x: -x[1])

    if not influences:
        layout.label(text=f"V{vert_idx}: no weights", icon='INFO')
        return

    col = layout.column(align=True)
    for name, weight in influences:
        row = col.row(align=True)
        sub = row.row()
        sub.scale_x = 0.4
        sub.label(text=f"{weight:.3f}")
        row.label(text=name)
        if rig and name in rig.data.bones:
            op = row.operator("wpt.select_bone", text="", icon='BONE_DATA')
            op.armature = rig.name
            op.bone = name


# ===== Tab draw helpers ====================================================

def _draw_paint_tab(layout, context):
    """Setup + Paint tools."""
    obj = context.active_object

    if not obj or obj.type not in {'MESH', 'ARMATURE'}:
        layout.label(text="Select a mesh or armature", icon='INFO')
        layout.prop(context.window_manager, "wpt_auto_follow_active_mesh",
                    text="Auto-Follow", icon='LINKED', toggle=True)
        return

    if obj.type == 'MESH' and context.mode != 'PAINT_WEIGHT':
        col = layout.column(align=True)
        col.scale_y = 1.4
        col.operator('wpt.setup_weight_paint', icon='MOD_ARMATURE')
    elif context.mode == 'PAINT_WEIGHT':
        row = layout.row(align=True)
        row.label(text=obj.name, icon='OBJECT_DATA')
        row.operator('wpt.quick_switch_mesh', text="", icon='FILE_REFRESH')

    layout.prop(context.window_manager, "wpt_auto_follow_active_mesh",
                text="Auto-Follow", icon='LINKED', toggle=True)

    if context.mode == 'PAINT_WEIGHT':
        layout.separator()

        row = layout.row(align=True)
        op = row.operator('wpt.switch_tool', text='Draw', icon='BRUSH_DATA')
        op.tool_name = "builtin_brush.Draw"
        op = row.operator('wpt.switch_tool', text='Gradient', icon='IPO_LINEAR')
        op.tool_name = "builtin.gradient"

        scene = context.scene
        if hasattr(scene.tool_settings, 'unified_paint_settings'):
            layout.prop(scene.tool_settings.unified_paint_settings, 'weight',
                        text='Weight', slider=True)
            row = layout.row(align=True)
            for w, label in ((0.0, '0'), (0.25, '.25'), (0.5, '.5'), (0.75, '.75'), (1.0, '1')):
                op = row.operator('wpt.set_brush_weight', text=label)
                op.weight = w

        layout.separator()
        col = layout.column(align=True)
        col.label(text="Mirror Weights:", icon='MOD_MIRROR')
        row = col.row(align=True)
        for axis in ('X', 'Y', 'Z'):
            op = row.operator('wpt.mirror_weights', text=axis)
            op.axis = axis

    _draw_influence_inspector(layout, context)


def _draw_smooth_tab(layout, context):
    """Smart Smooth + Sharpen + cleanup batch operations."""
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        layout.label(text="Select a mesh", icon='INFO')
        return
    if not obj.vertex_groups:
        layout.label(text="Mesh has no vertex groups", icon='INFO')
        return

    sm = context.scene.wpt_smooth

    layout.label(text="Smart Smooth:", icon='BRUSH_BLUR')
    col = layout.column(align=True)
    col.prop(sm, "iterations", slider=True)
    col.prop(sm, "strength", slider=True)
    row = col.row(align=True)
    row.prop(sm, "selected_only", toggle=True, text="Selected")
    row.prop(sm, "normalize", toggle=True, text="Normalize")
    col.prop(sm, "only_active_group", toggle=True, text="Active Group Only")

    row = col.row(align=True)
    op = row.operator("wpt.smart_smooth", text="Smooth", icon='BRUSH_BLUR')
    op.mode = 'SMOOTH'
    op = row.operator("wpt.smart_smooth", text="Sharpen", icon='SHARPCURVE')
    op.mode = 'SHARPEN'

    layout.separator()
    layout.label(text="Cleanup:", icon='BRUSH_DATA')
    col = layout.column(align=True)
    col.operator("object.vertex_group_normalize_all", text="Normalize All", icon='IPO_EASE_IN_OUT')
    col.operator("object.vertex_group_limit_total", text="Limit Total", icon='MOD_DECIM')
    col.operator("object.vertex_group_clean", text="Clean Zero", icon='TRASH')


def _draw_rig_tab(layout, context):
    """Bones visibility + Pose."""
    obj = context.active_object
    has_armature = False
    if obj:
        if obj.type == 'ARMATURE':
            has_armature = True
        elif obj.type == 'MESH':
            if any(mod.type == 'ARMATURE' and mod.object for mod in obj.modifiers):
                has_armature = True
            elif obj.parent and obj.parent.type == 'ARMATURE':
                has_armature = True
    if not has_armature:
        has_armature = any(o.type == 'ARMATURE' for o in context.scene.objects)
    if not has_armature:
        layout.label(text="No armature in scene", icon='INFO')
        return

    row = layout.row(align=True)
    row.operator("wpt.toggle_deform_bones", text="Deform", icon='BONE_DATA')
    row.operator("wpt.show_all_bones", text="All", icon='GROUP_BONE')

    row = layout.row(align=True)
    if context.mode == 'POSE':
        row.operator('wpt.apply_rest_pose', text="Apply Rest", icon='ARMATURE_DATA')
    row.operator("wpt.toggle_pose_rest", text="Pose / Rest", icon='MODIFIER_ON')

    layout.separator()

    col = layout.column(align=True)
    col.label(text="Collection Presets:", icon='PRESET')
    bc_props = context.scene.bone_collection_props
    row = col.row(align=True)
    row.prop(bc_props, "preset_name", text="")
    row.operator("wpt.save_bone_collections", text="", icon='ADD')

    if context.scene.bone_collection_presets:
        row = col.row(align=True)
        row.prop(bc_props, "selected_preset", text="")
        row.operator("wpt.rename_bone_collection_preset", text="", icon='GREASEPENCIL')
        row.operator("wpt.delete_bone_collection_preset", text="", icon='X')
        col.operator("wpt.restore_bone_collections", text="Load", icon='IMPORT')
    else:
        col.label(text="Save current visibility above", icon='INFO')

    layout.separator()
    layout.label(text="Pose:", icon='POSE_HLT')

    armature = utils.get_active_armature(context)
    if not armature:
        layout.label(text="Select an armature", icon='INFO')
        return

    pose_props = context.scene.pose_slider_props
    row = layout.row(align=True)
    row.prop(pose_props, "pose_name", text="")
    row.operator("pose.save_pose", text="Save", icon='ADD')

    row = layout.row(align=True)
    row.operator("pose.generate_t_pose", text="T-Pose", icon='OUTLINER_OB_ARMATURE')
    row.operator("pose.reset_to_restpose", text="Reset", icon='ARMATURE_DATA')
    row.operator("wpt.pose_mirror", text="Mirror", icon='MOD_MIRROR')

    if context.scene.pose_collection:
        draw_pose_blend(layout, context, with_management=True)


def _draw_tools_tab(layout, context):
    """Symmetry + Display."""
    obj = context.active_object

    if obj and obj.type == 'MESH':
        col = layout.column(align=True)
        col.label(text="Cut Half:", icon='SCULPTMODE_HLT')
        row = col.row(align=True)
        for axis in ('X', 'Y', 'Z'):
            op = row.operator("wpt.cut_half_mesh", text=axis)
            op.axis = axis
        col.separator()
        col.label(text="Add Mirror:", icon='MOD_MIRROR')
        row = col.row(align=True)
        for axis in ('X', 'Y', 'Z'):
            op = row.operator("wpt.add_mirror", text=axis)
            op.axis = axis
    else:
        layout.label(text="Symmetry: select a mesh", icon='INFO')

    layout.separator()
    layout.label(text="Display:", icon='OVERLAY')

    if context.mode == 'PAINT_WEIGHT':
        scene = context.scene
        layout.prop(scene.tool_settings, 'vertex_group_user', text="Restrict to Group")

    if hasattr(context, 'space_data') and hasattr(context.space_data, 'overlay'):
        overlay = context.space_data.overlay
        layout.prop(overlay, 'show_wireframes', text="Show Wireframe")

    armature = utils.get_active_armature(context)
    if armature:
        layout.prop(armature, 'show_in_front', text="Bones In Front")


_WPT_TAB_DISPATCH = {
    'PAINT':  _draw_paint_tab,
    'SMOOTH': _draw_smooth_tab,
    'RIG':    _draw_rig_tab,
    'TOOLS':  _draw_tools_tab,
}


# ===== Main panel ==========================================================

class WPT_PT_MainPanel(bpy.types.Panel):
    """Main panel with Zen UV-style tab rail on the left."""
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
        self.layout.label(icon='MOD_VERTEX_WEIGHT')

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        active = wm.wpt_active_tab

        split = layout.split(factor=0.18)

        rail = split.column(align=True)
        rail.scale_y = 2.0
        for tab_id, _label, builtin_icon, _desc in _WPT_TABS:
            kwargs = {'text': '', 'depress': (active == tab_id)}
            if _icons is not None and tab_id in _icons:
                kwargs['icon_value'] = _icons[tab_id].icon_id
            else:
                kwargs['icon'] = builtin_icon
            op = rail.operator('wpt.set_active_tab', **kwargs)
            op.tab = tab_id

        content = split.column()

        # Active tab header — colour badge + name so the user always knows where they are.
        active_label, active_builtin, _active_desc = _wpt_tab_meta(active)
        header = content.box()
        header_row = header.row(align=True)
        if _icons is not None and active in _icons:
            header_row.label(text=active_label, icon_value=_icons[active].icon_id)
        else:
            header_row.label(text=active_label, icon=active_builtin)

        draw_fn = _WPT_TAB_DISPATCH.get(active, _draw_paint_tab)
        draw_fn(content, context)


# Build the EnumProperty items that __init__.py registers on WindowManager.
def make_active_tab_items():
    return [(tid, tlabel, tdesc) for tid, tlabel, _icon, tdesc in _WPT_TABS]


classes = (
    WPT_OT_SetActiveTab,
    WPT_MT_BrushPieMenu,
    WPT_PT_MainPanel,
)
