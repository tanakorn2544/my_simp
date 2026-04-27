"""PropertyGroups stored on Scene for the My Simp addon."""

import bpy
from bpy.props import (
    BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty,
)
from bpy.types import PropertyGroup

from . import utils


class WPT_SmoothSettings(PropertyGroup):
    """Inline settings for the Smart Smooth Weights operator."""
    iterations: IntProperty(
        name="Iterations",
        description="How many smoothing passes to run",
        default=5, min=1, max=50,
    )
    strength: FloatProperty(
        name="Strength",
        description="How strongly each pass blends a vertex toward its neighbour average",
        default=0.5, min=0.0, max=1.0, subtype='FACTOR',
    )
    selected_only: BoolProperty(
        name="Selected Only",
        description="Only modify selected verts (Edit Mode, or Weight Paint with Vertex Mask)",
        default=True,
    )
    normalize: BoolProperty(
        name="Normalize",
        description="Re-normalise each affected vertex's weights to sum to 1.0",
        default=True,
    )
    only_active_group: BoolProperty(
        name="Active Group Only",
        description="Smooth only the active vertex group instead of every unlocked group",
        default=False,
    )


class PoseData(PropertyGroup):
    """One saved pose entry."""
    name: StringProperty(name="Pose Name")
    pose_data: StringProperty(name="Pose Data")


class BoneCollectionPreset(PropertyGroup):
    """One saved bone-collection visibility preset."""
    name: StringProperty(name="Preset Name")
    collection_data: StringProperty(name="Collection Data")


class PoseSliderProperties(PropertyGroup):
    """Live state for the pose slider UI."""
    pose_factor: FloatProperty(
        name="Pose Factor",
        description="Blend between rest pose (0.0) and selected pose (1.0)",
        default=0.0,
        min=0.0,
        max=1.0,
        update=lambda self, context: utils.update_pose_blend(self, context),
    )
    pose_name: StringProperty(
        name="Pose Name",
        description="Name for the new pose",
        default="NewPose",
    )
    selected_pose: EnumProperty(
        name="Selected Pose",
        description="Select the pose to blend with",
        items=lambda self, context: [
            (str(i), pose.name, "") for i, pose in enumerate(context.scene.pose_collection)
        ],
        update=lambda self, context: utils.update_pose_blend(self, context),
    )
    rename_index: IntProperty(
        name="Rename Index",
        description="Index of pose to rename",
        default=-1,
    )


class BoneCollectionProperties(PropertyGroup):
    """Live state for bone-collection presets UI."""
    preset_name: StringProperty(
        name="Preset Name",
        description="Name for the new bone collection preset",
        default="New Preset",
    )
    selected_preset: EnumProperty(
        name="Selected Preset",
        description="Select the bone collection preset to load",
        items=lambda self, context: [
            (str(i), preset.name, "") for i, preset in enumerate(context.scene.bone_collection_presets)
        ],
    )


classes = (
    WPT_SmoothSettings,
    PoseData,
    BoneCollectionPreset,
    PoseSliderProperties,
    BoneCollectionProperties,
)
