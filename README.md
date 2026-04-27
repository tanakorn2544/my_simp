# My Simp v2.8.2

**My Simp** is a Blender add-on focused on **streamlining weight painting and rigging workflows**.  
It provides **compact, one-click tools**, keyboard shortcuts, and smart visibility controls so artists can work faster **without constantly switching modes, tools, or UI panels**.

Designed for character artists who want to stay in flow.

---

## 🧩 UI Layout

The N-panel uses a **tab rail** on the left with four focused tabs:

| Tab | Purpose |
|---|---|
| 🎨 **Paint** | Setup, brushes, weight slider, mirror weights, vertex influence inspector |
| 💨 **Smooth** | Smart Smooth & Sharpen on selected verts, plus cleanup batch ops |
| 🦴 **Rig** | Bone visibility, collection presets, pose save / blend / mirror |
| ⚙ **Tools** | Mesh symmetry (cut / mirror) and viewport display options |

Click the icons on the rail to switch tabs. The active tab is highlighted.

---

## ✨ Key Features

### 🎨 Paint Tab
- **Auto setup**: one click selects the armature alongside the active mesh and enters Weight Paint mode
- **Auto-Follow Active Mesh**: when on, switching to another rigged mesh re-enters Weight Paint with the right armature paired automatically
- One-click **Draw / Gradient** with quick weight presets (`0`, `.25`, `.5`, `.75`, `1`)
- **Brush pie menu** — Draw / Add / Subtract / Smooth / Blur / Average / Gradient / Sample (`Alt + Q` by default)
- **Gradient Add/Subtract toggle** for fast falloff painting
- **Mirror Weights** across X / Y / Z using a KDTree-based vertex matcher (handles `.L/.R` group naming)
- **Vertex Influence Inspector**: select a vertex (Edit mode or paint mask), see every group weight driving it, click a bone icon to jump-select that bone on the rig

### 💨 Smooth Tab
- **Smart Smooth**: boundary-aware Laplacian smoothing on selected verts, with iteration count, strength, normalize, and *active group only* controls
- **Sharpen**: same engine in reverse — pushes weights away from neighbour mean
- Cleanup batch: **Normalize All**, **Limit Total**, **Clean Zero**

### 🦴 Rig Tab
- Toggle **Deform Bones only** (uses bone collections when present, falls back to name patterns)
- Show **Controller + Deform** bones in one click
- **Toggle Pose / Rest** on every mesh deformed by the active rig (scoped — leaves unrelated armatures alone)
- **Apply Rest Pose** while in Pose mode
- **Bone Collection Presets**: save current visibility set, load / rename / delete saved presets
- **Pose tools**:
  - Save current pose to a named slot
  - Blend rest ↔ pose with a slider, or via the modal mouse-drag control (`X` key)
  - **Pose Mirror**: copy selected bones' transforms to their `.L/.R` counterparts (X-axis flipped)
  - T-Pose generator and reset-to-rest

### ⚙ Tools Tab
- **Cut Half** along X / Y / Z (destructive — confirm dialog)
- **Add Mirror modifier** along X / Y / Z, optional weight mirroring
- **Display options**: restrict to active group, show wireframe, **Bones In Front** (X-Ray)

### ⚡ Compatibility
Works with **Rigify**, **Auto-Rig Pro**, and custom rigs. Auto-detects the deforming armature via the mesh's Armature modifier or parent.

---

## ⌨ Keyboard Shortcuts (Customizable)

All shortcuts can be changed in **Add-on Preferences** — no Blender restart required.

| Action | Default |
|---|---|
| Open Main Panel | `Y` |
| Brush Pie Menu | `Alt + Q` |
| Toggle Bones Overlay | `D` |
| Gradient Add/Subtract | `E` |
| Pose Slider Control | `X` |
| Pose Popup | `P` |
| Quick Switch Mesh | `Alt + U` |

> 💡 **Tip:** Shortcuts update instantly when changed in preferences.

---

## 🧩 UI Location

**3D Viewport > Sidebar (N) > Weight Paint**

## 📦 Installation

1. Download the `.zip` file.
2. In Blender, go to **Edit > Preferences > Add-ons**.
3. Click **Install...** and select the zip file.
4. Enable the add-on checkbox.
