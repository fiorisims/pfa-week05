#!/usr/bin/env python
"""Canvas bridge - read and submit work in your school's Canvas LMS.

Talks to any Canvas instance over its REST API (no browser needed). Nothing is
written to disk: the base URL and a personal access token come from the
environment, so no secret is ever committed.

Setup (PowerShell):
    $env:CANVAS_URL   = "https://canvas.yourschool.edu"
    $env:CANVAS_TOKEN = "<paste token>"
Get a token in Canvas: Account > Settings > + New Access Token.

Usage:
    python canvas_bridge.py --ping
    python canvas_bridge.py whoami
    python canvas_bridge.py courses [--all]
    python canvas_bridge.py assignments COURSE_ID
    python canvas_bridge.py submissions COURSE_ID ASSIGNMENT_ID
    python canvas_bridge.py grades [COURSE_ID]
    python canvas_bridge.py submit COURSE_ID ASSIGNMENT_ID --file essay.pdf
    python canvas_bridge.py submit COURSE_ID ASSIGNMENT_ID --text "my answer"
    python canvas_bridge.py submit COURSE_ID ASSIGNMENT_ID --link https://...
    python canvas_bridge.py get /api/v1/users/self/profile

Add --json to any command to print the raw API response instead.
Exit code is 1 on any auth/API error, so scripts can check $LASTEXITCODE.

Security: the token is only ever read from the environment (or --token on the
command line, which is NOT recommended because it lands in shell history) and
is never printed. Only your endpoints' data is shown.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

try:                                                   # non-ASCII course names
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                      # noqa: BLE001
    pass

TIMEOUT = 30                 # seconds for normal API calls
UPLOAD_TIMEOUT = 600         # seconds for file uploads (big files)

BASE = ""                    # set by configure(): e.g. https://x.edu
TOKEN = ""                   # set by configure(): personal access token


class CanvasError(Exception):
    """Any auth/network/API failure; message is safe to print."""


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def configure(base, token):
    global BASE, TOKEN
    BASE = (base or "").rstrip("/")
    TOKEN = token or ""
    if not BASE:
        raise CanvasError(
            "No Canvas URL set. Set $env:CANVAS_URL, e.g. "
            '"https://canvas.yourschool.edu"')
    if not TOKEN:
        raise CanvasError(
            "No Canvas token set. Set $env:CANVAS_TOKEN (Canvas > Account > "
            "Settings > + New Access Token).")


def _abs_url(path):
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return BASE + "/" + path.lstrip("/")


def _explain(code, body):
    msg = body.strip()
    try:
        data = json.loads(body)
        if isinstance(data, dict) and isinstance(data.get("errors"), list):
            parts = [e.get("message", "") for e in data["errors"]
                     if isinstance(e, dict)]
            msg = "; ".join(p for p in parts if p) or msg
        elif isinstance(data, dict) and data.get("message"):
            msg = data["message"]
    except Exception:                                  # noqa: BLE001
        pass
    if "<html" in msg.lower():
        msg = "(HTML error page)"
    msg = " ".join(msg.split())[:400]
    hint = ""
    if code == 401:
        hint = " - check CANVAS_TOKEN"
    elif code == 403:
        hint = " - your token lacks permission for this"
    elif code == 404:
        hint = " - not found, or no access to this course/assignment"
    return "HTTP %s%s: %s" % (code, hint, msg or "(no message)")


def _next_link(link_header):
    if not link_header:
        return None
    for part in link_header.split(","):
        seg = part.split(";")
        if len(seg) < 2:
            continue
        url = seg[0].strip().strip("<>")
        if any(a.strip() == 'rel="next"' for a in seg[1:]):
            return url
    return None


def _request(method, url, params=None, form=None, json_body=None,
             auth=True, timeout=TIMEOUT):
    """Return (json_or_text, link_header) for a single HTTP request."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(
            params, doseq=True)
    data = None
    ctype = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        ctype = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form, doseq=True).encode("utf-8")
        ctype = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if ctype:
        req.add_header("Content-Type", ctype)
    if auth:
        req.add_header("Authorization", "Bearer " + TOKEN)

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise CanvasError(_explain(e.code, e.read().decode("utf-8", "replace")))
    except urllib.error.URLError as e:
        raise CanvasError("cannot reach %s (%s)" % (BASE, e.reason))

    raw = resp.read().decode("utf-8", "replace")
    link = resp.headers.get("Link")
    if not raw:
        return None, link
    try:
        return json.loads(raw), link
    except ValueError:
        return raw, link


