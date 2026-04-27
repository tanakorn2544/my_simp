"""Paint and weight-manipulation operators for My Simp."""

import bpy
from bpy.utils import flip_name
from mathutils.kdtree import KDTree

from . import keymaps  # for _wpt_last_rig (auto-follow state stamp)


class WPT_OT_SetBrushMode(bpy.types.Operator):
    """Set weight paint brush mode"""
    bl_idname = "wpt.set_brush_mode"
    bl_label = "Set Brush Mode"
    bl_description = "Set the weight paint brush and blend mode"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.StringProperty(name="Mode", default="MIX")
    tool: bpy.props.StringProperty(name="Tool", default="builtin_brush.Draw")

    def execute(self, context):
        try:
            bpy.ops.wm.tool_set_by_id(name=self.tool)
        except Exception:
            self.report({'WARNING'}, f"Could not switch to tool: {self.tool}")
        if (context.mode == 'PAINT_WEIGHT'
                and self.tool == "builtin_brush.Draw"
                and self.mode in ('MIX', 'ADD', 'SUB')):
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

        if mesh_obj.hide_get():
            self.report({'ERROR'}, f"Mesh '{mesh_obj.name}' is hidden — unhide before setup")
            return {'CANCELLED'}

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

        if rig.hide_get():
            self.report({'ERROR'}, f"Armature '{rig.name}' is hidden — unhide before setup")
            return {'CANCELLED'}

        for obj in context.scene.objects:
            obj.select_set(False)
        context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        rig.select_set(True)

        try:
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        except RuntimeError:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    with context.temp_override(area=area):
                        try:
                            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
                        except Exception:
                            pass
                    break

        context.window_manager.wpt_auto_follow_active_mesh = True
        keymaps._wpt_last_rig["name"] = rig.name
        keymaps._wpt_last_rig["bones"] = []

        self.report({'INFO'}, f"Setup complete: '{rig.name}' + '{mesh_obj.name}' (auto-follow on)")
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
        except Exception:
            self.report({'WARNING'}, f"Could not switch to tool: {self.tool_name}")
        return {'FINISHED'}


class WPT_OT_QuickSwitchMesh(bpy.types.Operator):
    """Re-run weight paint setup on the active mesh (manual fallback when auto-follow misses)"""
    bl_idname = "wpt.quick_switch_mesh"
    bl_label = "Refresh Weight Paint Setup"
    bl_description = "Re-select armature alongside the active mesh and re-enter Weight Paint mode"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        current_mesh = context.active_object
        if not current_mesh or current_mesh.type != 'MESH':
            self.report({'ERROR'}, "No active mesh")
            return {'CANCELLED'}

        if current_mesh.hide_get():
            self.report({'ERROR'}, f"Mesh '{current_mesh.name}' is hidden")
            return {'CANCELLED'}

        armature = None
        for mod in current_mesh.modifiers:
            if mod.type == 'ARMATURE':
                armature = mod.object
                break
        if not armature:
            self.report({'ERROR'}, "No armature found")
            return {'CANCELLED'}

        if armature.hide_get():
            self.report({'ERROR'}, f"Armature '{armature.name}' is hidden")
            return {'CANCELLED'}

        try:
            selected_bones = [b.name for b in armature.data.bones if b.select]
            bpy.ops.object.mode_set(mode='OBJECT')
            for obj in context.scene.objects:
                obj.select_set(False)
            armature.select_set(True)
            current_mesh.select_set(True)
            context.view_layer.objects.active = current_mesh
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
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
    bl_description = "Mirror active vertex group weights across the chosen axis"
    bl_options = {"REGISTER", "UNDO"}

    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[
            ('X', "X-Axis", "Mirror across X axis"),
            ('Y', "Y-Axis", "Mirror across Y axis"),
            ('Z', "Z-Axis", "Mirror across Z axis"),
        ],
        default='X',
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH'
                and context.mode == 'PAINT_WEIGHT'
                and obj.vertex_groups.active is not None)

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
            except Exception:
                pass
            self.report({'ERROR'}, f"Failed to mirror weights: {e}")
            return {'CANCELLED'}

    def symmetrize_vertex_group(self, obj, vg_name, axis='X', threshold=0.0001):
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
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.gradient")
        except Exception:
            self.report({'WARNING'}, "Could not switch to gradient tool")
            return {'CANCELLED'}
        brush = context.tool_settings.weight_paint.brush
        if not brush:
            self.report({'WARNING'}, "No brush found")
            return {'CANCELLED'}
        if brush.blend == 'ADD':
            brush.blend = 'SUB'
            mode_name = "Subtract"
        else:
            brush.blend = 'ADD'
            mode_name = "Add"
        self.report({'INFO'}, f"Gradient tool: {mode_name} mode")
        return {'FINISHED'}


