from __future__ import annotations

import json
import sys
import time
import traceback
import urllib.request


result = {
    "contract_version":
        "SM3_ISOLATED_RUNTIME_BOOT_PROBE_V2",

    "probe_revision":
        "A8_R3_CORRECTED",

    "checks":
        {},

    "pass":
        False,

    "error":
        None,
}


try:

    # ========================================================
    # CORRECTION 1:
    # Script is executed from /tmp, so explicitly add /app.
    # ========================================================

    result["sys_path_zero_before"] = (
        sys.path[0]
        if sys.path
        else None
    )

    result["app_present_before"] = (
        "/app"
        in sys.path
    )


    if "/app" not in sys.path:

        sys.path.insert(
            0,
            "/app",
        )


    result["app_present_after"] = (
        "/app"
        in sys.path
    )


    import worker_service as worker

    import SM3_platform_temporal_validity_v1_r2 as temporal


    worker_version = getattr(
        worker,
        "WORKER_VERSION",
        None,
    )

    worker_module_file = getattr(
        worker,
        "__file__",
        None,
    )

    temporal_module_file = getattr(
        temporal,
        "__file__",
        None,
    )

    policy_version = getattr(
        temporal,
        "TEMPORAL_VALIDITY_POLICY_VERSION",
        None,
    )

    engine_version = getattr(
        temporal,
        "TEMPORAL_VALIDITY_ENGINE_VERSION",
        None,
    )

    implementation_revision = getattr(
        temporal,
        "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION",
        None,
    )


    result["worker_version"] = (
        worker_version
    )

    result["worker_module_file"] = (
        worker_module_file
    )

    result["temporal_module_file"] = (
        temporal_module_file
    )

    result["temporal_policy_version"] = (
        policy_version
    )

    result["temporal_engine_version"] = (
        engine_version
    )

    result["temporal_implementation_revision"] = (
        implementation_revision
    )


    # ========================================================
    # LOOPBACK HEALTH
    # ========================================================

    health_status = None
    health_body = None
    health_json = None
    health_error = None


    for attempt in range(
        1,
        31,
    ):

        try:

            request = urllib.request.Request(
                "http://127.0.0.1:8090/health",
                method="GET",
            )

            with urllib.request.urlopen(
                request,
                timeout=1.0,
            ) as response:

                health_status = (
                    response.status
                )

                health_body = (
                    response.read()
                    .decode(
                        "utf-8",
                        errors="replace",
                    )
                )


            health_json = json.loads(
                health_body
            )

            health_error = None

            break

        except Exception as exc:

            health_error = repr(
                exc
            )

            time.sleep(
                0.5
            )


    result["health_status"] = (
        health_status
    )

    result["health_body"] = (
        health_body
    )

    result["health_json"] = (
        health_json
    )

    result["health_last_error"] = (
        health_error
    )


    # ========================================================
    # CHECKS
    # ========================================================

    result["checks"]["APP_PATH_PRESENT_AFTER"] = (
        result[
            "app_present_after"
        ]
        is True
    )

    result["checks"]["WORKER_VERSION_EXACT"] = (
        worker_version
        == "2.35.1"
    )

    result["checks"]["WORKER_MODULE_EXACT"] = (
        worker_module_file
        == "/app/worker_service.py"
    )

    result["checks"]["TEMPORAL_MODULE_EXACT"] = (
        temporal_module_file
        == "/app/SM3_platform_temporal_validity_v1_r2.py"
    )

    result["checks"]["TEMPORAL_POLICY_EXACT"] = (
        policy_version
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
    )

    result["checks"]["TEMPORAL_ENGINE_EXACT"] = (
        engine_version
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
    )

    result["checks"]["TEMPORAL_REVISION_EXACT"] = (
        implementation_revision
        == "R2"
    )

    result["checks"]["HEALTH_HTTP_200"] = (
        health_status
        == 200
    )

    result["checks"]["HEALTH_JSON_OBJECT"] = (
        isinstance(
            health_json,
            dict,
        )
    )

    result["checks"]["HEALTH_OK_TRUE"] = (
        isinstance(
            health_json,
            dict,
        )
        and
        health_json.get(
            "ok"
        )
        is True
    )

    result["checks"]["HEALTH_SERVICE_EXACT"] = (
        isinstance(
            health_json,
            dict,
        )
        and
        health_json.get(
            "service"
        )
        == "sm3-media-worker"
    )


    # ========================================================
    # CORRECTION 2:
    # Canonical health version field is "version".
    # ========================================================

    result["checks"]["HEALTH_VERSION_FIELD_PRESENT"] = (
        isinstance(
            health_json,
            dict,
        )
        and
        "version"
        in health_json
    )

    result["checks"]["HEALTH_VERSION_EXACT"] = (
        isinstance(
            health_json,
            dict,
        )
        and
        health_json.get(
            "version"
        )
        == "2.35.1"
    )


    result["pass"] = all(
        result[
            "checks"
        ].values()
    )


except Exception:

    result["error"] = (
        traceback.format_exc()
    )


print(
    json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
    )
)