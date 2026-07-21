"""
Minimal TCP socket server add-on for Blender.

Listens on localhost:9876 (configurable). Accepts null-byte-delimited JSON
requests, executes the Python code in Blender's main thread, and returns
a JSON response with the result, stdout, and stderr.

Protocol (same as blender_mcp so blender_direct.py works unchanged):
  Request:  {"type": "execute", "code": "...", "strict_json": false}\0
  Response: {"status": "ok", "result": {...}, "stdout": "...", "stderr": "..."}\0
"""

import io
import json
import select
import socket
import sys
import traceback

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty

# ---------------------------------------------------------------------------
# Constants

_HOST_DEFAULT = "localhost"
_PORT_DEFAULT = 9876
_TIMER_INTERVAL = 0.1       # seconds between polls
_RECV_BUFFER = 4096
_MAX_REQUEST_BYTES = 10 * 1024 * 1024
_CLIENT_TIMEOUT_TICKS = 100  # ~10s at 0.1s/tick

# ---------------------------------------------------------------------------
# Server state (module-level singletons)

_server_sock: socket.socket | None = None

class _Client:
    __slots__ = ("conn", "buf", "ticks")
    def __init__(self, conn: socket.socket) -> None:
        self.conn = conn
        self.buf = bytearray()
        self.ticks = _CLIENT_TIMEOUT_TICKS

_clients: list[_Client] = []

# ---------------------------------------------------------------------------
# Stdout/stderr capture

class _Tee(io.TextIOBase):
    __slots__ = ("_buf", "_orig")
    def __init__(self, orig):
        self._buf = io.StringIO()
        self._orig = orig
    def write(self, s):
        self._orig.write(s)
        return self._buf.write(s)
    def flush(self):
        self._orig.flush()
        self._buf.flush()
    def getvalue(self):
        return self._buf.getvalue()

class _CaptureOutput:
    def __enter__(self):
        self._out = _Tee(sys.stdout)
        self._err = _Tee(sys.stderr)
        sys.stdout, sys.stderr = self._out, self._err
        return self
    def __exit__(self, *_):
        sys.stdout = self._out._orig
        sys.stderr = self._err._orig
    @property
    def stdout(self): return self._out.getvalue()
    @property
    def stderr(self): return self._err.getvalue()

# ---------------------------------------------------------------------------
# Code execution

def _execute(code: str) -> dict:
    ns: dict = {"result": {}}
    with _CaptureOutput() as cap:
        try:
            exec(code, ns)
        except Exception:
            resp = {"status": "error", "message": traceback.format_exc()}
            if cap.stdout: resp["stdout"] = cap.stdout
            if cap.stderr: resp["stderr"] = cap.stderr
            return resp

    result = ns["result"]
    if not isinstance(result, dict):
        result = {"value": repr(result)}

    # Fallback: repr any non-serializable values so we never crash here.
    result = json.loads(json.dumps(result, default=repr))

    resp = {"status": "ok", "result": result}
    if cap.stdout: resp["stdout"] = cap.stdout
    if cap.stderr: resp["stderr"] = cap.stderr
    return resp


def _handle_request(data: bytes) -> dict:
    try:
        req = json.loads(data)
    except json.JSONDecodeError as ex:
        return {"status": "error", "message": "Invalid JSON: " + str(ex)}

    if req.get("type") != "execute":
        return {"status": "error", "message": "Unknown type: " + repr(req.get("type"))}

    return _execute(req.get("code", ""))


def _encode(resp: dict) -> bytes:
    return (json.dumps(resp) + "\0").encode()

# ---------------------------------------------------------------------------
# Socket polling (called by the timer)

