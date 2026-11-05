from __future__ import annotations

import json
import os
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
PORT = 8765
CONSOLE = Path(__file__).resolve().parent
INVENTORY_PATH = ROOT / "state" / "material_intelligence" / "SM3_MATERIAL_INVENTORY_CURRENT.json"
BLUEPRINT_PATH = ROOT / "state" / "material_intelligence" / "SM3_MATERIAL_AWARE_POST_BLUEPRINT_CURRENT.json"
INSTALL_REPORT_PATH = ROOT / "reports" / "09D" / "A11_A18_R10" / "SM3_09D_A11_A18_R10_INSTALL_VERIFY.json"
RUN_LOG_PATH = ROOT / "state" / "material_intelligence" / "logs" / "r10_runner.log"
RUNNER_PATH = ROOT / "SM3_09D_A11_A18_R10_RUN_v1.ps1"
RUN_LOCK = threading.Lock()


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def make_snapshot() -> dict:
    inventory = load_json(INVENTORY_PATH)
    blueprint = load_json(BLUEPRINT_PATH)
    report = load_json(INSTALL_REPORT_PATH)
    sessions = []
    for item in inventory.get("edit_sessions", []):
        if not isinstance(item, dict):
            continue
        session = {
            "project_id": item.get("project_id"),
            "content_id": item.get("content_id"),
            "edit_session_id": item.get("edit_session_id"),
            "updated_at": item.get("updated_at"),
            "status": item.get("status"),
        }
        parts = [session.get(key) for key in ("project_id", "content_id", "edit_session_id")]
        if all(parts):
            session["editor_url"] = "http://127.0.0.1:8090/production/editor/" + "/".join(quote(str(part), safe="") for part in parts)
        sessions.append(session)
    evidence = []
    for index, item in enumerate(inventory.get("stage_evidence", []), start=1):
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", ""))
        normalized = value.upper()
        untrusted = any(label in normalized for label in ("RESULTADO", "FINAL_RESULT", "FINAL_REVEAL", "FINAL_DETAIL"))
        evidence.append({
            "id": f"STAGE-{index:03d}",
            "value": value[:220],
            "value_truncated": len(value) > 220,
            "record": str(item.get("record_path", "")),
            "field": str(item.get("path", "")),
            "untrusted_final_label": untrusted,
        })

    platforms = []
    for item in blueprint.get("platform_blueprints", []):
        if isinstance(item, dict):
            platforms.append({
                "platform": item.get("platform"),
                "surface": item.get("surface"),
                "status": item.get("blueprint_status"),
                "render_authorized": item.get("render_authorized") is True,
                "publication_authorized": item.get("publication_authorized") is True,
                "context": item.get("material_context", {}),
                "blocking_reasons": item.get("blocking_reasons", []),
                "duration_bands": item.get("duration_candidate_bands", []),
            })

    try:
        log_lines = RUN_LOG_PATH.read_text(encoding="utf-8-sig").splitlines()[-24:]
    except OSError:
        log_lines = []

    return {
        "ok": bool(inventory and blueprint),
        "generated_at": inventory.get("generated_at"),
        "worker_version": report.get("worker_version"),
        "install_ok": report.get("ok") is True,
        "worker_core_mutated": report.get("worker_core_mutated"),
        "production_state_writes": report.get("production_state_writes"),
        "render_performed": report.get("render_performed"),
        "publication_performed": report.get("publication_performed"),
        "inventory": {
            "record_count": inventory.get("record_count", 0),
            "stage_evidence_count": inventory.get("stage_evidence_count", len(evidence)),
            "read_only_scan": inventory.get("read_only_scan") is True,
            "network_calls": inventory.get("network_calls", 0),
            "model_calls": inventory.get("model_calls", 0),
            "roots": inventory.get("roots", {}),
            "sessions": sessions,
            "stage_evidence": evidence,
        },
        "blueprint": {
            "generated_at": blueprint.get("generated_at"),
            "mode": blueprint.get("mode"),
            "verified_final_count": blueprint.get("stage_evidence_summary", {}).get("verified_final_count", 0),
            "untrusted_final_label_count": blueprint.get("stage_evidence_summary", {}).get("untrusted_final_label_count", 0),
            "platforms": platforms,
        },
        "links": {
            "n8n": "http://127.0.0.1:5678",
            "editor": sessions[0].get("editor_url") if sessions else None,
        },
        "activity": log_lines,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "MolotovConsole/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send_json(self, status: int, value: dict) -> None:
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _request_is_local(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0].lower()
        if host not in {"127.0.0.1", "localhost"}:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}

    def do_GET(self) -> None:
        if not self._request_is_local():
            self._send_json(403, {"ok": False, "error": "LOCAL_REQUEST_REQUIRED"})
            return
        if self.path == "/api/state":
            self._send_json(200, make_snapshot())
            return
        if self.path in {"/", "/index.html"}:
            try:
                data = (CONSOLE / "index.html").read_bytes()
            except OSError:
                self._send_json(500, {"ok": False, "error": "CONSOLE_ASSET_MISSING"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)
            return
        self._send_json(404, {"ok": False, "error": "NOT_FOUND"})

    def do_POST(self) -> None:
        if not self._request_is_local():
            self._send_json(403, {"ok": False, "error": "LOCAL_REQUEST_REQUIRED"})
            return
        if self.path != "/api/refresh":
            self._send_json(404, {"ok": False, "error": "NOT_FOUND"})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self._send_json(415, {"ok": False, "error": "JSON_REQUIRED"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1024:
                raise ValueError
            if length:
                json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "error": "INVALID_REQUEST"})
            return
        if not RUN_LOCK.acquire(blocking=False):
            self._send_json(409, {"ok": False, "error": "REFRESH_ALREADY_RUNNING"})
            return
        try:
            if not RUNNER_PATH.is_file():
                self._send_json(503, {"ok": False, "error": "R10_RUNNER_MISSING"})
                return
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                [
                    "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-File", str(RUNNER_PATH),
                    "-ProjectRoot", str(ROOT), "-Quiet",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,
                creationflags=flags,
                check=False,
            )
            if result.returncode:
                detail = (result.stderr or result.stdout or "R10_REFRESH_FAILED")[-3000:]
                self._send_json(500, {"ok": False, "error": "R10_REFRESH_FAILED", "detail": detail})
                return
            self._send_json(200, make_snapshot())
        except subprocess.TimeoutExpired:
            self._send_json(504, {"ok": False, "error": "R10_REFRESH_TIMEOUT"})
        except OSError as error:
            self._send_json(503, {"ok": False, "error": "R10_REFRESH_UNAVAILABLE", "detail": str(error)})
        finally:
            RUN_LOCK.release()


if __name__ == "__main__":
    os.chdir(ROOT)
    address = ("127.0.0.1", PORT)
    server = ThreadingHTTPServer(address, Handler)
    print(f"MOLOTOV Console: http://127.0.0.1:{PORT}", flush=True)
    threading.Timer(0.8, webbrowser.open, args=(f"http://127.0.0.1:{PORT}",)).start()
    server.serve_forever()