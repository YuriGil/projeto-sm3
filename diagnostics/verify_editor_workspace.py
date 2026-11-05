#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import copy
import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path

try:
    from fastapi import HTTPException
except ModuleNotFoundError:
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class FastAPI:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return lambda function: function

        def post(self, *args, **kwargs):
            return lambda function: function

    class FileResponse:
        def __init__(self, path, media_type=None, filename=None, headers=None):
            self.path = path
            self.media_type = media_type
            self.filename = filename
            self.headers = {str(k).lower(): v for k, v in (headers or {}).items()}

    class HTMLResponse:
        def __init__(self, content, headers=None):
            self.body = str(content).encode("utf-8")
            self.headers = {str(k).lower(): v for k, v in (headers or {}).items()}

    fastapi_stub = types.ModuleType("fastapi")
    fastapi_stub.FastAPI = FastAPI
    fastapi_stub.HTTPException = HTTPException
    responses_stub = types.ModuleType("fastapi.responses")
    responses_stub.FileResponse = FileResponse
    responses_stub.HTMLResponse = HTMLResponse
    sys.modules["fastapi"] = fastapi_stub
    sys.modules["fastapi.responses"] = responses_stub

if "httpx" not in sys.modules:
    try:
        __import__("httpx")
    except ModuleNotFoundError:
        sys.modules["httpx"] = types.ModuleType("httpx")


WORKER = Path(__file__).resolve().parents[1] / "worker" / "worker_service.py"
spec = importlib.util.spec_from_file_location("sm3_worker_240", WORKER)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def recipe() -> dict:
    return {
        "variant_id": "V01",
        "label": "Documentário seguro",
        "strategy": "DOCUMENTARY_SAFE",
        "rationale": "Preservar enquadramento e leitura da tattoo.",
        "media_order": ["MEDIA_01"],
        "timeline": [{
            "media_id": "MEDIA_01", "role": "HERO", "start_seconds": 0,
            "end_seconds": 4, "duration_hint_seconds": 4,
        }],
        "framing": [{
            "media_id": "MEDIA_01", "mode": "CONTAIN", "focus_x": 0.5,
            "focus_y": 0.5, "zoom_start": 1.0, "zoom_end": 1.0,
            "preserve_subject": True,
        }],
        "text_overlays": [],
        "identity_application": {
            "density": "LOW", "logo": False, "stamp": False,
            "texture": False, "frame": False, "safe_margin_percent": 8,
        },
        "color_treatment": {
            "style": "NEUTRAL", "exposure_delta": 0,
            "contrast_delta": 0, "saturation_delta": 0,
        },
        "transition_style": "CUT",
        "audio_strategy": "ORIGINAL_MUTED",
        "manual_edit_intent": "Base segura para edição manual.",
    }


