from __future__ import annotations

import json
import sys
import time
import traceback
import urllib.request


result = {
    "contract_version": "SM3_A13_ISOLATED_RUNTIME_BOOT_PROBE_V2",
    "pass": False,
    "checks": {},
    "error": None,
}


try:

    if "/app" not in sys.path:
        sys.path.insert(0, "/app")

    result["app_path_present"] = "/app" in sys.path

    import worker_service as worker
    import SM3_platform_temporal_validity_v1_r2 as temporal

    result["worker_version"] = getattr(
        worker,
        "WORKER_VERSION",
        None,
    )

    result["worker_module_file"] = getattr(
        worker,
        "__file__",
        None,
    )

    result["temporal_module_file"] = getattr(
        temporal,
        "__file__",
        None,
    )

    result["temporal_policy_version"] = getattr(
        temporal,
        "TEMPORAL_VALIDITY_POLICY_VERSION",
        None,
    )

    result["temporal_engine_version"] = getattr(
        temporal,
        "TEMPORAL_VALIDITY_ENGINE_VERSION",
        None,
    )

    result["temporal_implementation_revision"] = getattr(
        temporal,
        "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION",
        None,
    )

    status = None
    body = None
    health = None
    last_error = None

    for _ in range(40):

        try:

            req = urllib.request.Request(
                "http://127.0.0.1:8090/health",
                method="GET",
            )

            with urllib.request.urlopen(
                req,
                timeout=1.0,
            ) as response:

                status = response.status

                body = response.read().decode(
                    "utf-8",
                    errors="replace",
                )

            health = json.loads(body)
            last_error = None
            break

        except Exception as exc:

            last_error = repr(exc)
            time.sleep(0.5)

    result["health_status"] = status
    result["health_body"] = body
    result["health_json"] = health
    result["health_last_error"] = last_error

    checks = result["checks"]

    checks["APP_PATH_PRESENT"] = (
        result["app_path_present"] is True
    )

    checks["WORKER_VERSION_EXACT"] = (
        result["worker_version"] == "2.35.1"
    )

    checks["WORKER_MODULE_FILE_EXACT"] = (
        result["worker_module_file"]
        == "/app/worker_service.py"
    )

    checks["TEMPORAL_MODULE_FILE_EXACT"] = (
        result["temporal_module_file"]
        == "/app/SM3_platform_temporal_validity_v1_r2.py"
    )

    checks["TEMPORAL_POLICY_EXACT"] = (
        result["temporal_policy_version"]
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
    )

    checks["TEMPORAL_ENGINE_EXACT"] = (
        result["temporal_engine_version"]
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
    )

    checks["TEMPORAL_REVISION_EXACT"] = (
        result["temporal_implementation_revision"]
        == "R2"
    )

    checks["HEALTH_HTTP_200"] = (
        status == 200
    )

    checks["HEALTH_JSON_OBJECT"] = (
        isinstance(health, dict)
    )

    checks["HEALTH_OK_TRUE"] = (
        isinstance(health, dict)
        and health.get("ok") is True
    )

    checks["HEALTH_SERVICE_EXACT"] = (
        isinstance(health, dict)
        and health.get("service") == "sm3-media-worker"
    )

    checks["HEALTH_VERSION_EXACT"] = (
        isinstance(health, dict)
        and health.get("version") == "2.35.1"
    )

    result["pass"] = all(
        checks.values()
    )

except Exception:

    result["error"] = traceback.format_exc()


print(
    json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
    )
)

if not result["pass"]:
    raise SystemExit(1)