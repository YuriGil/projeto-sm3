from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(sys.argv[1])
COMPOSE_CONFIG = Path(sys.argv[2])
CANONICAL_WORKER = Path(sys.argv[3])
STAGED_WORKER = Path(sys.argv[4])
TEMPORAL = Path(sys.argv[5])
A5_PACKAGING = Path(sys.argv[6])

RUNNING_IMAGE_REF = sys.argv[7]
RUNNING_IMAGE_ID = sys.argv[8]
RESOLVED_BASE_IMAGE_ID = sys.argv[9]

ISOLATED_CONTEXT = Path(sys.argv[10])
REPORT = Path(sys.argv[11])
MANIFEST = Path(sys.argv[12])


EXPECTED_CANONICAL_SHA = (
    "cf778554e324acdc30ba60897767e97c8"
    "6dfe7fa3cc497ac0545cc71796ef89f"
)

EXPECTED_STAGED_WORKER_SHA = (
    "550664623791a9f8a021c165b47ea511"
    "3226287cab63f0732767c47c1663a77e"
)

EXPECTED_TEMPORAL_SHA = (
    "848537b62be672c51b2ecd6c4079ad20"
    "57382c01034d2bdd2b0a50191055dc4d"
)


def sha256(path: Path) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(path: Path):

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def write_json(path: Path, value):

    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


canonical_sha = sha256(
    CANONICAL_WORKER
)

staged_worker_sha = sha256(
    STAGED_WORKER
)

temporal_sha = sha256(
    TEMPORAL
)


if canonical_sha != EXPECTED_CANONICAL_SHA:

    raise SystemExit(
        "A4_A6_R2_CANONICAL_SHA_MISMATCH:"
        + canonical_sha
    )


if staged_worker_sha != EXPECTED_STAGED_WORKER_SHA:

    raise SystemExit(
        "A4_A6_R2_STAGED_WORKER_SHA_MISMATCH:"
        + staged_worker_sha
    )


if temporal_sha != EXPECTED_TEMPORAL_SHA:

    raise SystemExit(
        "A4_A6_R2_TEMPORAL_SHA_MISMATCH:"
        + temporal_sha
    )


if RUNNING_IMAGE_ID != RESOLVED_BASE_IMAGE_ID:

    raise SystemExit(
        "A4_A6_R2_RUNNING_BASE_IMAGE_ID_MISMATCH"
    )


compose = load_json(
    COMPOSE_CONFIG
)


a5_packaging = json.loads(
    A5_PACKAGING.read_text(
        encoding="utf-8-sig"
    )
)


# ============================================================
# 1. RESOLVE MEDIA-WORKER
# ============================================================

services = compose.get(
    "services"
)


if not isinstance(
    services,
    dict,
):

    raise SystemExit(
        "A4_A6_R2_COMPOSE_SERVICES_INVALID"
    )


service_name = None


for candidate in (
    "media-worker",
    "media_worker",
    "mediaworker",
):

    if candidate in services:

        service_name = candidate
        break


if service_name is None:

    raise SystemExit(
        "A4_A6_R2_MEDIA_WORKER_SERVICE_NOT_FOUND:"
        + json.dumps(
            sorted(
                services.keys()
            )
        )
    )


service = services[
    service_name
]


# ============================================================
# 2. RESOLVE BUILD TOPOLOGY
# ============================================================

build = service.get(
    "build"
)


build_context = None
dockerfile_ref = None
dockerfile_inline = None


if isinstance(
    build,
    str,
):

    build_context = build
    dockerfile_ref = "Dockerfile"


elif isinstance(
    build,
    dict,
):

    build_context = build.get(
        "context"
    )

    dockerfile_ref = build.get(
        "dockerfile",
        "Dockerfile",
    )

    dockerfile_inline = build.get(
        "dockerfile_inline"
    )


else:

    raise SystemExit(
        "A4_A6_R2_MEDIA_WORKER_BUILD_CONFIG_MISSING"
    )


