Execute a task in Blender by writing `bpy` Python code and running it over TCP.

Task: $ARGUMENTS

---

## Your workflow

**Tools available:**
- `Write` — write code to a temp file
- `Bash` — run it via `python D:\game-asset-heartland\mcp-servers\blender_mcp\blender_exec.py -f <file>`
- Repeat until the task is complete

**Step 1 — Inspect the scene first** (unless the task is purely creative/additive)

Write a quick inspection script to understand what exists:

```python
import bpy
result = {
    "objects": [(o.name, o.type) for o in bpy.data.objects],
    "active": bpy.context.active_object.name if bpy.context.active_object else None,
    "mode": bpy.context.mode,
}
```

Run it, read the output, then plan your approach.

**Step 2 — Write the code**

- Always `import bpy` at the top
- Set `result = {...}` with anything meaningful to confirm success
- Prefer `bpy.ops.*` for standard actions (add mesh, apply modifier, set origin)
- Use `bpy.data.*` for direct data access
- Set active object and selection explicitly — never assume current state:
  ```python
  bpy.context.view_layer.objects.active = obj
  obj.select_set(True)
  ```
- Switch modes explicitly when needed:
  ```python
  bpy.ops.object.mode_set(mode='EDIT')
  ```
- After structural changes, update the dependency graph before reading computed values:
  ```python
  bpy.context.view_layer.update()
  ```

**Step 3 — Execute**

Write the code to `D:\game-asset-heartland\mcp-servers\blender_mcp\_blender_task.py`, then run:

```
python D:\game-asset-heartland\mcp-servers\blender_mcp\blender_exec.py -f D:\game-asset-heartland\mcp-servers\blender_mcp\_blender_task.py
```

**Step 4 — Handle results**

- `stdout` — any `print()` calls from your code
- `stderr` — warnings
- `result` — the dict you set
- On error: read the traceback, fix the code, re-run

**Step 5 — Verify**

Run a second inspection script to confirm the scene is in the expected state.

---

## Rules

- Never destructively modify objects without first confirming their names from an inspection run
- Do not assume mode — always check or set it explicitly
- Keep each execution focused; break complex tasks into multiple runs
- If Blender is not reachable, tell the user to start the Simple TCP Server add-on (Edit → Preferences → Add-ons → Simple TCP Server → Start Server)