def api(method, path, params=None, form=None, json_body=None, paginate=False,
        timeout=TIMEOUT):
    """Call a Canvas endpoint. Follows pagination when paginate=True."""
    url = _abs_url(path)
    data, link = _request(method, url, params=params, form=form,
                          json_body=json_body, timeout=timeout)
    if not paginate or not isinstance(data, list):
        return data
    out = list(data)
    seen = 0
    while link:
        nxt = _next_link(link)
        if not nxt or seen > 200:                      # stop runaway loops
            break
        seen += 1
        data, link = _request("GET", nxt)
        if isinstance(data, list):
            out.extend(data)
        else:
            break
    return out


def _post_multipart(url, fields, filename, content):
    """POST multipart/form-data (used for the Canvas file-upload step)."""
    boundary = "----CanvasBridge" + uuid.uuid4().hex
    body = bytearray()
    for key, value in (fields or {}).items():
        body += ("--%s\r\n" % boundary).encode()
        body += ('Content-Disposition: form-data; name="%s"\r\n\r\n'
                 % key).encode()
        body += ("%s\r\n" % value).encode()
    body += ("--%s\r\n" % boundary).encode()
    body += ('Content-Disposition: form-data; name="file"; filename="%s"\r\n'
             % os.path.basename(filename)).encode()
    body += b"Content-Type: application/octet-stream\r\n\r\n"
    body += content + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()

    req = urllib.request.Request(url, data=bytes(body), method="POST")
    req.add_header("Content-Type",
                   "multipart/form-data; boundary=" + boundary)
    try:
        resp = urllib.request.urlopen(req, timeout=UPLOAD_TIMEOUT)
    except urllib.error.HTTPError as e:
        raise CanvasError("upload failed: "
                          + _explain(e.code, e.read().decode("utf-8",
                                                             "replace")))
    except urllib.error.URLError as e:
        raise CanvasError("upload could not reach server (%s)" % e.reason)
    return resp.read().decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _term(course):
    term = course.get("term")
    name = term.get("name") if isinstance(term, dict) else None
    return " - %s" % name if name else ""


def _self_enrollment(course):
    for e in course.get("enrollments") or []:
        if e.get("role") == "studentEnrollment" or e.get("type") == "student":
            return e
    enrolls = course.get("enrollments") or []
    return enrolls[0] if enrolls else None


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_whoami(args):
    user = api("GET", "/api/v1/users/self")
    if not args.json:
        print("Name:  %s" % user.get("name"))
        print("ID:    %s" % user.get("id"))
        if user.get("login_id"):
            print("Login: %s" % user.get("login_id"))
    return user


def cmd_courses(args):
    params = {"per_page": 100, "include[]": "enrollments"}
    if not args.all:
        params["enrollment_state"] = "active"
    courses = api("GET", "/api/v1/courses", params=params, paginate=True)
    if not args.json:
        if not courses:
            print("(no courses)")
        for c in courses:
            print("[%s] %s (%s)%s" % (c.get("id"), c.get("name"),
                                      c.get("course_code", ""), _term(c)))
    return courses


def cmd_assignments(args):
    path = "/api/v1/courses/%s/assignments" % args.course_id
    items = api("GET", path,
                params={"per_page": 100, "include[]": "submission",
                        "order_by": "due_at"},
                paginate=True)
    if not args.json:
        if not items:
            print("(no assignments)")
        for a in items:
            sub = a.get("submission") or {}
            status = "submitted" if sub.get("submitted_at") else (
                "missing" if sub.get("missing") else "not submitted")
            pts = a.get("points_possible")
            print("[%s] %s  due %s  (%s pts)  %s" % (
                a.get("id"), a.get("name"), a.get("due_at") or "-",
                pts if pts is not None else "-", status))
    return items


def cmd_submissions(args):
    path = ("/api/v1/courses/%s/assignments/%s/submissions/self"
            % (args.course_id, args.assignment_id))
    sub = api("GET", path)
    if not args.json:
        print("Attempt %s - %s" % (sub.get("attempt"),
                                   sub.get("workflow_state")))
        print("Submitted: %s" % (sub.get("submitted_at") or "-"))
        score = sub.get("score")
        total = sub.get("assignment", {}).get("points_possible") \
            if isinstance(sub.get("assignment"), dict) else None
        if score is not None:
            print("Score: %s%s" % (score, " / %s" % total if total else ""))
        if sub.get("grade") is not None:
            print("Grade: %s" % sub.get("grade"))
        if sub.get("preview_url") or sub.get("url"):
            print("URL: %s" % (sub.get("preview_url") or sub.get("url")))
    return sub


def cmd_grades(args):
    courses = api("GET", "/api/v1/courses",
                  params={"per_page": 100, "include[]": "enrollments",
                          "enrollment_state": "active"},
                  paginate=True)
    if args.course_id:
        courses = [c for c in courses if str(c.get("id")) == str(args.course_id)]
    if not args.json:
        if not courses:
            print("(no matching courses)")
        for c in courses:
            e = _self_enrollment(c) or {}
            g = e.get("grades") or {}
            score = g.get("current_score")
            grade = g.get("current_grade")
            if score is None and grade is None:
                print("[%s] %s - (no grade)" % (c.get("id"), c.get("name")))
            else:
                print("[%s] %s - %s%% (%s)" % (
                    c.get("id"), c.get("name"),
                    score if score is not None else "?", grade or "-"))
    return courses