if not build_context:

    raise SystemExit(
        "A4_A6_R2_MEDIA_WORKER_BUILD_CONTEXT_MISSING"
    )


context_path = Path(
    str(
        build_context
    )
)


if not context_path.is_absolute():

    context_path = (
        ROOT
        / context_path
    ).resolve()


if not context_path.exists():

    raise SystemExit(
        "A4_A6_R2_BUILD_CONTEXT_NOT_FOUND:"
        + str(
            context_path
        )
    )


dockerfile_path = None
dockerfile_text = None
dockerfile_source_kind = None


if dockerfile_inline:

    dockerfile_text = str(
        dockerfile_inline
    )

    dockerfile_source_kind = (
        "INLINE"
    )


else:

    raw_dockerfile = Path(
        str(
            dockerfile_ref
            or "Dockerfile"
        )
    )


    if raw_dockerfile.is_absolute():

        dockerfile_path = (
            raw_dockerfile
        )


    else:

        dockerfile_path = (
            context_path
            / raw_dockerfile
        ).resolve()


    if not dockerfile_path.exists():

        raise SystemExit(
            "A4_A6_R2_RESOLVED_DOCKERFILE_NOT_FOUND:"
            + str(
                dockerfile_path
            )
        )


    dockerfile_text = dockerfile_path.read_text(
        encoding="utf-8-sig"
    )


    dockerfile_source_kind = (
        "FILE"
    )


# ============================================================
# 3. DOCKERFILE INSTRUCTION MAP
# ============================================================

physical_lines = dockerfile_text.splitlines()

logical_lines = []

buffer = ""


for raw in physical_lines:

    stripped = raw.rstrip()


    if not buffer:

        buffer = stripped


    else:

        buffer = (
            buffer
            + " "
            + stripped.lstrip()
        )


    if buffer.endswith(
        "\\"
    ):

        buffer = buffer[
            :-1
        ].rstrip()

        continue


    logical_lines.append(
        buffer.strip()
    )

    buffer = ""


if buffer:

    logical_lines.append(
        buffer.strip()
    )


instructions = []


for line in logical_lines:

    if not line:
        continue


    if line.startswith(
        "#"
    ):
        continue


    match = re.match(
        r"^([A-Za-z]+)\s+(.*)$",
        line,
    )


    if not match:
        continue


    instructions.append({
        "instruction":
            match.group(
                1
            ).upper(),

        "value":
            match.group(
                2
            ).strip(),

        "raw":
            line,
    })


copy_add_instructions = [
    item
    for item in instructions
    if item[
        "instruction"
    ]
    in {
        "COPY",
        "ADD",
    }
]


worker_service_copy_mentions = [
    item
    for item in copy_add_instructions
    if "worker_service.py"
    in item[
        "value"
    ]
]


worker_directory_copy_mentions = [
    item
    for item in copy_add_instructions
    if re.search(
        r"(^|\s|[\"'])(?:\./)?worker/?(\s|[\"']|$)",
        item[
            "value"
        ],
        flags=re.IGNORECASE,
    )
]


temporal_module_copy_mentions = [
    item
    for item in copy_add_instructions
    if (
        "SM3_platform_temporal_validity_v1_r2.py"
        in item[
            "value"
        ]
    )
]


if worker_directory_copy_mentions:

    production_packaging_classification = (
        "WORKER_DIRECTORY_COPY_PRESENT"
    )


elif worker_service_copy_mentions:

    production_packaging_classification = (
        "EXPLICIT_WORKER_SERVICE_COPY"
    )


else:

    production_packaging_classification = (
        "PACKAGING_REQUIRES_FURTHER_RESOLUTION"
    )


separate_module_native_static_evidence = (
    bool(
        worker_directory_copy_mentions
    )
    or
    bool(
        temporal_module_copy_mentions
    )
)


# ============================================================
# 4. SERVICE EXECUTION TOPOLOGY
# ============================================================

compose_image_ref = service.get(
    "image"
)


service_command = service.get(
    "command"
)


service_entrypoint = service.get(
    "entrypoint"
)