class WPT_OT_FloodSmooth(bpy.types.Operator):
    """Flood smooth weights using Blender's built-in vertex_group_smooth"""
    bl_idname = "wpt.flood_smooth"
    bl_label = "Flood Smooth"
    bl_options = {'REGISTER', 'UNDO'}

    iterations: bpy.props.IntProperty(name="Iterations", default=5, min=1)
    strength: bpy.props.FloatProperty(name="Strength", default=1.0, min=0.0, max=1.0)

    @classmethod
    def poll(cls, context):
        return (context.active_object
                and context.active_object.type == 'MESH'
                and context.mode == 'PAINT_WEIGHT')

    def execute(self, context):
        obj = context.active_object
        prev_mask = obj.data.use_paint_mask_vertex
        obj.data.use_paint_mask_vertex = True
        try:
            bpy.ops.object.vertex_group_smooth(
                group_select_mode='ALL',
                repeat=self.iterations,
                factor=self.strength,
            )
            self.report({'INFO'}, f"Flood Smoothed (Iter: {self.iterations})")
        except Exception as e:
            self.report({'ERROR'}, f"Flood Smooth Failed: {e}")
            return {'CANCELLED'}
        finally:
            obj.data.use_paint_mask_vertex = prev_mask
        return {'FINISHED'}


class WPT_OT_SmartSmoothWeights(bpy.types.Operator):
    """Smart neighbor-based weight smooth/sharpen on selected vertices.

    Boundary-aware Laplacian: averages from all neighbors so smoothed verts
    blend cleanly into untouched ones. Optionally normalises per-vertex.

    mode='SMOOTH'  → lerp each weight toward neighbour mean (Laplacian)
    mode='SHARPEN' → push each weight away from neighbour mean (negative Laplacian, clamped)
    """
    bl_idname = "wpt.smart_smooth"
    bl_label = "Smart Smooth"
    bl_description = "Smooth or sharpen weights on selected vertices with iteration / strength control"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('SMOOTH', "Smooth", "Blend each weight toward its neighbours' average"),
            ('SHARPEN', "Sharpen", "Push each weight away from its neighbours' average"),
        ],
        default='SMOOTH',
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None
                and obj.type == 'MESH'
                and len(obj.vertex_groups) > 0)

    def execute(self, context):
        obj = context.active_object
        s = context.scene.wpt_smooth
        original_mode = context.mode

        if s.selected_only:
            target_indices = self._collect_selected(obj, original_mode)
            if target_indices is None:
                return {'CANCELLED'}
            if not target_indices:
                self.report({'WARNING'},
                            "Nothing selected — mask or select verts/faces, or turn off 'Selected Only'")
                return {'CANCELLED'}
        else:
            target_indices = None

        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        try:
            n_modified = self._smooth(obj, target_indices, s)
        finally:
            if original_mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='EDIT')
            elif original_mode == 'PAINT_WEIGHT':
                bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        if n_modified < 0:
            return {'CANCELLED'}

        scope = "active group" if s.only_active_group else "all unlocked groups"
        norm = ", normalised" if s.normalize else ""
        verb = "Sharpened" if self.mode == 'SHARPEN' else "Smoothed"
        self.report({'INFO'}, f"{verb} {n_modified} vert(s), {s.iterations} iter, {scope}{norm}")
        return {'FINISHED'}

    def _collect_selected(self, obj, mode):
        if mode == 'EDIT_MESH':
            try:
                import bmesh
                bm = bmesh.from_edit_mesh(obj.data)
                return [v.index for v in bm.verts if v.select]
            except Exception as e:
                self.report({'ERROR'}, f"bmesh access failed: {e}")
                return None

        # Weight Paint / Object mode: union of vertex selection and polygon selection.
        selected = set()
        mesh = obj.data
        for v in mesh.vertices:
            if v.select:
                selected.add(v.index)
        for poly in mesh.polygons:
            if poly.select:
                selected.update(poly.vertices)
        return sorted(selected)

    def _smooth(self, obj, target_indices, s):
        mesh = obj.data
        n_verts = len(mesh.vertices)

        if target_indices is None:
            target_indices = list(range(n_verts))

        if s.only_active_group:
            active_idx = obj.vertex_groups.active_index
            if active_idx < 0:
                self.report({'WARNING'}, "No active vertex group")
                return -1
            group_indices = [active_idx]
        else:
            group_indices = [i for i, g in enumerate(obj.vertex_groups) if not g.lock_weight]

        if not group_indices:
            self.report({'WARNING'}, "No unlocked vertex groups to smooth")
            return -1
        group_set = set(group_indices)

        neighbors = [[] for _ in range(n_verts)]
        for edge in mesh.edges:
            v0, v1 = edge.vertices
            neighbors[v0].append(v1)
            neighbors[v1].append(v0)

        current = {gi: {} for gi in group_indices}
        for v in mesh.vertices:
            for vge in v.groups:
                if vge.group in group_set:
                    current[vge.group][v.index] = vge.weight

        eps = 1e-5
        strength = s.strength
        sign = -1.0 if self.mode == 'SHARPEN' else 1.0

        for _ in range(s.iterations):
            updates = []
            for vidx in target_indices:
                nbrs = neighbors[vidx]
                if not nbrs:
                    continue
                inv_n = 1.0 / len(nbrs)
                for gi in group_indices:
                    cur_w = current[gi].get(vidx, 0.0)
                    nbr_sum = 0.0
                    cg = current[gi]
                    for n in nbrs:
                        nbr_sum += cg.get(n, 0.0)
                    avg = nbr_sum * inv_n
                    new_w = cur_w + (avg - cur_w) * strength * sign
                    if new_w < 0.0:
                        new_w = 0.0
                    elif new_w > 1.0:
                        new_w = 1.0
                    updates.append((gi, vidx, new_w))
            for gi, vidx, w in updates:
                if w > eps:
                    current[gi][vidx] = w
                elif vidx in current[gi]:
                    del current[gi][vidx]

        if s.normalize:
            for vidx in target_indices:
                total = 0.0
                for gi in group_indices:
                    total += current[gi].get(vidx, 0.0)
                if total > eps and abs(total - 1.0) > eps:
                    inv_t = 1.0 / total
                    for gi in group_indices:
                        if vidx in current[gi]:
                            current[gi][vidx] *= inv_t

        for gi in group_indices:
            vg = obj.vertex_groups[gi]
            for vidx in target_indices:
                w = current[gi].get(vidx, 0.0)
                if w > eps:
                    vg.add([vidx], w, 'REPLACE')
                else:
                    try:
                        vg.remove([vidx])
                    except RuntimeError:
                        pass

        return len(target_indices)


