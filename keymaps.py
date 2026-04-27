"""Keymap registration + auto-follow msgbus subscription for My Simp."""

import bpy

addon_keymaps = {}


# ===== AUTO-FOLLOW ACTIVE MESH =====
# When the user switches active object, we auto-resetup weight paint on the
# new mesh: select armature alongside, enter WP mode, preserve bone selection.

# msgbus owner is stashed on bpy.app.driver_namespace so a Reload Scripts
# (which re-imports this module) finds the same owner used by the still-alive
# subscription, and clear_by_owner() can actually clean it up.
_OWNER_KEY = "my_simp_msgbus_owner"


def _msgbus_owner():
    ns = bpy.app.driver_namespace
    owner = ns.get(_OWNER_KEY)
    if owner is None:
        owner = object()
        ns[_OWNER_KEY] = owner
    return owner


_wpt_last_rig = {"name": None, "bones": []}
_wpt_resetup_in_progress = False


def _wpt_find_rig_for_mesh(mesh_obj):
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            return mod.object
    if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
        return mesh_obj.parent
    return None


def _wpt_resetup_active_mesh():
    """Timer callback: if auto-follow is on and active is a rigged mesh, enter WP with full setup.

    Deliberately defensive: every state mutation that could fault on a
    transient context (hidden objects, deleted refs, mid-depsgraph) is wrapped
    so a single bad input doesn't propagate up and crash Blender.
    """
    global _wpt_resetup_in_progress
    try:
        ctx = bpy.context
        wm = ctx.window_manager
        if not getattr(wm, "wpt_auto_follow_active_mesh", False):
            return None

        obj = ctx.view_layer.objects.active
        if not obj or obj.type != 'MESH':
            return None
        if ctx.mode == 'PAINT_WEIGHT':
            return None
        # Hidden meshes — mode_set('WEIGHT_PAINT') raises RuntimeError on them.
        try:
            if obj.hide_get():
                return None
        except Exception:
            return None

        rig = _wpt_find_rig_for_mesh(obj)
        if not rig:
            return None
        try:
            if rig.hide_get():
                return None
        except Exception:
            return None

        bones_to_restore = []
        if _wpt_last_rig["name"] == rig.name:
            bones_to_restore = list(_wpt_last_rig["bones"])

        # Only deselect what's currently selected (and isn't our target pair).
        # The old code iterated every scene object — slow on big scenes and
        # emits a flurry of depsgraph notifications.
        try:
            for o in list(ctx.selected_objects):
                if o != obj and o != rig:
                    try:
                        o.select_set(False)
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            ctx.view_layer.objects.active = obj
            obj.select_set(True)
            rig.select_set(True)
        except Exception:
            return None

        try:
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        except RuntimeError:
            for area in ctx.screen.areas:
                if area.type == 'VIEW_3D':
                    with ctx.temp_override(area=area):
                        try:
                            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
                        except Exception:
                            pass
                    break
        except Exception:
            return None

        if bones_to_restore:
            try:
                for bone in rig.data.bones:
                    if bone.name in bones_to_restore:
                        bone.select = True
            except Exception:
                pass

        _wpt_last_rig["name"] = rig.name
        try:
            _wpt_last_rig["bones"] = [b.name for b in rig.data.bones if b.select]
        except Exception:
            _wpt_last_rig["bones"] = bones_to_restore
        return None
    except Exception:
        return None
    finally:
        _wpt_resetup_in_progress = False


def _wpt_on_active_object_change():
    """msgbus callback: defer the resetup to a timer so we don't run ops mid-notify."""
    global _wpt_resetup_in_progress
    if _wpt_resetup_in_progress:
        return
    wm = bpy.context.window_manager
    if not getattr(wm, "wpt_auto_follow_active_mesh", False):
        return
    _wpt_resetup_in_progress = True
    bpy.app.timers.register(_wpt_resetup_active_mesh, first_interval=0.0)


def register_msgbus():
    owner = _msgbus_owner()
    try:
        bpy.msgbus.clear_by_owner(owner)
    except Exception:
        pass
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, "active"),
        owner=owner,
        args=(),
        notify=_wpt_on_active_object_change,
    )


def unregister_msgbus():
    try:
        bpy.msgbus.clear_by_owner(_msgbus_owner())
    except Exception:
        pass


@bpy.app.handlers.persistent
def load_post_handler(*args):
    register_msgbus()


# ===== KEYMAP MANAGEMENT =====