service_volumes = service.get(
    "volumes",
    []
)


# ============================================================
# 5. A5 PACKAGING LINEAGE
# ============================================================

a5_packaging_checks = {
    "A5_STATUS_EXACT":
        a5_packaging.get(
            "status"
        )
        == "PACKAGING_TOPOLOGY_AUDIT_COMPLETE",

    "A5_EVIDENCE_PRESENT":
        a5_packaging.get(
            "packaging_evidence_present"
        )
        is True,

    "A5_COMPOSE_CANDIDATES_PRESENT":
        int(
            a5_packaging.get(
                "compose_candidate_count",
                0,
            )
        )
        > 0,
}


a5_packaging_pass = all(
    a5_packaging_checks.values()
)


# ============================================================
# 6. MATERIALIZE ISOLATED BUILD CONTEXT
# ============================================================

if ISOLATED_CONTEXT.exists():

    shutil.rmtree(
        ISOLATED_CONTEXT
    )


ISOLATED_CONTEXT.mkdir(
    parents=True,
    exist_ok=False,
)


isolated_worker = (
    ISOLATED_CONTEXT
    / "worker_service.py"
)


isolated_temporal = (
    ISOLATED_CONTEXT
    / "SM3_platform_temporal_validity_v1_r2.py"
)


isolated_dockerfile = (
    ISOLATED_CONTEXT
    / "Dockerfile"
)


shutil.copyfile(
    STAGED_WORKER,
    isolated_worker,
)


shutil.copyfile(
    TEMPORAL,
    isolated_temporal,
)


if sha256(
    isolated_worker
) != staged_worker_sha:

    raise SystemExit(
        "A4_A6_R2_ISOLATED_WORKER_SHA_MISMATCH"
    )


if sha256(
    isolated_temporal
) != temporal_sha:

    raise SystemExit(
        "A4_A6_R2_ISOLATED_TEMPORAL_SHA_MISMATCH"
    )


# ============================================================
# 7. ISOLATED OVERLAY DOCKERFILE
# ============================================================

dockerfile = (
    "FROM "
    + RUNNING_IMAGE_REF
    + "\n"
    "\n"
    "COPY worker_service.py /app/worker_service.py\n"
    "COPY SM3_platform_temporal_validity_v1_r2.py "
    "/app/SM3_platform_temporal_validity_v1_r2.py\n"
    "\n"
    "RUN python -m py_compile "
    "/app/worker_service.py "
    "/app/SM3_platform_temporal_validity_v1_r2.py\n"
)


isolated_dockerfile.write_text(
    dockerfile,
    encoding="utf-8",
)


# ============================================================
# 8. ATTACK ISOLATED DOCKERFILE
# ============================================================

isolated_lines = [
    line.strip()
    for line in dockerfile.splitlines()
    if line.strip()
]


from_lines = [
    line
    for line in isolated_lines
    if line.upper().startswith(
        "FROM "
    )
]


copy_lines = [
    line
    for line in isolated_lines
    if line.upper().startswith(
        "COPY "
    )
]


run_lines = [
    line
    for line in isolated_lines
    if line.upper().startswith(
        "RUN "
    )
]


entrypoint_lines = [
    line
    for line in isolated_lines
    if (
        line.upper().startswith(
            "ENTRYPOINT "
        )
        or
        line.upper().startswith(
            "CMD "
        )
    )
]


forbidden_tokens = [
    "curl ",
    "wget ",
    "apt ",
    "apt-get ",
    "apk ",
    "yum ",
    "dnf ",
    "pip install",
    "pip3 install",
    "git clone",
    "powershell ",
    "invoke-webrequest",
]


dockerfile_lower = dockerfile.lower()


forbidden_network_build_tokens = [
    token
    for token in forbidden_tokens
    if token
    in dockerfile_lower
]


expected_copy_lines = sorted([
    "COPY worker_service.py /app/worker_service.py",
    (
        "COPY SM3_platform_temporal_validity_v1_r2.py "
        "/app/SM3_platform_temporal_validity_v1_r2.py"
    ),
])


