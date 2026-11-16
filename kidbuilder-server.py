#!/usr/bin/env python3
"""
Kid Builder builder server - stdlib only, no pip packages.

A SEPARATE builder server for the Kid Builder iOS app. It runs on its
own port, 8081, ALONGSIDE the YewBuilder server on port 8080 - it does
not replace it, and YewBuilder never talks to it. The YewBuilder
server, its scheduled task, and its folder are left completely alone.
This server has the same shape as YewBuilder's (GET /health, POST
/build for 5 source files) plus two block endpoints, /generate-blocks
and /build-blocks, for Kid Builder.

What it does
------------
Your iPhone cannot run cargo or trunk, so this little server does the
build for it:

  iPhone --POST /build-blocks {blocks}--> this server
         --turns blocks into Yew files, runs `trunk build --release`-->
  iPhone <--{dist/ files as base64 + build log}-- this server
  iPhone --FTP upload--> ftp.mikegyver-studio.si

The server NEVER sees your FTP password. It only builds. The phone
uploads to FTP itself, using the password from its Keychain.

Run it
-------
Windows (PowerShell), in this folder - needs Rust + trunk first:
  PS> winget install Rustlang.Rustup
  PS> rustup default stable
  PS> rustup target add wasm32-unknown-unknown
  PS> cargo install trunk
  PS> python kidbuilder-server.py
  # listens on http://0.0.0.0:8081 - put that machine's LAN IP in the
  # iPhone app Settings, e.g. http://192.168.1.10:8081

API
---
  GET  /health  -> {"ok": true, "trunk": "trunk 0.22.1", "cargo": "..."}
  POST /build   -> {"files": [{"path": "index.html", "content": "..."}, ...],
                    "deploy_path": "/public_html/my-app"}   (optional)
                <- {"success": true, "log": "...",
                    "deploy_path": "/public_html/my-app",
                    "files": [{"path": "index.html", "content_base64": "..."}]}
  POST /generate-blocks -> {"project_name": "My Rocket Launch",
                            "blocks": [{"kind": "title", "text": "..."}, ...]}
                <- {"success": true, "log": "...",
                    "files": [{"path": "index.html", "content": "..."}, ...]}
                (no build, just runs kidbuilder_gen.py's generator)
  POST /build-blocks -> {"project_name": "...",
                         "blocks": [...],
                         "deploy_path": "/public_html/kids/my-rocket-launch"}
                <- same shape as /build: {"success": true, "log": "...",
                    "deploy_path": "...",
                    "files": [{"path": "index.html", "content_base64": "..."}]}
  The deploy folder is whatever the user entered on the phone's Build
  tab - the server validates it (rejects ".." escapes), normalises it
  ("/" for the site root), logs it, and echoes it back. The phone
  uploads to exactly that echoed folder. The server itself never
  deploys anywhere: it only builds.
  On build failure: {"success": false, "log": "<trunk output>", "files": []}
  On bad input: HTTP 400 with {"success": false, "log": "...", "files": []}
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# kidbuilder_gen.py lives next to this server; import it (do not copy
# the generator code here - the server is the one place that turns
# blocks into Yew files, so the phone and the server can never disagree).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kidbuilder_gen  # noqa: E402

# The only project paths a build may contain. The 5 core files are
# always required; the two SSTV files are only present when the project
# has an sstv block (Trunk copy-file links pull them into dist/).
# Anything else (notably ".." escapes) is rejected.
CORE_PATHS = {"index.html", "styles.css", "Cargo.toml", "Trunk.toml", "src/main.rs"}
ALLOWED_PATHS = CORE_PATHS | {"sstv-core.js", "kid-sstv-bridge.js"}
MAX_BODY_BYTES = 5 * 1024 * 1024
BUILD_TIMEOUT_SECONDS = 300


def normalise_deploy_path(raw):
    """Validate + normalise the deploy folder the phone sends.

    The folder is whatever the user entered on the Build tab - nothing
    is hardcoded here (yew-builder was only ever the first example).
    Returns the normalised path ("/" for the site root), or raises
    ValueError for a path that must never be used as a deploy target.
    """
    if raw is None:
        return "/"
    if not isinstance(raw, str):
        raise ValueError("deploy_path must be a string")
    path = raw.strip()
    if not path or path == "/":
        return "/"
    if "\x00" in path or "\\" in path:
        raise ValueError(f"Bad deploy_path: {raw!r} (no backslashes or NUL bytes)")
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError(f"Bad deploy_path: {raw!r} ('..' would escape the deploy folder)")
    if not parts:
        return "/"
    return "/" + "/".join(parts)


def run(cmd, cwd=None, timeout=30):
    """Run a command, return (returncode, combined stdout+stderr)."""
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s: {' '.join(cmd)}"


def tool_version(cmd):
    code, out = run(cmd, timeout=15)
    if code != 0:
        return None
    return (out or "").strip().splitlines()[0] if out.strip() else None


def build_project(files):
    """Write the five files to a temp dir, run trunk, read dist/. Returns (success, log, built_files)."""
    log_lines = []
    tmp = Path(tempfile.mkdtemp(prefix="yewbuilder-"))
    try:
        for item in files:
            path = item.get("path", "")
            content = item.get("content", "")
            if path not in ALLOWED_PATHS:
                return False, f"Rejected path: {path!r}. Only {sorted(ALLOWED_PATHS)} are allowed.", []
            dest = tmp / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            log_lines.append(f"wrote {path} ({len(content)} chars)")

        missing = CORE_PATHS - {f.get("path") for f in files}
        if missing:
            return False, f"Missing files: {sorted(missing)}", []

        trunk_toml = (tmp / "Trunk.toml").read_text(encoding="utf-8", errors="ignore")
        if 'public_url = "./"' not in trunk_toml and 'public_url="./"' not in trunk_toml:
            log_lines.append("WARNING: Trunk.toml does not set public_url = \"./\" - "
                             "the built site may 404 in a subfolder. See README.md.")

        log_lines.append("running: trunk build --release")
        code, out = run(["trunk", "build", "--release"], cwd=str(tmp),
                        timeout=BUILD_TIMEOUT_SECONDS)
        log_lines.append(out)
        if code != 0:
            return False, "\n".join(log_lines), []

        dist = tmp / "dist"
        if not dist.is_dir():
            return False, "\n".join(log_lines) + "\nERROR: trunk exited 0 but no dist/ folder appeared.", []

        built = []
        for path in sorted(dist.rglob("*")):
            if path.is_file():
                rel = path.relative_to(dist).as_posix()
                built.append({
                    "path": rel,
                    "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
                })
                log_lines.append(f"built {rel} ({path.stat().st_size} bytes)")
        if not built:
            return False, "\n".join(log_lines) + "\nERROR: dist/ is empty.", []
        return True, "\n".join(log_lines), built
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def generate_blocks(project_name, blocks):
    """Run kidbuilder_gen.py's generator. Returns (success, log, files).

    files is [{"path": ..., "content": ...}] - source files, no build.
    """
    try:
        slug, gen = kidbuilder_gen.generate_project(
            {"name": project_name, "blocks": blocks}
        )
    except (ValueError, FileNotFoundError) as exc:
        return False, str(exc), []
    files = [
        {"path": path, "content": content}
        for path, content in sorted(gen.items())
    ]
    log = "generated %d files for %r (slug %s)" % (len(files), project_name, slug)
    return True, log, files


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep stdout readable
        sys.stderr.write("[kidbuilder] " + fmt % args + "\n")

    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        """Read + parse the POST body. Returns (payload, error_response)."""
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            return None, (400, {"success": False, "log": f"Bad Content-Length: {length}", "files": []})
        try:
            payload = json.loads(self.rfile.read(length))
        except Exception as exc:
            return None, (400, {"success": False, "log": f"Invalid JSON: {exc}", "files": []})
        return payload, None

    def _handle_generate_blocks(self, payload):
        project_name = payload.get("project_name") or "My App"
        blocks = payload.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            self._send_json(400, {"success": False, "log": "Expected {\"project_name\", \"blocks\": [...]} with at least one block.", "files": []})
            return
        success, log, files = generate_blocks(project_name, blocks)
        status = 200 if success else 400
        self._send_json(status, {"success": success, "log": log, "files": files})

    def _handle_build_blocks(self, payload):
        project_name = payload.get("project_name") or "My App"
        blocks = payload.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            self._send_json(400, {"success": False, "log": "Expected {\"project_name\", \"blocks\": [...]} with at least one block.", "files": []})
            return
        try:
            deploy_path = normalise_deploy_path(payload.get("deploy_path"))
        except ValueError as exc:
            self._send_json(400, {"success": False, "log": str(exc), "files": []})
            return
        success, log, files = generate_blocks(project_name, blocks)
        if not success:
            self._send_json(400, {"success": False, "log": log, "files": []})
            return
        built_success, build_log, built = build_project(files)
        log = f"deploy target: {deploy_path}\n" + log + "\n" + build_log
        self._send_json(200, {"success": built_success, "log": log,
                              "deploy_path": deploy_path, "files": built})

    def do_GET(self):
        if self.path in ("/", "/health"):
            trunk = tool_version(["trunk", "--version"])
            cargo = tool_version(["cargo", "--version"])
            ok = trunk is not None and cargo is not None
            self._send_json(200 if ok else 503, {
                "ok": ok,
                "trunk": trunk,
                "cargo": cargo,
                "error": None if ok else "trunk and/or cargo not found on this machine - install Rust, add the wasm32 target, and `cargo install trunk`.",
            })
        else:
            self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path == "/generate-blocks":
            payload, err = self._read_json_body()
            if err is not None:
                self._send_json(err[0], err[1])
                return
            self._handle_generate_blocks(payload)
            return
        if self.path == "/build-blocks":
            payload, err = self._read_json_body()
            if err is not None:
                self._send_json(err[0], err[1])
                return
            self._handle_build_blocks(payload)
            return
        if self.path != "/build":
            self._send_json(404, {"success": False, "log": "not found", "files": []})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(400, {"success": False, "log": f"Bad Content-Length: {length}", "files": []})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except Exception as exc:
            self._send_json(400, {"success": False, "log": f"Invalid JSON: {exc}", "files": []})
            return
        files = payload.get("files")
        if not isinstance(files, list) or not files:
            self._send_json(400, {"success": False, "log": "Expected {\"files\": [...]} with the 5 project files.", "files": []})
            return
        try:
            deploy_path = normalise_deploy_path(payload.get("deploy_path"))
        except ValueError as exc:
            self._send_json(400, {"success": False, "log": str(exc), "files": []})
            return
        success, log, built = build_project(files)
        log = f"deploy target: {deploy_path}\n" + log
        self._send_json(200, {"success": success, "log": log,
                              "deploy_path": deploy_path, "files": built})


class QuietServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that stays quiet when a client just goes away.

    The iPhone closes its keep-alive connection after a request finishes,
    and Python's http.server treats that as an error and prints a full
    traceback (ConnectionResetError, WinError 10054 on Windows). The
    build already succeeded by then - the POST returned 200 before the
    phone hung up - so it is log noise, not a failure. Swallow the
    three "client went away" errors; anything else still gets logged.
    """

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


def main():
    port = int(os.environ.get("PORT", "8081"))
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    print(f"KidBuilder server on http://0.0.0.0:{port}  (trunk: {tool_version(['trunk', '--version'])})")
    print("POST /build-blocks with blocks; POST /generate-blocks for source only; GET /health to check the toolchain.")
    QuietServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
