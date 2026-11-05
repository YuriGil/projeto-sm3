from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


PATH = Path(sys.argv[1])


raw = PATH.read_bytes()


UTF8_BOM = bytes(
    [
        0xEF,
        0xBB,
        0xBF,
    ]
)


starts_with_bom = raw.startswith(
    UTF8_BOM
)


if starts_with_bom:

    raise SystemExit(
        "COMPOSE_CONFIG_HAS_UTF8_BOM"
    )


try:

    text = raw.decode(
        "utf-8"
    )

except UnicodeDecodeError as exc:

    raise SystemExit(
        "COMPOSE_CONFIG_UTF8_DECODE_FAILED:"
        + repr(
            exc
        )
    )


try:

    data = json.loads(
        text
    )

except Exception as exc:

    raise SystemExit(
        "COMPOSE_CONFIG_JSON_PARSE_FAILED:"
        + repr(
            exc
        )
    )


services = data.get(
    "services"
)


if not isinstance(
    services,
    dict,
):

    raise SystemExit(
        "COMPOSE_CONFIG_SERVICES_INVALID"
    )


service_names = sorted(
    services.keys()
)


media_worker_candidates = [
    name
    for name in service_names
    if name in {
        "media-worker",
        "media_worker",
        "mediaworker",
    }
]


if len(
    media_worker_candidates
) != 1:

    raise SystemExit(
        "COMPOSE_CONFIG_MEDIA_WORKER_COUNT_INVALID:"
        + str(
            len(
                media_worker_candidates
            )
        )
        + ":"
        + json.dumps(
            service_names
        )
    )


media_worker_name = media_worker_candidates[
    0
]


media_worker = services[
    media_worker_name
]


build = media_worker.get(
    "build"
)


build_present = build is not None


if not build_present:

    raise SystemExit(
        "COMPOSE_CONFIG_MEDIA_WORKER_BUILD_MISSING"
    )


sha = hashlib.sha256(
    raw
).hexdigest()


result = {
    "starts_with_utf8_bom":
        starts_with_bom,

    "utf8_decode_pass":
        True,

    "json_parse_pass":
        True,

    "service_count":
        len(
            service_names
        ),

    "media_worker_service_present":
        True,

    "media_worker_service_name":
        media_worker_name,

    "media_worker_build_present":
        build_present,

    "compose_config_sha256":
        sha,
}


print(
    "STARTS_WITH_UTF8_BOM="
    + str(
        result[
            "starts_with_utf8_bom"
        ]
    )
)

print(
    "UTF8_DECODE_PASS=True"
)

print(
    "JSON_PARSE_PASS=True"
)

print(
    "SERVICE_COUNT="
    + str(
        result[
            "service_count"
        ]
    )
)

print(
    "MEDIA_WORKER_SERVICE_PRESENT=True"
)

print(
    "MEDIA_WORKER_SERVICE_NAME="
    + media_worker_name
)

print(
    "MEDIA_WORKER_BUILD_PRESENT=True"
)

print(
    "COMPOSE_CONFIG_SHA256="
    + sha
)