isolated_checks = {
    "BASE_IMAGE_REF_NONEMPTY":
        bool(
            RUNNING_IMAGE_REF
        ),

    "BASE_IMAGE_ID_EXACT_RUNTIME_MATCH":
        RUNNING_IMAGE_ID
        == RESOLVED_BASE_IMAGE_ID,

    "ISOLATED_WORKER_SHA_EXACT":
        sha256(
            isolated_worker
        )
        == EXPECTED_STAGED_WORKER_SHA,

    "ISOLATED_TEMPORAL_SHA_EXACT":
        sha256(
            isolated_temporal
        )
        == EXPECTED_TEMPORAL_SHA,

    "ONE_BASE_IMAGE":
        len(
            from_lines
        )
        == 1,

    "BASE_IMAGE_REF_EXACT":
        from_lines
        == [
            "FROM "
            + RUNNING_IMAGE_REF
        ],

    "COPY_SET_EXACT":
        sorted(
            copy_lines
        )
        == expected_copy_lines,

    "ONE_COMPILE_RUN":
        len(
            run_lines
        )
        == 1,

    "RUN_IS_COMPILE_ONLY":
        (
            len(
                run_lines
            )
            == 1
            and
            run_lines[
                0
            ].startswith(
                "RUN python -m py_compile "
            )
        ),

    "NO_ENTRYPOINT_OR_CMD_OVERRIDE":
        entrypoint_lines
        == [],

    "NO_BUILD_NETWORK_INSTALL_TOKEN":
        forbidden_network_build_tokens
        == [],
}


isolated_context_pass = all(
    isolated_checks.values()
)


# ============================================================
# 9. PRODUCTION TOPOLOGY CHECKS
# ============================================================

topology_checks = {
    "MEDIA_WORKER_SERVICE_FOUND":
        bool(
            service_name
        ),

    "BUILD_CONTEXT_RESOLVED":
        context_path.exists(),

    "PRODUCTION_DOCKERFILE_RESOLVED":
        bool(
            dockerfile_text
        ),

    "PRODUCTION_DOCKERFILE_HAS_INSTRUCTIONS":
        bool(
            instructions
        ),

    "A5_PACKAGING_LINEAGE_PASS":
        a5_packaging_pass,

    "RUNNING_IMAGE_REF_PRESENT":
        bool(
            RUNNING_IMAGE_REF
        ),

    "RUNNING_IMAGE_ID_MATCHES_LOCAL_REF":
        RUNNING_IMAGE_ID
        == RESOLVED_BASE_IMAGE_ID,
}


topology_pass = all(
    topology_checks.values()
)


# ============================================================
# 10. PREFLIGHT VERDICT
# ============================================================

preflight_pass = (
    topology_pass
    and
    isolated_context_pass
)


isolated_image_tag = (
    "sm3-a4-a7-temporal-2351:local"
)


next_gate = (
    "09C7-B3E-A4-A7_ISOLATED_RUNTIME_IMAGE_BUILD"
    if preflight_pass
    else
    "09C7-B3E-A4-A6_REMEDIATION_REQUIRED"
)


# ============================================================
# 11. MANIFEST
# ============================================================

