"""
Direct TCP connection to Blender — bypasses MCP entirely.

Requirements:
  - Blender is running
  - The blender_mcp add-on is installed and its socket server is started
  - Default: localhost:9876

Usage:
  python blender_direct.py
"""

import socket
import json


HOST = "localhost"
PORT = 9876
TIMEOUT = 30.0


def run_in_blender(code: str, strict_json: bool = False) -> dict:
    """Send Python code to Blender and return the response dict."""
    request = json.dumps({"type": "execute", "code": code, "strict_json": strict_json}) + "\0"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(TIMEOUT)
        s.connect((HOST, PORT))
        s.sendall(request.encode("utf-8"))

        buf = bytearray()
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            if b"\0" in buf:
                break

    response_line = buf.split(b"\0")[0]
    return json.loads(response_line.decode("utf-8"))


def blender(code: str) -> None:
    """Run code in Blender and pretty-print the result."""
    try:
        resp = run_in_blender(code)
    except ConnectionRefusedError:
        print(f"[ERROR] Could not connect to Blender on {HOST}:{PORT}")
        print("        Make sure the add-on socket server is running.")
        return
    except TimeoutError:
        print("[ERROR] Blender did not respond within the timeout.")
        return

    status = resp.get("status")
    result = resp.get("result")
    stdout = resp.get("stdout", "").strip()
    stderr = resp.get("stderr", "").strip()

    if status == "ok":
        print("[OK]", json.dumps(result, indent=2) if result else "(no result)")
    else:
        print("[ERROR]", status)

    if stdout:
        print("[stdout]\n" + stdout)
    if stderr:
        print("[stderr]\n" + stderr)


# ---------------------------------------------------------------------------
# Examples — edit or replace these as needed
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    # 1. Get the names of all objects in the scene
    blender("""
result = [obj.name for obj in bpy.data.objects]
""")

    # 2. Add a cube at a specific location and return its name
    blender("""
import bpy
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 2))
result = {"added": bpy.context.active_object.name}
""")

    # 3. Print something (captured in stdout)
    blender("""
import bpy
for obj in bpy.data.objects:
    print(obj.name, obj.type)
""")
