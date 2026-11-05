#!/usr/bin/env python3
"""Real FFmpeg render, replay, stale state, unsupported recipe, and asset tamper."""
import copy
import hashlib
import importlib.util
import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

# The previous diagnostic supplies only test import stubs when FastAPI is absent.
old = Path(__file__).resolve().parents[3] / "PROJETO_SM3_MEDIA_WORKER_v2_5_0_MANUAL_EDITOR" / "diagnostics" / "verify_editor_workspace.py"
if not old.exists():
    old = Path(__file__).resolve().parents[1] / "diagnostics" / "verify_editor_workspace.py"
if old.exists():
    previous = runpy.run_path(str(old))
    recipe = previous["recipe"]
else:
    # The shipped package must be runnable independently of the old package.
    import types
    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            super().__init__(detail)
            self.status_code, self.detail = status_code, detail
    class FastAPI:
        def __init__(self, *a, **kw): pass
        def get(self, *a, **kw): return lambda f: f
        def post(self, *a, **kw): return lambda f: f
    class FileResponse:
        def __init__(self, *a, **kw): pass
    class HTMLResponse(FileResponse): pass
    sys.modules["fastapi"] = types.SimpleNamespace(FastAPI=FastAPI, HTTPException=HTTPException)
    sys.modules["fastapi.responses"] = types.SimpleNamespace(FileResponse=FileResponse, HTMLResponse=HTMLResponse)
    sys.modules["httpx"] = types.ModuleType("httpx")
    def recipe():
        return {"variant_id":"V01","label":"Seguro","strategy":"DOCUMENTARY_SAFE","rationale":"Tattoo real",
                "media_order":["M0001"],"timeline":[{"media_id":"M0001","role":"HERO","start_seconds":0,
                "end_seconds":2,"duration_hint_seconds":2}],"framing":[{"media_id":"M0001","mode":"CONTAIN",
                "focus_x":0.5,"focus_y":0.5,"zoom_start":1,"zoom_end":1,"preserve_subject":True}],
                "text_overlays":[],"identity_application":{"density":"LOW","logo":False,"stamp":False,
                "texture":False,"frame":False,"safe_margin_percent":8},
                "color_treatment":{"style":"NEUTRAL","exposure_delta":0,"contrast_delta":0,"saturation_delta":0},
                "transition_style":"CUT","audio_strategy":"ORIGINAL_MUTED","manual_edit_intent":"Original"}

worker_file = Path(__file__).resolve().parents[1] / "worker" / "worker_service.py"
spec = importlib.util.spec_from_file_location("sm3_worker_260_test", worker_file)
worker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = worker
spec.loader.exec_module(worker)

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

def blocked(code, call):
    try:
        call()
    except worker.HTTPException as err:
        assert code in str(err.detail), str(err.detail)
    else:
        raise AssertionError("Expected fail closed: " + code)