manifest = {
    "contract_version":
        "SM3_ISOLATED_RUNTIME_BUILD_MANIFEST_V1",

    "phase":
        "09C7-B3E-A4-A6-R2",

    "status":
        (
            "READY_FOR_ISOLATED_BUILD"
            if preflight_pass
            else
            "BLOCKED"
        ),

    "running_image_ref":
        RUNNING_IMAGE_REF,

    "running_image_id":
        RUNNING_IMAGE_ID,

    "resolved_base_image_id":
        RESOLVED_BASE_IMAGE_ID,

    "compose_service_name":
        service_name,

    "compose_image_ref":
        compose_image_ref,

    "production_build_context":
        str(
            context_path
        ),

    "production_dockerfile_source_kind":
        dockerfile_source_kind,

    "production_dockerfile_path":
        (
            str(
                dockerfile_path
            )
            if dockerfile_path
            else None
        ),

    "production_dockerfile_sha256":
        (
            sha256(
                dockerfile_path
            )
            if dockerfile_path
            else None
        ),

    "production_packaging_classification":
        production_packaging_classification,

    "separate_module_native_static_evidence":
        separate_module_native_static_evidence,

    "worker_service_copy_mentions":
        worker_service_copy_mentions,

    "worker_directory_copy_mentions":
        worker_directory_copy_mentions,

    "temporal_module_copy_mentions":
        temporal_module_copy_mentions,

    "service_command":
        service_command,

    "service_entrypoint":
        service_entrypoint,

    "service_volumes":
        service_volumes,

    "isolated_build_context":
        str(
            ISOLATED_CONTEXT
        ),

    "isolated_worker_sha256":
        sha256(
            isolated_worker
        ),

    "isolated_temporal_sha256":
        sha256(
            isolated_temporal
        ),

    "isolated_dockerfile_sha256":
        sha256(
            isolated_dockerfile
        ),

    "isolated_image_tag":
        isolated_image_tag,

    "isolated_build_must_use_pull_false":
        True,

    "isolated_build_must_not_replace_running_container":
        True,

    "isolated_build_must_not_use_compose_up":
        True,

    "isolated_build_must_not_modify_canonical_source":
        True,

    "runtime_deployment_performed":
        False,

    "canonical_source_modified":
        False,

    "next_gate":
        next_gate,
}


write_json(
    MANIFEST,
    manifest,
)


manifest_sha = sha256(
    MANIFEST
)


# ============================================================
# 12. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3E-A4-A6-R2",

    "status":
        "ISOLATED_RUNTIME_BUILD_PREFLIGHT_COMPLETE",

    "topology_checks":
        topology_checks,

    "isolated_checks":
        isolated_checks,

    "topology_pass":
        topology_pass,

    "isolated_context_pass":
        isolated_context_pass,

    "preflight_pass":
        preflight_pass,

    "service_name":
        service_name,

    "running_image_ref":
        RUNNING_IMAGE_REF,

    "running_image_id":
        RUNNING_IMAGE_ID,

    "resolved_base_image_id":
        RESOLVED_BASE_IMAGE_ID,

    "compose_image_ref":
        compose_image_ref,

    "production_build_context":
        str(
            context_path
        ),

    "production_dockerfile_source_kind":
        dockerfile_source_kind,

    "production_dockerfile_path":
        (
            str(
                dockerfile_path
            )
            if dockerfile_path
            else None
        ),

    "production_dockerfile_sha256":
        (
            sha256(
                dockerfile_path
            )
            if dockerfile_path
            else None
        ),

    "copy_add_instruction_count":
        len(
            copy_add_instructions
        ),

    "worker_service_copy_mention_count":
        len(
            worker_service_copy_mentions
        ),

    "worker_directory_copy_mention_count":
        len(
            worker_directory_copy_mentions
        ),

    "temporal_module_copy_mention_count":
        len(
            temporal_module_copy_mentions
        ),

    "production_packaging_classification":
        production_packaging_classification,

    "separate_module_native_static_evidence":
        separate_module_native_static_evidence,

    "isolated_context":
        str(
            ISOLATED_CONTEXT
        ),

    "isolated_worker_sha256":
        sha256(
            isolated_worker
        ),

    "isolated_temporal_sha256":
        sha256(
            isolated_temporal
        ),

    "isolated_dockerfile_sha256":
        sha256(
            isolated_dockerfile
        ),

    "isolated_image_tag":
        isolated_image_tag,

    "isolated_build_executed":
        False,

    "runtime_deployment_performed":
        False,

    "canonical_source_modified":
        False,

    "compose_up_executed":
        False,

    "production_restart_executed":
        False,

    "route_called":
        False,

    "network_request_performed":
        False,

    "provider_called":
        False,

    "model_called":
        False,

    "manifest_sha256":
        manifest_sha,

    "next_gate":
        next_gate,
}


