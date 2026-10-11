"""Offline tests for canvas_bridge.py.

Runs a tiny in-process HTTP server that pretends to be Canvas, points the bridge
at it via CANVAS_URL/CANVAS_TOKEN, and exercises every command - including the
3-step file upload - plus the auth-failure path. No real Canvas account needed.

Run:  python test_canvas_bridge.py      (expect exit 0, "all checks passed")
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import canvas_bridge as cb                              # noqa: E402

BASE = ""
GOOD_TOKEN = "testtoken"

PASS = 0
FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok  %s" % label)
    else:
        FAIL += 1
        print(" FAIL %s" % label)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj, extra=None):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self):
        return self.headers.get("Authorization") == "Bearer " + GOOD_TOKEN

    def do_GET(self):
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)
        if path != "/upload/1" and not self._auth_ok():
            return self._json(401, {"errors": [{"message": "Invalid access token"}]})
        if path == "/api/v1/users/self":
            return self._json(200, {"id": 42, "name": "Ada Lovelace",
                                    "login_id": "ada@school.edu"})
        if path == "/api/v1/courses":
            if q.get("page") == ["2"]:
                return self._json(200, [
                    {"id": 12, "name": "Physics", "course_code": "PHY200",
                     "enrollments": [{"role": "studentEnrollment",
                                      "grades": {"current_score": 88.0,
                                                 "current_grade": "B+"}}]}])
            link = ('<%s/api/v1/courses?page=2>; rel="next", '
                    '<%s/api/v1/courses?page=2>; rel="last"' % (BASE, BASE))
            return self._json(200, [
                {"id": 10, "name": "Intro to Design", "course_code": "ART101",
                 "term": {"name": "Fall 2026"},
                 "enrollments": [{"role": "studentEnrollment",
                                  "grades": {"current_score": 92.0,
                                             "current_grade": "A"}}]},
                {"id": 11, "name": "Algebra", "course_code": "MAT100",
                 "enrollments": [{"role": "studentEnrollment", "grades": {}}]}],
                extra={"Link": link})
        if path == "/api/v1/courses/10/assignments":
            return self._json(200, [
                {"id": 20, "name": "Essay 1", "due_at": "2026-10-20T18:00:00Z",
                 "points_possible": 100,
                 "submission": {"submitted_at": "2026-10-19T22:04:00Z"}}])
        if path == "/api/v1/courses/10/assignments/20/submissions/self":
            return self._json(200, {
                "attempt": 1, "workflow_state": "submitted",
                "submitted_at": "2026-10-19T22:04:00Z", "score": 92,
                "grade": "A", "assignment": {"points_possible": 100}})
        return self._json(404, {"errors": [{"message": "not found"}]})

    def do_POST(self):
        u = urlparse(self.path)
        path = u.path
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        if path == "/upload/1":                          # upload target, no auth
            return self._json(200, {"id": 99, "url": "https://files/file99"})
        if not self._auth_ok():
            return self._json(401, {"errors": [{"message": "Invalid access token"}]})
        if path == "/api/v1/courses/10/assignments/20/submissions/self/files":
            return self._json(200, {"upload_url": BASE + "/upload/1",
                                    "upload_params": {"key": "k1", "policy": "p1"}})
        if path == "/api/v1/courses/10/assignments/20/submissions":
            return self._json(200, {"attempt": 1, "workflow_state": "submitted"})
        return self._json(404, {"errors": [{"message": "not found"}]})


def run(argv, url=None, token=None):
    os.environ.pop("CANVAS_URL", None)
    os.environ.pop("CANVAS_TOKEN", None)
    args = ["--url", url if url is not None else BASE,
            "--token", token if token is not None else GOOD_TOKEN] + argv
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cb.main(args)
    return code, out.getvalue(), err.getvalue()


def main():
    global BASE
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    BASE = "http://127.0.0.1:%d" % srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    try:
        code, out, _ = run(["whoami"])
        check("whoami exit 0", code == 0)
        check("whoami name", "Ada Lovelace" in out)
        check("whoami login", "ada@school.edu" in out)

        code, out, _ = run(["--ping"])
        check("ping = whoami", code == 0 and "Ada Lovelace" in out)

        code, out, _ = run(["courses"])
        check("courses exit 0", code == 0)
        check("courses page 1", "Intro to Design" in out)
        check("courses page 2 (pagination)", "Physics" in out)
        check("courses term", "Fall 2026" in out)

        code, out, _ = run(["assignments", "10"])
        check("assignments exit 0", code == 0)
        check("assignment listed", "[20] Essay 1" in out)
        check("assignment due", "2026-10-20" in out)
        check("assignment submission status", "submitted" in out)

        code, out, _ = run(["submissions", "10", "20"])
        check("submissions exit 0", code == 0)
        check("submission attempt", "Attempt 1" in out)
        check("submission score", "92 / 100" in out)
        check("submission grade", "Grade: A" in out)

        code, out, _ = run(["grades"])
        check("grades exit 0", code == 0)
        check("grade ART101", "92.0%" in out and "Intro to Design" in out)
        check("grade PHY200", "Physics" in out and "B+" in out)
        check("grades no-grade course", "Algebra" in out and "(no grade)" in out)

        code, out, _ = run(["grades", "10"])
        check("grades filter", "Intro to Design" in out and "Physics" not in out)

        code, out, _ = run(["submit", "10", "20", "--text", "my answer"])
        check("submit text exit 0", code == 0)
        check("submit text echo", "Submitted to assignment 20" in out)

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("hello canvas")
            tmp = fh.name
        try:
            code, out, _ = run(["submit", "10", "20", "--file", tmp])
            check("submit file exit 0", code == 0)
            check("submit file echo", "Submitted to assignment 20" in out)
        finally:
            os.unlink(tmp)

        code, out, _ = run(["get", "/api/v1/users/self", "--json"])
        check("get --json exit 0", code == 0)
        check("get --json body", '"name": "Ada Lovelace"' in out)

        code, out, err = run(["courses"], token="wrong")
        check("bad token exit 1", code == 1)
        check("bad token message", "CANVAS ERROR" in err and "401" in err)

        code, out, err = run(["whoami"], url="")
        check("missing url exit 1", code == 1)
        check("missing url message", "No Canvas URL" in err)

        code, out, err = run(["whoami"], token="")
        check("missing token exit 1", code == 1)
        check("missing token message", "No Canvas token" in err)
    finally:
        srv.shutdown()

    print("\n%d passed, %d failed" % (PASS, FAIL))
    if FAIL:
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