def cmd_submit(args):
    cid, aid = args.course_id, args.assignment_id
    form = {"submission[submission_type]": ""}
    if args.text is not None:
        form["submission[submission_type]"] = "online_text_entry"
        form["submission[body]"] = args.text
    elif args.link is not None:
        form["submission[submission_type]"] = "online_url"
        form["submission[url]"] = args.link
    elif args.file is not None:
        if not os.path.isfile(args.file):
            raise CanvasError("file not found: %s" % args.file)
        fid = _upload(cid, aid, args.file)
        form["submission[submission_type]"] = "online_upload"
        form["submission[file_ids][]"] = [str(fid)]
    else:
        raise CanvasError("nothing to submit: pass --file, --text or --link")

    sub = api("POST", "/api/v1/courses/%s/assignments/%s/submissions" % (cid, aid),
              form=form)
    if not args.json:
        print("Submitted to assignment %s (course %s)." % (aid, cid))
        print("Attempt %s - state %s" % (sub.get("attempt"),
                                         sub.get("workflow_state")))
    return sub


def _upload(cid, aid, path):
    """3-step Canvas upload; returns the new file id."""
    size = os.path.getsize(path)
    name = os.path.basename(path)
    init = api("POST",
               "/api/v1/courses/%s/assignments/%s/submissions/self/files"
               % (cid, aid),
               params={"name": name, "size": size})
    if not isinstance(init, dict) or not init.get("upload_url"):
        raise CanvasError("upload setup failed: %r" % (init,))
    with open(path, "rb") as fh:
        content = fh.read()
    text = _post_multipart(init["upload_url"], init.get("upload_params"),
                           name, content)
    try:
        filedata = json.loads(text)
    except ValueError:
        raise CanvasError("upload did not return JSON: %s" % text[:200])
    if not isinstance(filedata, dict) or "id" not in filedata:
        raise CanvasError("upload returned no file id: %s" % text[:200])
    return filedata["id"]


def cmd_get(args):
    data = api("GET", args.path,
               params={"per_page": 100} if args.paginate else None,
               paginate=args.paginate)
    if not args.json:
        if isinstance(data, (dict, list)):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(data)
    return data


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(
        prog="canvas_bridge.py",
        description="Read and submit work in your school's Canvas LMS.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=os.environ.get("CANVAS_URL"),
                   help="Canvas base URL (default $env:CANVAS_URL)")
    p.add_argument("--token", default=os.environ.get("CANVAS_TOKEN"),
                   help="access token (default $env:CANVAS_TOKEN; prefer env)")
    p.add_argument("--ping", action="store_true",
                   help="check that URL + token work")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true",
                        help="print the raw JSON response")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("whoami", help="show the logged-in user", parents=[common])

    c = sub.add_parser("courses", help="list your courses", parents=[common])
    c.add_argument("--all", action="store_true",
                   help="include completed/inactive enrollments")

    a = sub.add_parser("assignments", help="list a course's assignments",
                       parents=[common])
    a.add_argument("course_id")

    s = sub.add_parser("submissions", parents=[common],
                       help="show your submission for one assignment")
    s.add_argument("course_id")
    s.add_argument("assignment_id")

    g = sub.add_parser("grades", help="show your current grades",
                       parents=[common])
    g.add_argument("course_id", nargs="?")

    su = sub.add_parser("submit", help="submit work for an assignment",
                        parents=[common])
    su.add_argument("course_id")
    su.add_argument("assignment_id")
    su.add_argument("--file", help="upload this file")
    su.add_argument("--text", help="online text entry body")
    su.add_argument("--link", help="online URL submission")

    ge = sub.add_parser("get", help="GET any API path", parents=[common])
    ge.add_argument("path")
    ge.add_argument("--paginate", action="store_true",
                    help="follow pagination on list responses")

    return p


COMMANDS = {
    "whoami": cmd_whoami,
    "courses": cmd_courses,
    "assignments": cmd_assignments,
    "submissions": cmd_submissions,
    "grades": cmd_grades,
    "submit": cmd_submit,
    "get": cmd_get,
}


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "json"):                      # e.g. bare --ping
        args.json = False
    cmd = "whoami" if args.ping else args.cmd
    if not cmd:
        parser.print_help()
        return 0
    try:
        configure(args.url, args.token)
        data = COMMANDS[cmd](args)
        if getattr(args, "json", False) and data is not None:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    except CanvasError as e:
        print("CANVAS ERROR: %s" % e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
