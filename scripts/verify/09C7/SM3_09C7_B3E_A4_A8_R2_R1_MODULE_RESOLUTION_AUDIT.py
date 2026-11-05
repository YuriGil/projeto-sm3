from __future__ import annotations

import importlib
import json
import os
import sys
import time
import traceback
import urllib.request
from pathlib import Path


result = {
    "contract_version":
        "SM3_RUNTIME_MODULE_RESOLUTION_AUDIT_V1",

    "checks":
        {},

    "pass":
        False,

    "error":
        None,
}


try:

    result["cwd"] = os.getcwd()

    result["sys_path_before"] = list(
        sys.path
    )

    result["sys_path_zero_before"] = (
        sys.path[0]
        if sys.path
        else None
    )


    worker_path = Path(
        "/app/worker_service.py"
    )

    temporal_path = Path(
        "/app/SM3_platform_temporal_validity_v1_r2.py"
    )


    result["worker_file_exists"] = (
        worker_path.is_file()
    )

    result["temporal_file_exists"] = (
        temporal_path.is_file()
    )


    pre_import_success = False
    pre_import_error = None


    try:

        import worker_service

        pre_import_success = True

    except Exception as exc:

        pre_import_error = (
            repr(
                exc
            )
        )


    result["pre_insert_import_success"] = (
        pre_import_success
    )

    result["pre_insert_import_error"] = (
        pre_import_error
    )


    if "/app" not in sys.path:

        sys.path.insert(
            0,
            "/app",
        )


    result["sys_path_after"] = list(
        sys.path
    )

    result["app_present_after"] = (
        "/app"
        in sys.path
    )


    worker = importlib.import_module(
        "worker_service"
    )

    temporal = importlib.import_module(
        "SM3_platform_temporal_validity_v1_r2"
    )


    result["post_insert_import_success"] = True

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


    health_status = None
    health_body = None
    health_json = None
    health_error = None


    for attempt in range(
        1,
        21,
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


    result[
        "original_failure_reproduced"
    ] = (
        pre_import_success is False
        and
        isinstance(
            pre_import_error,
            str,
        )
        and
        "worker_service"
        in pre_import_error
    )


    result[
        "root_cause_classification"
    ] = (
        "PYTHON_SCRIPT_MODE_SYS_PATH_OMITTED_APP"
        if result[
            "original_failure_reproduced"
        ]
        else
        "MODULE_RESOLUTION_CONTEXT_DIFFERED"
    )


    result["checks"]["WORKER_FILE_EXISTS"] = (
        result[
            "worker_file_exists"
        ]
        is True
    )

    result["checks"]["TEMPORAL_FILE_EXISTS"] = (
        result[
            "temporal_file_exists"
        ]
        is True
    )

    result["checks"]["APP_PATH_PRESENT_AFTER"] = (
        result[
            "app_present_after"
        ]
        is True
    )

    result["checks"]["POST_INSERT_IMPORT_SUCCESS"] = (
        result[
            "post_insert_import_success"
        ]
        is True
    )

    result["checks"]["WORKER_VERSION_EXACT"] = (
        result[
            "worker_version"
        ]
        == "2.35.1"
    )

    result["checks"]["WORKER_MODULE_FROM_APP"] = (
        result[
            "worker_module_file"
        ]
        == "/app/worker_service.py"
    )

    result["checks"]["TEMPORAL_MODULE_FROM_APP"] = (
        result[
            "temporal_module_file"
        ]
        == "/app/SM3_platform_temporal_validity_v1_r2.py"
    )

    result["checks"]["TEMPORAL_POLICY_EXACT"] = (
        result[
            "temporal_policy_version"
        ]
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
    )

    result["checks"]["TEMPORAL_ENGINE_EXACT"] = (
        result[
            "temporal_engine_version"
        ]
        == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
    )

    result["checks"]["TEMPORAL_REVISION_EXACT"] = (
        result[
            "temporal_implementation_revision"
        ]
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

    result["post_insert_import_success"] = False

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