def register_keymaps():
    """Register all addon keymaps from the current preference values."""
    global addon_keymaps

    unregister_keymaps()

    wm = bpy.context.window_manager
    if not wm:
        return
    kc = wm.keyconfigs.addon
    if not kc:
        return

    try:
        preferences = bpy.context.preferences.addons[__package__].preferences
    except Exception:
        return

    print("[WPT] Registering keymaps:")
    print(f"[WPT]   panel_shortcut: {preferences.panel_shortcut}")
    print(f"[WPT]   toggle_bones_shortcut: {preferences.toggle_bones_shortcut}")
    print(f"[WPT]   pie_menu_shortcut: {preferences.pie_menu_shortcut}")
    print(f"[WPT]   gradient_toggle_shortcut: {preferences.gradient_toggle_shortcut}")

    # Main panel shortcut — register in Window context for global access
    try:
        km_window = kc.keymaps.get('Window') or kc.keymaps.new(name='Window', space_type='EMPTY')
        kmi = km_window.keymap_items.new('wpt.toggle_main_panel', preferences.panel_shortcut, 'PRESS')
        addon_keymaps['main_window'] = (km_window, kmi)
        print(f"[WPT] Registered main panel with key: {preferences.panel_shortcut}")
    except Exception as e:
        print(f"[WPT] ERROR registering main panel: {e}")

    try:
        km_3d = kc.keymaps.get('3D View') or kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi_3d = km_3d.keymap_items.new('wpt.toggle_main_panel', preferences.panel_shortcut, 'PRESS')
        addon_keymaps['main_3d_view'] = (km_3d, kmi_3d)
    except Exception as e:
        print(f"[WPT] ERROR registering 3D View panel: {e}")

    # Toggle bones overlay
    try:
        km_window = kc.keymaps.get('Window') or kc.keymaps.new(name='Window', space_type='EMPTY')
        kmi_bones = km_window.keymap_items.new('wpt.toggle_bones_overlay', preferences.toggle_bones_shortcut, 'PRESS')
        addon_keymaps['toggle_bones_window'] = (km_window, kmi_bones)
    except Exception:
        pass
    try:
        km_3d = kc.keymaps.get('3D View') or kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi_bones_3d = km_3d.keymap_items.new('wpt.toggle_bones_overlay', preferences.toggle_bones_shortcut, 'PRESS')
        addon_keymaps['toggle_bones_3d_view'] = (km_3d, kmi_bones_3d)
    except Exception:
        pass

    # Weight Paint mode shortcuts
    try:
        km_wp = kc.keymaps.get('Weight Paint') or kc.keymaps.new(name='Weight Paint', space_type='EMPTY')

        kmi_pie = km_wp.keymap_items.new(
            'wm.call_menu_pie', preferences.pie_menu_shortcut, 'PRESS',
            ctrl=preferences.pie_menu_ctrl,
            alt=preferences.pie_menu_alt,
            shift=preferences.pie_menu_shift,
        )
        kmi_pie.properties.name = 'WPT_MT_brush_pie_menu'
        addon_keymaps['brush_pie'] = (km_wp, kmi_pie)

        kmi_gradient = km_wp.keymap_items.new('wpt.gradient_add_subtract', preferences.gradient_toggle_shortcut, 'PRESS')
        addon_keymaps['gradient_toggle'] = (km_wp, kmi_gradient)

        kmi_switch = km_wp.keymap_items.new(
            'wpt.quick_switch_mesh', preferences.quick_switch_mesh_shortcut, 'PRESS',
            ctrl=preferences.quick_switch_mesh_ctrl,
            alt=preferences.quick_switch_mesh_alt,
            shift=preferences.quick_switch_mesh_shift,
        )
        addon_keymaps['quick_switch_mesh'] = (km_wp, kmi_switch)
    except Exception as e:
        print(f"[WPT] ERROR registering WP keymaps: {e}")

    try:
        km_3d = kc.keymaps.get('3D View') or kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi_switch_3d = km_3d.keymap_items.new(
            'wpt.quick_switch_mesh', preferences.quick_switch_mesh_shortcut, 'PRESS',
            ctrl=preferences.quick_switch_mesh_ctrl,
            alt=preferences.quick_switch_mesh_alt,
            shift=preferences.quick_switch_mesh_shift,
        )
        addon_keymaps['quick_switch_mesh_3d'] = (km_3d, kmi_switch_3d)
    except Exception as e:
        print(f"[WPT] ERROR registering quick switch mesh in 3D View: {e}")

    # Pose Slider shortcuts
    try:
        km_window = kc.keymaps.get('Window') or kc.keymaps.new(name='Window', space_type='EMPTY')
        kmi_pose_slider = km_window.keymap_items.new('pose.activate_slider_control', 'X', 'PRESS')
        addon_keymaps['pose_slider_window'] = (km_window, kmi_pose_slider)
        kmi_pose_popup = km_window.keymap_items.new('pose.popup_panel', 'P', 'PRESS')
        addon_keymaps['pose_popup_window'] = (km_window, kmi_pose_popup)
    except Exception:
        pass
    try:
        km_3d = kc.keymaps.get('3D View') or kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi_pose_slider_3d = km_3d.keymap_items.new('pose.activate_slider_control', 'X', 'PRESS')
        addon_keymaps['pose_slider_3d'] = (km_3d, kmi_pose_slider_3d)
        kmi_pose_popup_3d = km_3d.keymap_items.new('pose.popup_panel', 'P', 'PRESS')
        addon_keymaps['pose_popup_3d'] = (km_3d, kmi_pose_popup_3d)
    except Exception:
        pass


def unregister_keymaps():
    """Remove every addon keymap entry, including legacy ones."""
    global addon_keymaps

    wm = bpy.context.window_manager
    if not wm:
        return
    kc = wm.keyconfigs.addon
    if not kc:
        return

    addon_operator_ids = {
        'wpt.toggle_main_panel',
        'wpt.toggle_bones_overlay',
        'wm.call_menu_pie',
        'wpt.gradient_add_subtract',
        'wpt.quick_switch_mesh',
        'pose.activate_slider_control',
        'pose.popup_panel',
    }

    for key, (km, kmi) in addon_keymaps.items():
        try:
            if km and kmi and kmi in km.keymap_items:
                km.keymap_items.remove(kmi)
        except Exception:
            continue
    addon_keymaps.clear()

    for km in kc.keymaps:
        items_to_remove = []
        for kmi in km.keymap_items:
            if kmi.idname in addon_operator_ids:
                items_to_remove.append(kmi)
        for kmi in items_to_remove:
            try:
                km.keymap_items.remove(kmi)
            except Exception:
                continue


def update_keymaps(self, context):
    """Property update callback for shortcut prefs — defers re-registration via timer."""
    print("[WPT] update_keymaps callback triggered")

    def do_update():
        try:
            register_keymaps()
            print("[WPT] Keymaps updated successfully")
        except Exception as e:
            print(f"[WPT] Error updating keymaps: {e}")
        return None

    bpy.app.timers.register(do_update, first_interval=0.01)