class WPT_OT_SetBrushWeight(bpy.types.Operator):
    """Set the unified brush weight to a preset value"""
    bl_idname = "wpt.set_brush_weight"
    bl_label = "Set Brush Weight"
    bl_options = {'REGISTER', 'INTERNAL'}

    weight: bpy.props.FloatProperty(default=0.5, min=0.0, max=1.0)

    def execute(self, context):
        ts = context.scene.tool_settings
        if hasattr(ts, 'unified_paint_settings'):
            ts.unified_paint_settings.weight = self.weight
        return {'FINISHED'}


class WPT_OT_SelectBone(bpy.types.Operator):
    """Select a single bone on a given armature (used by the Vertex Influence Inspector)"""
    bl_idname = "wpt.select_bone"
    bl_label = "Select Bone"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    armature: bpy.props.StringProperty()
    bone: bpy.props.StringProperty()

    def execute(self, context):
        rig = bpy.data.objects.get(self.armature)
        if not rig or rig.type != 'ARMATURE':
            self.report({'WARNING'}, f"Armature '{self.armature}' not found")
            return {'CANCELLED'}
        for b in rig.data.bones:
            b.select = False
        target = rig.data.bones.get(self.bone)
        if not target:
            self.report({'WARNING'}, f"Bone '{self.bone}' not found")
            return {'CANCELLED'}
        target.select = True
        rig.data.bones.active = target
        return {'FINISHED'}


classes = (
    WPT_OT_SetBrushMode,
    WPT_OT_SetupWeightPaint,
    WPT_OT_SwitchTool,
    WPT_OT_QuickSwitchMesh,
    WPT_OT_MirrorWeights,
    WPT_OT_GradientAddSubtract,
    WPT_OT_FloodSmooth,
    WPT_OT_SmartSmoothWeights,
    WPT_OT_SetBrushWeight,
    WPT_OT_SelectBone,
)