def _poll() -> None:
    global _server_sock
    if _server_sock is None:
        return

    # Accept new connections.
    while True:
        try:
            conn, _ = _server_sock.accept()
            conn.setblocking(False)
            _clients.append(_Client(conn))
        except BlockingIOError:
            break
        except OSError:
            break

    # Service existing clients.
    for client in _clients[:]:
        client.ticks -= 1
        if client.ticks <= 0:
            try: client.conn.sendall(_encode({"status": "error", "message": "Client timed out"}))
            except OSError: pass
            client.conn.close()
            _clients.remove(client)
            continue

        try:
            chunk = client.conn.recv(_RECV_BUFFER)
        except BlockingIOError:
            continue
        except OSError:
            client.conn.close()
            _clients.remove(client)
            continue

        if not chunk:
            client.conn.close()
            _clients.remove(client)
            continue

        client.buf.extend(chunk)

        if len(client.buf) > _MAX_REQUEST_BYTES:
            try: client.conn.sendall(_encode({"status": "error", "message": "Request too large"}))
            except OSError: pass
            client.conn.close()
            _clients.remove(client)
            continue

        if b"\0" not in client.buf:
            continue

        data = bytes(client.buf[:client.buf.index(b"\0")])
        resp = _handle_request(data)
        try:
            client.conn.sendall(_encode(resp))
        except OSError:
            pass
        client.conn.close()
        _clients.remove(client)


def _timer_cb() -> float | None:
    if _server_sock is None:
        return None
    try:
        _poll()
    except Exception:
        traceback.print_exc()
    return _TIMER_INTERVAL

# ---------------------------------------------------------------------------
# Start / stop

def _start(host: str, port: int) -> None:
    global _server_sock
    if _server_sock is not None:
        raise RuntimeError("Server already running")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setblocking(False)
    s.bind((host, port))
    s.listen(5)
    _server_sock = s
    bpy.app.timers.register(_timer_cb, first_interval=_TIMER_INTERVAL, persistent=True)


def _stop() -> None:
    global _server_sock
    if bpy.app.timers.is_registered(_timer_cb):
        bpy.app.timers.unregister(_timer_cb)
    if _server_sock is not None:
        _server_sock.close()
        _server_sock = None
    for c in _clients:
        try: c.conn.close()
        except OSError: pass
    _clients.clear()


def _is_running() -> bool:
    return _server_sock is not None

# ---------------------------------------------------------------------------
# Blender UI

class SimpleTCPPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    host: StringProperty(name="Host", default=_HOST_DEFAULT)
    port: IntProperty(name="Port", default=_PORT_DEFAULT, min=1024, max=65535)
    auto_start: BoolProperty(name="Auto Start", default=True)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "host")
        layout.prop(self, "port")
        layout.prop(self, "auto_start")
        if _is_running():
            layout.operator("simple_tcp.stop", icon="CANCEL")
            layout.label(text="Running on {:s}:{:d}".format(self.host, self.port), icon="CHECKMARK")
        else:
            layout.operator("simple_tcp.start", icon="PLAY")
            layout.label(text="Stopped", icon="X")


class SIMPLETCP_OT_start(bpy.types.Operator):
    bl_idname = "simple_tcp.start"
    bl_label = "Start Server"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        try:
            _start(prefs.host, prefs.port)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}
        self.report({"INFO"}, "TCP server started on {:s}:{:d}".format(prefs.host, prefs.port))
        return {"FINISHED"}


class SIMPLETCP_OT_stop(bpy.types.Operator):
    bl_idname = "simple_tcp.stop"
    bl_label = "Stop Server"

    def execute(self, context):
        _stop()
        self.report({"INFO"}, "TCP server stopped")
        return {"FINISHED"}


class SIMPLETCP_PT_panel(bpy.types.Panel):
    bl_label = "Simple TCP Server"
    bl_idname = "SIMPLETCP_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "TCP Server"

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__package__].preferences
        if _is_running():
            layout.operator("simple_tcp.stop", icon="CANCEL")
            layout.label(text="Running on {:s}:{:d}".format(prefs.host, prefs.port), icon="CHECKMARK")
        else:
            layout.operator("simple_tcp.start", icon="PLAY")
            layout.label(text="Stopped", icon="X")


_classes = (SimpleTCPPreferences, SIMPLETCP_OT_start, SIMPLETCP_OT_stop, SIMPLETCP_PT_panel)


def _autostart():
    prefs = bpy.context.preferences.addons[__package__].preferences
    if prefs.auto_start and not _is_running():
        try:
            _start(prefs.host, prefs.port)
        except Exception:
            traceback.print_exc()


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.app.timers.register(_autostart, first_interval=1.0, persistent=False)


def unregister():
    _stop()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