with tempfile.TemporaryDirectory(prefix="sm3_edit_preview_") as name:
    root = Path(name).resolve()
    worker.MEDIA_ROOT = root
    worker.INBOX = root / "inbox"
    worker.PRODUCTION_STATE = root / "production_state"
    worker.PRODUCTION_VARIANTS = worker.PRODUCTION_STATE / "variant_sets"
    worker.PRODUCTION_PREVIEWS = worker.PRODUCTION_STATE / "variant_previews"
    worker.PRODUCTION_EDIT_SESSIONS = worker.PRODUCTION_STATE / "edit_sessions"
    worker.PRODUCTION_EDIT_PREVIEWS = worker.PRODUCTION_STATE / "edit_previews"
    source = worker.INBOX / "source.png"
    source.parent.mkdir(parents=True)
    from PIL import Image
    Image.new("RGB", (160, 160), (180, 20, 20)).save(source)
    project, content, session, vsid = "TATTOO_TEST", "CARROSSEL_TEST", "ES_test", "VS_test"
    base = recipe()
    base["media_order"] = ["M0001"]
    base["timeline"] = [{"media_id":"M0001","role":"HERO","start_seconds":0,"end_seconds":2,"duration_hint_seconds":2}]
    base["framing"][0]["media_id"] = "M0001"
    save(worker._production_variant_path(project, content, vsid), {
        "ok":True,"production_contract_version":"SM3_PRODUCTION_EDIT_V1","project_id":project,
        "content_id":content,"variant_set_id":vsid,"immutable_variant_set":True,"format":"CARROSSEL",
        "variants":[base],
    })
    original_dir = worker._variant_preview_dir(project, content, vsid)
    rendered = worker._render_variant_preview_video(
        base, {"M0001":worker.VariantPreviewSource(media_id="M0001",kind="image",source_path=str(source))},
        original_dir, 160, 200, 12, 3)
    save(worker._variant_preview_manifest_path(project, content, vsid), {
        "ok":True,"preview_contract_version":"SM3_VARIANT_PREVIEW_V1","variant_set_id":vsid,
        "previews":[rendered],
    })
    recipe2 = copy.deepcopy(base)
    recipe2["color_treatment"]["contrast_delta"] = 0.25
    folder = worker._edit_session_dir(project, content, session)
    state = {"ok":True,"production_contract_version":"SM3_PRODUCTION_EDIT_V1",
             "edit_session_contract_version":"SM3_EDIT_SESSION_V1", "edit_contract_version":"SM3_EDIT_RECIPE_V1",
             "project_id":project,"content_id":content,"edit_session_id":session,"variant_set_id":vsid,
             "base_variant_id":"V01","status":"SAVED","current_revision":2,"recipe":recipe2,
             "selection_evidence":{"preview_path":rendered["preview_path"],
                 "preview_sha256":rendered["preview_sha256"],"preview_contract_version":"SM3_VARIANT_PREVIEW_V1"},
             "history":[{"revision":1},{"revision":2}]}
    save(folder / "current.json", state)
    save(folder / "revision_0002.json", state)
    etag = worker._build_editor_workspace(project, content, session)["state_etag"]
    request = worker.EditPreviewRequest(project_id=project,content_id=content,edit_session_id=session,
        expected_revision=2,expected_state_etag=etag,
        source_media=[worker.EditPreviewSource(media_id="M0001",kind="image",source_path=str(source))],
        fps=12,max_seconds=3)
    first = worker.production_render_edit_preview(request)
    assert first["reused_existing"] is False and first["revision"] == 2
    assert first["preview_sha256"] != rendered["preview_sha256"]
    assert worker.production_render_edit_preview(request)["reused_existing"] is True
    assert worker.production_get_edit_preview(project,content,session,2)["preview_sha256"] == first["preview_sha256"]
    stale = request.model_copy(update={"expected_state_etag":"f"*64})
    blocked("STALE_REVISION_OR_ETAG", lambda:worker.production_render_edit_preview(stale))
    state["recipe"]["text_overlays"] = [{"text":"OVER","purpose":"HOOK","placement":"SAFE_MARGIN",
                                          "start_seconds":None,"end_seconds":None}]
    save(folder / "current.json", state)
    save(folder / "revision_0002.json", state)
    blocked("TEXT_RENDERER_NOT_READY", lambda:worker.production_render_edit_preview(
        request.model_copy(update={"expected_state_etag":worker._build_editor_workspace(project,content,session)["state_etag"]})))
    state["recipe"]["text_overlays"] = []
    save(folder / "current.json", state)
    save(folder / "revision_0002.json", state)
    Path(first["preview_path"]).write_bytes(b"TAMPERED")
    blocked("ASSET_HASH_MISMATCH", lambda:worker.production_get_edit_preview(project,content,session,2))
    blocked("ASSET_HASH_MISMATCH", lambda:worker.production_render_edit_preview(request))
print("SM3_07F_EDIT_PREVIEW_REAL_FFMPEG_PASS")