with tempfile.TemporaryDirectory(prefix="sm3_editor_workspace_") as tmp:
    root = Path(tmp).resolve()
    module.MEDIA_ROOT = root
    module.PRODUCTION_STATE = root / "production_state"
    module.PRODUCTION_VARIANTS = module.PRODUCTION_STATE / "variant_sets"
    module.PRODUCTION_PREVIEWS = module.PRODUCTION_STATE / "variant_previews"
    module.PRODUCTION_EDIT_SESSIONS = module.PRODUCTION_STATE / "edit_sessions"
    for directory in (
        module.PRODUCTION_VARIANTS,
        module.PRODUCTION_PREVIEWS,
        module.PRODUCTION_EDIT_SESSIONS,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    project_id = "TATTOO_TEST"
    content_id = "CARROSSEL_TEST"
    variant_set_id = "VS_test"
    edit_session_id = "ES_test"
    preview_path = (
        module.PRODUCTION_PREVIEWS / project_id / content_id /
        variant_set_id / "V01" / "preview.mp4"
    )
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_bytes(b"SM3 verified preview fixture")
    preview_sha256 = hashlib.sha256(preview_path.read_bytes()).hexdigest()

    variant = recipe()
    variant_path = module._production_variant_path(
        project_id, content_id, variant_set_id
    )
    write_json(variant_path, {
        "ok": True,
        "production_contract_version": "SM3_PRODUCTION_EDIT_V1",
        "project_id": project_id,
        "content_id": content_id,
        "variant_set_id": variant_set_id,
        "immutable_variant_set": True,
        "variants": [variant],
    })
    manifest_path = module._variant_preview_manifest_path(
        project_id, content_id, variant_set_id
    )
    write_json(manifest_path, {
        "ok": True,
        "preview_contract_version": "SM3_VARIANT_PREVIEW_V1",
        "variant_set_id": variant_set_id,
        "previews": [{
            "variant_id": "V01",
            "preview_path": str(preview_path),
            "preview_sha256": preview_sha256,
        }],
    })
    session_dir = module._edit_session_dir(
        project_id, content_id, edit_session_id
    )
    state = {
        "ok": True,
        "service": "sm3-media-worker",
        "version": "2.3.0",
        "production_contract_version": "SM3_PRODUCTION_EDIT_V1",
        "edit_session_contract_version": "SM3_EDIT_SESSION_V1",
        "edit_contract_version": "SM3_EDIT_RECIPE_V1",
        "edit_session_id": edit_session_id,
        "project_id": project_id,
        "content_id": content_id,
        "variant_set_id": variant_set_id,
        "base_variant_id": "V01",
        "selection_source": "HUMAN_GOOGLE_SHEETS",
        "status": "OPEN",
        "current_revision": 1,
        "history": [{"revision": 1, "at": "2026-09-18T00:00:00+00:00",
                     "change_summary": "SESSION_STARTED_FROM_VERIFIED_AI_VARIANT"}],
        "recipe": variant,
        "selection_evidence": {
            "manifest_path": str(manifest_path),
            "preview_path": str(preview_path),
            "preview_sha256": preview_sha256,
            "preview_bytes": preview_path.stat().st_size,
            "preview_contract_version": "SM3_VARIANT_PREVIEW_V1",
        },
    }
    write_json(session_dir / "current.json", state)
    write_json(session_dir / "revision_0001.json", state)

    first = module._build_editor_workspace(
        project_id, content_id, edit_session_id
    )
    second = module._build_editor_workspace(
        project_id, content_id, edit_session_id
    )
    assert first["workspace_contract_version"] == "SM3_EDITOR_WORKSPACE_V1"
    assert first["read_only"] is False
    assert first["save_contract_version"] == "SM3_EDIT_SAVE_V1"
    assert first["preview"]["verified"] is True
    assert first["preview"]["sha256"] == preview_sha256
    assert first["state_etag"] == second["state_etag"]
    assert len(first["state_etag"]) == 64
    assert all(first["capabilities"].values())
    assert first["constraints"]["publish_from_preview_forbidden"] is True

    asset = module.production_get_editor_base_preview(
        project_id, content_id, edit_session_id
    )
    assert Path(asset.path).resolve() == preview_path.resolve()
    assert asset.headers["x-sm3-preview-verified"] == "true"
    page = module.production_editor_workspace_page(
        project_id, content_id, edit_session_id
    )
    assert b"Edi\xc3\xa7\xc3\xa3o manual" in page.body
    assert b"SM3_EDITOR_WORKSPACE_V1" in page.body

    edited = copy.deepcopy(variant)
    edited["framing"][0]["focus_x"] = 0.35
    edited["text_overlays"].append({
        "text": "Arte na pele", "purpose": "CAPTION",
        "placement": "SAFE_MARGIN", "start_seconds": 0,
        "end_seconds": 3,
    })
    request = module.EditSessionSaveRequest(
        project_id=project_id, content_id=content_id,
        edit_session_id=edit_session_id, expected_revision=1,
        expected_state_etag=first["state_etag"],
        idempotency_key="test_save_key_123456",
        recipe=edited, change_summary="Ajustar foco e texto",
    )
    result = module.production_save_edit_session(request)
    assert result["reused_existing"] is False
    assert result["workspace"]["current_revision"] == 2
    assert result["workspace"]["recipe"] == edited
    saved = json.loads((session_dir / "current.json").read_text(encoding="utf-8"))
    revision = json.loads((session_dir / "revision_0002.json").read_text(encoding="utf-8"))
    assert saved == revision
    repeat = module.production_save_edit_session(request)
    assert repeat["reused_existing"] is True
    assert repeat["state"]["current_revision"] == 2

    def rejected(payload, code):
        try:
            module.production_save_edit_session(payload)
        except HTTPException as exc:
            assert exc.detail == code, exc.detail
        else:
            raise AssertionError("Expected rejection: " + code)

    reused_key = request.model_copy(update={"change_summary": "Outra edicao"})
    rejected(reused_key, "EDIT_SAVE_IDEMPOTENCY_KEY_REUSED")
    stale = request.model_copy(update={"idempotency_key": "another_save_key_123456"})
    rejected(stale, "EDIT_SAVE_STALE_REVISION_OR_ETAG")
    assert json.loads((session_dir / "current.json").read_text(encoding="utf-8")) == saved
    unsafe_recipe = copy.deepcopy(edited)
    unsafe_recipe["framing"][0]["preserve_subject"] = False
    unsafe = request.model_copy(update={
        "idempotency_key": "unsafe_save_key_123456", "expected_revision": 2,
        "expected_state_etag": result["workspace"]["state_etag"],
        "recipe": unsafe_recipe,
    })
    rejected(unsafe, "EDIT_RECIPE_INVALID:SUBJECT_PROTECTION_REQUIRED")

    crash_recipe = copy.deepcopy(edited)
    crash_recipe["color_treatment"]["contrast_delta"] = 0.25
    crash_request = request.model_copy(update={
        "idempotency_key": "crash_save_key_123456", "expected_revision": 2,
        "expected_state_etag": result["workspace"]["state_etag"],
        "recipe": crash_recipe, "change_summary": "Ajustar contraste",
    })
    candidate = copy.deepcopy(saved)
    candidate.update({"recipe": crash_recipe, "status": "SAVED", "current_revision": 3,
                      "updated_at": "2026-09-19T00:00:00+00:00", "version": "2.5.0"})
    candidate["history"].append({
        "revision": 3, "at": "2026-09-19T00:00:00+00:00",
        "change_summary": "Ajustar contraste",
        "idempotency_key": crash_request.idempotency_key,
        "request_fingerprint": module._save_fingerprint(crash_request),
        "save_contract_version": "SM3_EDIT_SAVE_V1",
        "parent_state_etag": crash_request.expected_state_etag,
    })
    write_json(session_dir / "revision_0003.json", candidate)
    recovered = module.production_save_edit_session(crash_request)
    assert recovered["reused_existing"] is True
    assert recovered["workspace"]["current_revision"] == 3
    assert recovered["workspace"]["recipe"] == crash_recipe
    assert json.loads((session_dir / "current.json").read_text(encoding="utf-8")) == candidate

    preview_path.write_bytes(b"tampered")
    try:
        module._build_editor_workspace(project_id, content_id, edit_session_id)
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail == "SELECTED_VARIANT_PREVIEW_HASH_MISMATCH"
    else:
        raise AssertionError("Tampered preview was not rejected")

health = module.health()
assert health["version"] == "2.5.0"
assert health["editor_workspace"] is True
assert health["editor_workspace_read_only"] is False
assert health["editor_workspace_asset_verified"] is True
assert health["editor_workspace_contract"] == "SM3_EDITOR_WORKSPACE_V1"
assert health["edit_session_save_contract"] == "SM3_EDIT_SAVE_V1"
print("SM3_MANUAL_EDITOR_2_5_0_PASS")
