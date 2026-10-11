"""Executed inside Maya by maya_bridge.py; defines run(inp, out).

run() executes the staged script with stdout/stderr captured and writes the log
plus the value of __result__ to the output file.
"""

import sys
import time
import traceback


def run(inp, out):
    started = time.time()
    src = open(inp, encoding="utf-8-sig").read()
    ns = {"__name__": "__maya_bridge__", "__file__": inp}
    log = []
    result = None
    old = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = _Capture(log)
    try:
        try:
            exec(compile(src, inp, "exec"), ns)
        except SystemExit:
            pass
        else:
            result = ns.get("__result__")
    except BaseException:
        log.append(traceback.format_exc())
    finally:
        sys.stdout, sys.stderr = old

    text = "".join(log)
    if result is not None:
        text += ("__result__ = %r\n" % (result,))
    text += "--- %.2fs ---\n" % (time.time() - started)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    return "ok"


class _Capture:
    def __init__(self, sink):
        self.sink = sink
        self.buf = ""

    def write(self, data):
        self.buf += data
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            self.sink.append(line + "\n")

    def flush(self):
        if self.buf:
            self.sink.append(self.buf)
            self.buf = ""
