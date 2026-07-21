"""
CLI tool to execute Python code in Blender via TCP.

Usage:
  python blender_exec.py -f script.py       # run a file
  python blender_exec.py                    # read code from stdin
  echo "result = 1+1" | python blender_exec.py
"""

import json
import socket
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HOST = "localhost"
PORT = 9876
TIMEOUT = 60.0


def send(code: str) -> dict:
    request = json.dumps({"type": "execute", "code": code, "strict_json": False}) + "\0"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(TIMEOUT)
        s.connect((HOST, PORT))
        s.sendall(request.encode())
        buf = bytearray()
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)
            if b"\0" in buf:
                break
    return json.loads(buf.split(b"\0")[0].decode())


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "-f":
        with open(sys.argv[2], encoding="utf-8") as f:
            code = f.read()
    else:
        code = sys.stdin.read()

    try:
        resp = send(code)
    except ConnectionRefusedError:
        print(f"ERROR: cannot connect to Blender on {HOST}:{PORT}")
        print("Make sure the Simple TCP Server add-on is running.")
        sys.exit(1)
    except TimeoutError:
        print("ERROR: Blender did not respond within the timeout.")
        sys.exit(1)

    if resp.get("stdout"):
        print(resp["stdout"], end="")
    if resp.get("stderr"):
        print(resp["stderr"], end="", file=sys.stderr)

    if resp.get("status") == "ok":
        result = resp.get("result")
        if result:
            print(json.dumps(result, indent=2))
    else:
        print("ERROR:", resp.get("message", resp))
        sys.exit(1)


if __name__ == "__main__":
    main()
