---
name: blender
description: >
  Execute tasks in Blender — creating, modifying, or inspecting 3D objects, meshes,
  materials, modifiers, animations, renders, and scene data — by writing bpy Python
  code and running it in the connected Blender instance via TCP. Use this skill whenever
  the user wants to do anything in Blender: add a mesh, apply a modifier, export a file,
  render a frame, check what's in the scene, move objects, set up materials, or any
  other 3D workflow task. Trigger even if the request is phrased casually like "can you
  add a cube" or "what objects are in my scene" — not just explicit code requests.
---

# Blender Skill

Execute `bpy` Python code in a live Blender instance via a local TCP server on port 9876.

## Prerequisites

The Simple TCP Server add-on must be installed and running in Blender before any code
can be executed. Without it, all connections will fail.

---

## Bundled scripts

| Script | Purpose |
|--------|---------|
| `.claude/skills/blender/blender_exec.py` | CLI executor — sends a `.py` file to Blender over TCP and prints the result. The primary tool for running task scripts. |
| `.claude/skills/blender/blender_direct.py` | Low-level TCP wrapper with a `run_in_blender(code)` helper. Useful as a reference or for interactive use from a Python REPL. Not needed for normal task execution. |

---

## Execution

Write new task scripts to the project root or `./scripts/` — not inside `.claude/`.
Then run them through the executor:

```
uv run .claude/skills/blender/blender_exec.py -f scripts/_blender_task.py
```

Or for a top-level script:

```
uv run .claude/skills/blender/blender_exec.py -f _blender_task.py
```

Response fields:
- `stdout` — any `print()` calls from your script
- `stderr` — warnings
- `result` — the dict you assigned to `result = {...}`
- On error: read the traceback, fix, re-run

---

## Workflow

### Step 1 — Inspect the scene first (unless purely additive)

Before modifying anything, understand what exists:

```python
import bpy
result = {
    "objects": [(o.name, o.type) for o in bpy.data.objects],
    "active": bpy.context.active_object.name if bpy.context.active_object else None,
    "mode": bpy.context.mode,
}
```

Run this, read the output, then plan your approach.

### Step 2 — Write the bpy code

```python
import bpy  # always import at the top

# Set active + selection explicitly — never assume current state
obj = bpy.data.objects["MyObject"]
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

# Switch mode explicitly when needed
bpy.ops.object.mode_set(mode='EDIT')

# After structural changes, update depsgraph before reading computed values
bpy.context.view_layer.update()

# Always set result to confirm what happened
result = {"status": "done", "object": obj.name}
```

Prefer `bpy.ops.*` for standard actions (add mesh, apply modifier, set origin) — they
handle defaults and context. Use `bpy.data.*` for precise data control or to avoid
side effects.

In Edit mode, use the `bmesh` API and flush changes back to the mesh before exiting.

### Step 3 — Execute and verify

After running, do a second inspection (or targeted check) to confirm the scene is
in the expected state. Then delete the task script (e.g. `scripts/_blender_task.py`).
