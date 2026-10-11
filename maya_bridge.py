"""Run Python inside the live Maya 2027 session over its command port (127.0.0.1:7001).

Usage:
    python maya_bridge.py script.py            run a file in Maya
    python maya_bridge.py -c "print(2+2)"      run inline code
    python maya_bridge.py --ping               check the bridge responds
    python maya_bridge.py --port 7001 script.py

Output (stdout, stderr, tracebacks and the value of a `__result__` variable) comes
back in _maya_out.txt. Enable the port in Maya with:
    import maya.cmds as cmds
    cmds.commandPort(name="127.0.0.1:7001", protocol="echo", sourceType="python")
"""

import argparse
import socket
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE / "maya_hook.py"
IN = HERE / "_maya_in.py"
OUT = HERE / "_maya_out.txt"
DEFAULT_PORT = 7001
FAIL = "BRIDGE-FAILED"


def trigger(hook, inp, out):
    # One single-line expression: exec the hook into this command's globals, then
    # call run(). The port evaluates expressions and echoes the result.
    return ("(exec(open(r'%s', encoding='utf-8').read(), globals()), "
            "globals()['run'](r'%s', r'%s'))[1]" % (hook, inp, out))


def send(expr, port, timeout):
    with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
        sock.settimeout(timeout)
        sock.sendall(expr.encode("utf-8") + b"\n")
        chunks = []
        while True:
            try:
                data = sock.recv(4096)
            except socket.timeout:
                break
            if not data:
                break
            chunks.append(data)
            if b"\n" in data:
                break
        return b"".join(chunks).decode("utf-8", "replace").strip()


def run(code, port=DEFAULT_PORT, timeout=60.0):
    """Execute code in Maya; return the captured output (or raise RuntimeError)."""
    if code.startswith("\ufeff"):
        code = code.lstrip("\ufeff")
    IN.write_text(code, encoding="utf-8")
    OUT.unlink(missing_ok=True)
    try:
        echo = send(trigger(HOOK, IN, OUT), port, timeout)
    except OSError as exc:
        raise RuntimeError(
            "Maya command port 127.0.0.1:%d unreachable (%s).\n"
            'In Maya run: import maya.cmds as cmds; '
            'cmds.commandPort(name="127.0.0.1:%d", protocol="echo", sourceType="python")'
            % (port, exc, port)) from exc

    deadline = time.time() + timeout
    while time.time() < deadline:
        if OUT.exists():
            text = OUT.read_text(encoding="utf-8", errors="replace")
            if text:
                return text
        time.sleep(0.1)

    if FAIL in echo:
        return echo + "\n"
    raise RuntimeError("Maya never wrote a reply (echo was: %r)" % echo)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run Python in the live Maya session.")
    ap.add_argument("script", nargs="?", help="file to execute")
    ap.add_argument("-c", "--code", help="inline code to execute")
    ap.add_argument("--ping", action="store_true", help="just check the bridge")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=60.0)
    a = ap.parse_args(argv)

    if a.ping:
        code = "import maya.cmds as cmds\nprint('maya', cmds.about(version=True))"
    elif a.code:
        code = a.code
    elif a.script:
        p = Path(a.script).expanduser()
        if not p.exists():
            ap.error("no such file: %s" % p)
        code = p.read_text(encoding="utf-8-sig")
    else:
        ap.print_help()
        return 2

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    try:
        out = run(code, a.port, a.timeout)
    except RuntimeError as exc:
        print("BRIDGE ERROR: %s" % exc, file=sys.stderr)
        return 1

    sys.stdout.write(out if out.endswith("\n") else out + "\n")
    return 1 if "Traceback (most recent call last)" in out else 0


if __name__ == "__main__":
    sys.exit(main())
