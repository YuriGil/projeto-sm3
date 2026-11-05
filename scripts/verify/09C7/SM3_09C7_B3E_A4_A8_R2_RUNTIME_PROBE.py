from __future__ import annotations

import json
import time
import traceback
import urllib.request


result = {
    "contract_version":
        "SM3_ISOLATED_RUNTIME_BOOT_PROBE_V1",

    "checks":
        {},

    "pass":
        False,

    "error":
        None,
}


try:

    import worker_service as worker

    import SM3_platform_temporal_validity_v1_r2 as temporal


    worker_version = getattr(
        worker,
        "WORKER_VERSION",
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

    result["temporal_policy_version"] = (
        policy_version
    )

    result["temporal_engine_version"] = (
        engine_version
    )

    result["temporal_implementation_revision"] = (
        implementation_revision
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


    result["checks"]["WORKER_VERSION_EXACT"] = (
        worker_version
        == "2.35.1"
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

    result["checks"]["WORKER_MODULE_FROM_APP"] = (
        isinstance(
            result["worker_module_file"],
            str,
        )
        and
        result["worker_module_file"].startswith(
            "/app/"
        )
    )

    result["checks"]["TEMPORAL_MODULE_FROM_APP"] = (
        isinstance(
            result["temporal_module_file"],
            str,
        )
        and
        result["temporal_module_file"].startswith(
            "/app/"
        )
    )


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
                1.0
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


    result["checks"]["HEALTH_HTTP_200"] = (
        health_status
        == 200
    )

    result["checks"]["HEALTH_BODY_PRESENT"] = (
        isinstance(
            health_body,
            str,
        )
        and
        len(
            health_body.strip()
        )
        > 0
    )

    result["checks"]["HEALTH_JSON_OBJECT"] = (
        isinstance(
            health_json,
            dict,
        )
    )

    result["checks"]["HEALTH_WORKER_VERSION_EXACT"] = (
        isinstance(
            health_json,
            dict,
        )
        and
        health_json.get(
            "worker_version"
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