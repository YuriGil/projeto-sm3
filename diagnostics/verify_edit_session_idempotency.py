#!/usr/bin/env python3
"""Contract test for SM3 edit-session start idempotency and fail-closed evidence."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import types
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
WORKER_SOURCE = PACKAGE_ROOT / "worker" / "worker_service.py"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_worker(media_root: Path):
    os.environ["MEDIA_ROOT"] = str(media_root)

    # The production image installs FastAPI/httpx. The contract test only calls
    # pure persistence functions, so lightweight stubs keep it runnable on a
    # maintenance host that does not have the HTTP stack installed.
    try:
        import httpx  # noqa: F401
    except ModuleNotFoundError:
        sys.modules["httpx"] = types.ModuleType("httpx")

    try:
        import fastapi  # noqa: F401
    except ModuleNotFoundError:
        fastapi_stub = types.ModuleType("fastapi")

        class HTTPException(Exception):
            def __init__(self, status_code: int, detail: str):
                super().__init__(detail)
                self.status_code = status_code
                self.detail = detail

        class FastAPI:
            def __init__(self, *args, **kwargs):
                pass

            @staticmethod
            def _route(*args, **kwargs):
                def decorator(function):
                    return function

                return decorator

            get = _route
            post = _route

        fastapi_stub.FastAPI = FastAPI
        fastapi_stub.HTTPException = HTTPException
        sys.modules["fastapi"] = fastapi_stub

    spec = importlib.util.spec_from_file_location("sm3_worker_test", WORKER_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("WORKER_IMPORT_SPEC_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sm3_edit_session_test_") as temp_dir:
        media_root = Path(temp_dir) / "media"
        worker = load_worker(media_root)

        project_id = "TATTOO_TEST"
        content_id = "REEL_TEST"
        variant_set_id = "VS_TEST"
        variant_id = "V01"

        variant_path = worker._production_variant_path(
            project_id, content_id, variant_set_id
        )
        write_json(
            variant_path,
            {
                "ok": True,
                "production_contract_version": "SM3_PRODUCTION_EDIT_V1",
                "project_id": project_id,
                "content_id": content_id,
                "variant_set_id": variant_set_id,
                "immutable_variant_set": True,
                "variants": [
                    {
                        "variant_id": variant_id,
                        "variant_name": "Teste idempotente",
                        "media_order": ["MEDIA_001"],
                        "timeline": [],
                        "framing": [],
                    }
                ],
            },
        )

        preview_path = (
            worker._variant_preview_dir(project_id, content_id, variant_set_id)
            / variant_id
            / "preview.mp4"
        )
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_bytes = b"SM3_EDIT_SESSION_IDEMPOTENCY_FIXTURE"
        preview_path.write_bytes(preview_bytes)
        preview_sha256 = hashlib.sha256(preview_bytes).hexdigest()

        manifest_path = worker._variant_preview_manifest_path(
            project_id, content_id, variant_set_id
        )
        write_json(
            manifest_path,
            {
                "ok": True,
                "preview_contract_version": "SM3_VARIANT_PREVIEW_V1",
                "project_id": project_id,
                "content_id": content_id,
                "variant_set_id": variant_set_id,
                "previews": [
                    {
                        "variant_id": variant_id,
                        "preview_path": str(preview_path),
                        "preview_sha256": preview_sha256,
                    }
                ],
            },
        )

        request = worker.EditSessionStartRequest(
            project_id=project_id,
            content_id=content_id,
            variant_set_id=variant_set_id,
            variant_id=variant_id,
            selection_source="HUMAN_GOOGLE_SHEETS",
            force_new=False,
        )

        first = worker.production_start_edit_session(request)
        second = worker.production_start_edit_session(request)

        assert first["edit_session_id"] == second["edit_session_id"]
        assert first["reused_existing"] is False
        assert first["idempotency_match"] == "CREATED"
        assert second["reused_existing"] is True
        assert second["idempotency_match"] == "FINGERPRINT"
        assert first["edit_session_contract_version"] == "SM3_EDIT_SESSION_V1"
        assert first["selection_evidence"]["preview_sha256"] == preview_sha256
        assert Path(first["state_path"]).is_file()

        current = json.loads(Path(first["state_path"]).read_text(encoding="utf-8"))
        revision = Path(first["state_path"]).with_name("revision_0001.json")
        assert current["edit_session_id"] == first["edit_session_id"]
        assert revision.is_file()

        preview_path.write_bytes(b"TAMPERED")
        try:
            worker.production_start_edit_session(request)
        except worker.HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == "SELECTED_VARIANT_PREVIEW_HASH_MISMATCH"
        else:
            raise AssertionError("TAMPERED_PREVIEW_WAS_ACCEPTED")

        preview_path.write_bytes(preview_bytes)
        current["edit_contract_version"] = "CORRUPTED_CONTRACT"
        write_json(Path(first["state_path"]), current)
        try:
            worker.production_start_edit_session(request)
        except worker.HTTPException as exc:
            assert exc.status_code == 409
            assert str(exc.detail).startswith(
                "EDIT_SESSION_IDEMPOTENCY_RECORD_MISMATCH:"
            )
        else:
            raise AssertionError("CORRUPTED_SESSION_STATE_WAS_ACCEPTED")

        print("SM3_EDIT_SESSION_IDEMPOTENCY_PASS")
        print(f"edit_session_id={first['edit_session_id']}")
        print(f"state_path={first['state_path']}")
        print("tamper_check=FAIL_CLOSED")
        print("state_conflict_check=FAIL_CLOSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