write_json(
    REPORT,
    report,
)


# ============================================================
# 13. OUTPUT
# ============================================================

print(
    "=== ISOLATED RUNTIME BUILD PREFLIGHT ==="
)


print(
    "SERVICE_NAME="
    + str(
        service_name
    )
)

print(
    "RUNNING_IMAGE_REF="
    + RUNNING_IMAGE_REF
)

print(
    "RUNNING_IMAGE_ID="
    + RUNNING_IMAGE_ID
)

print(
    "RESOLVED_BASE_IMAGE_ID="
    + RESOLVED_BASE_IMAGE_ID
)


print(
    "\n=== PRODUCTION BUILD TOPOLOGY ==="
)

print(
    "BUILD_CONTEXT="
    + str(
        context_path
    )
)

print(
    "DOCKERFILE_SOURCE_KIND="
    + str(
        dockerfile_source_kind
    )
)

print(
    "DOCKERFILE_PATH="
    + str(
        dockerfile_path
    )
)

print(
    "COPY_ADD_INSTRUCTION_COUNT="
    + str(
        len(
            copy_add_instructions
        )
    )
)

print(
    "WORKER_SERVICE_COPY_MENTION_COUNT="
    + str(
        len(
            worker_service_copy_mentions
        )
    )
)

print(
    "WORKER_DIRECTORY_COPY_MENTION_COUNT="
    + str(
        len(
            worker_directory_copy_mentions
        )
    )
)

print(
    "TEMPORAL_MODULE_COPY_MENTION_COUNT="
    + str(
        len(
            temporal_module_copy_mentions
        )
    )
)

print(
    "PRODUCTION_PACKAGING_CLASSIFICATION="
    + production_packaging_classification
)

print(
    "SEPARATE_MODULE_NATIVE_STATIC_EVIDENCE="
    + str(
        separate_module_native_static_evidence
    )
)


print(
    "\n=== ISOLATED BUILD CONTEXT ==="
)

print(
    "ISOLATED_CONTEXT="
    + str(
        ISOLATED_CONTEXT
    )
)

print(
    "ISOLATED_WORKER_SHA256="
    + report[
        "isolated_worker_sha256"
    ]
)

print(
    "ISOLATED_TEMPORAL_SHA256="
    + report[
        "isolated_temporal_sha256"
    ]
)

print(
    "ISOLATED_DOCKERFILE_SHA256="
    + report[
        "isolated_dockerfile_sha256"
    ]
)

print(
    "ISOLATED_IMAGE_TAG="
    + isolated_image_tag
)


print(
    "\n=== CHECKS ==="
)


for name,value in topology_checks.items():

    print(
        name
        + "="
        + str(
            value
        )
    )


for name,value in isolated_checks.items():

    print(
        name
        + "="
        + str(
            value
        )
    )


print(
    "\nTOPOLOGY_PASS="
    + str(
        topology_pass
    )
)

print(
    "ISOLATED_CONTEXT_PASS="
    + str(
        isolated_context_pass
    )
)

print(
    "PREFLIGHT_PASS="
    + str(
        preflight_pass
    )
)


print(
    "\nISOLATED_BUILD_EXECUTED=False"
)

print(
    "RUNTIME_DEPLOYMENT_PERFORMED=False"
)

print(
    "CANONICAL_SOURCE_MODIFIED=False"
)

print(
    "COMPOSE_UP_EXECUTED=False"
)

print(
    "PRODUCTION_RESTART_EXECUTED=False"
)

print(
    "ROUTE_CALLED=False"
)

print(
    "NETWORK_REQUEST_PERFORMED=False"
)

print(
    "PROVIDER_CALLED=False"
)

print(
    "MODEL_CALLED=False"
)


print(
    "MANIFEST_SHA256="
    + manifest_sha
)

print(
    "NEXT_GATE="
    + next_gate
)


if not preflight_pass:

    raise SystemExit(
        1
    )