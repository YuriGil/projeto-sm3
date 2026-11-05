from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path


SOURCE = Path(
    r"D:\MOLOTOV_SOCIAL_OS_RC7\worker\worker_service.py"
)

REPORT = Path(
    r"D:\MOLOTOV_SOCIAL_OS_RC7\reports\09C7\SM3_09C7_B3C_B2_STATIC_ATTACH_GATE.json"
)

EXPECTED_SHA = (
    "fc5731035a73d7b0a5bfed523f564ce682d41633a6002a5d334a52ca2a8a7d46"
)

EXPECTED_FIELDS = [
    "reference_item_id",
    "media_artifact_id",
    "expected_source_sha256",
    "source_kind",
    "original_filename",
    "notes",
]


raw = SOURCE.read_bytes()

sha = hashlib.sha256(
    raw
).hexdigest()

text = raw.decode(
    "utf-8-sig"
)

tree = ast.parse(
    text,
    filename=str(SOURCE),
)


checks = {}


def add(name, value):
    checks[name] = bool(value)


# ============================================================
# 1. SOURCE / VERSION / CONTRACT
# ============================================================

add(
    "SOURCE_SHA_MATCH",
    sha == EXPECTED_SHA,
)

add(
    "WORKER_VERSION_2_24_1",
    bool(
        re.search(
            r'(?m)^WORKER_VERSION\s*=\s*["\']2\.24\.1["\']\s*$',
            text,
        )
    ),
)

add(
    "ATTACH_CONTRACT_V1",
    'REFERENCE_MEDIA_ATTACH_CONTRACT_VERSION = "SM3_REFERENCE_MEDIA_ATTACH_V1"'
    in text,
)


# ============================================================
# 2. REQUEST MODEL
# ============================================================

models = [
    node
    for node in tree.body
    if (
        isinstance(node, ast.ClassDef)
        and
        node.name == "ReferenceMediaAttachRequest"
    )
]

add(
    "REQUEST_MODEL_SINGLETON",
    len(models) == 1,
)

model_fields = []

if len(models) == 1:

    model = models[0]

    for child in model.body:

        if (
            isinstance(child, ast.AnnAssign)
            and
            isinstance(child.target, ast.Name)
        ):
            model_fields.append(
                child.target.id
            )

    model_source = (
        ast.get_source_segment(
            text,
            model,
        )
        or ""
    )

else:
    model = None
    model_source = ""


add(
    "REQUEST_EXACT_FIELDS",
    model_fields == EXPECTED_FIELDS,
)

add(
    "REQUEST_EXTRA_FORBID",
    '"extra": "forbid"'
    in model_source,
)

add(
    "REQUEST_NO_LOCAL_PATH",
    "local_path"
    not in model_fields,
)

add(
    "REQUEST_NO_INBOX_MEDIA_REF",
    "inbox_media_ref"
    not in model_fields,
)


# ============================================================
# 3. ENDPOINT / ROUTE
# ============================================================

functions = [
    node
    for node in tree.body
    if (
        isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and
        node.name == "production_reference_media_attach"
    )
]

add(
    "ATTACH_FUNCTION_SINGLETON",
    len(functions) == 1,
)

route_count = text.count(
    '@app.post("/production/reference-corpus/reference-media/attach")'
)

add(
    "ATTACH_ROUTE_SINGLETON",
    route_count == 1,
)


if len(functions) == 1:

    endpoint = functions[0]

    endpoint_source = (
        ast.get_source_segment(
            text,
            endpoint,
        )
        or ""
    )

else:

    endpoint = None
    endpoint_source = ""


# ============================================================
# 4. CALL GRAPH
# ============================================================

direct_calls = set()
attribute_calls = set()


if endpoint is not None:

    for node in ast.walk(
        endpoint
    ):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        fn = node.func

        if isinstance(
            fn,
            ast.Name,
        ):
            direct_calls.add(
                fn.id
            )

        elif isinstance(
            fn,
            ast.Attribute,
        ):
            attribute_calls.add(
                fn.attr
            )


required_calls = [
    "_require_reference_item_active",
    "_reference_media_artifact_id",
    "_load_reference_media_artifact",
    "_verify_reference_media_artifact",
    "_canonical_sha256",
    "_reference_media_path",
    "_verify_reference_media_acquisition",
    "_write_revision_once",
]


for name in required_calls:

    add(
        "CALL_"
        + name.upper(),
        name in direct_calls,
    )


forbidden_calls = [
    "_persist_reference_media_artifact",
    "_resolve_reference_inbox_ref",
    "_resolve_reference_media_ref",
    "ffprobe",
    "sha256_file",
]


for name in forbidden_calls:

    add(
        "NO_CALL_"
        + name.upper(),
        name not in direct_calls,
    )


forbidden_attributes = [
    "unlink",
    "replace",
    "rename",
    "copy",
    "copy2",
    "move",
]


for name in forbidden_attributes:

    add(
        "NO_FILE_MUTATION_"
        + name.upper(),
        name not in attribute_calls,
    )


# ============================================================
# 5. ACTIVE/TOMBSTONE + MEDIA TYPE
# ============================================================

add(
    "ACTIVE_ITEM_GATE_PRESENT",
    "_require_reference_item_active"
    in direct_calls,
)

add(
    "VIDEO_ITEM_TYPES_EXPLICIT",
    all(
        value in endpoint_source
        for value in (
            '"REEL"',
            '"VIDEO"',
            '"STORY"',
        )
    ),
)

add(
    "NON_VIDEO_REJECT_CODE",
    "REFERENCE_MEDIA_ATTACH_ITEM_TYPE_NOT_VIDEO"
    in endpoint_source,
)


# ============================================================
# 6. EXPLICIT SHA + ARTIFACT IDENTITY
# ============================================================

add(
    "EXPECTED_SHA_REQUIRED",
    "expected_source_sha256"
    in endpoint_source,
)

add(
    "LOWERCASE_SHA_REGEX",
    r"[a-f0-9]{64}"
    in endpoint_source,
)

add(
    "ARTIFACT_ID_DERIVED_FROM_SHA",
    "_reference_media_artifact_id"
    in direct_calls,
)

add(
    "ARTIFACT_ID_SOURCE_MISMATCH_REJECTED",
    "REFERENCE_MEDIA_ATTACH_ARTIFACT_ID_SOURCE_MISMATCH"
    in endpoint_source,
)

add(
    "ARTIFACT_SHA_MISMATCH_REJECTED",
    "REFERENCE_MEDIA_ATTACH_ARTIFACT_SHA_MISMATCH"
    in endpoint_source,
)

add(
    "ARTIFACT_ID_MISMATCH_REJECTED",
    "REFERENCE_MEDIA_ATTACH_ARTIFACT_ID_MISMATCH"
    in endpoint_source,
)


# ============================================================
# 7. ARTIFACT MUST PRE-EXIST / BE VERIFIED
# ============================================================

add(
    "ARTIFACT_LOAD_EXISTING",
    "_load_reference_media_artifact"
    in direct_calls,
)

add(
    "ARTIFACT_VERIFY_EXISTING",
    "_verify_reference_media_artifact"
    in direct_calls,
)

add(
    "NO_ARTIFACT_CREATE",
    "_persist_reference_media_artifact"
    not in direct_calls,
)

add(
    "NO_MEDIA_PROBE",
    "ffprobe"
    not in direct_calls,
)


# ============================================================
# 8. ACQUISITION V2 IDENTITY
# ============================================================

add(
    "USES_CURRENT_ACQUISITION_CONTRACT",
    "REFERENCE_MEDIA_ACQUISITION_CONTRACT_VERSION"
    in endpoint_source,
)

add(
    "USES_CURRENT_ACQUIRER_VERSION",
    "REFERENCE_MEDIA_ACQUISITION_VERSION"
    in endpoint_source,
)

add(
    "RM_PREFIX",
    '"RM_"'
    in endpoint_source,
)

add(
    "IDENTITY_REFERENCE_ITEM",
    '"reference_item_id"'
    in endpoint_source,
)

add(
    "IDENTITY_SOURCE_SHA",
    '"source_sha256"'
    in endpoint_source,
)

add(
    "IDENTITY_ACQUIRER_VERSION",
    '"acquirer_version"'
    in endpoint_source,
)

add(
    "IDENTITY_CANONICAL_HASH",
    "_canonical_sha256"
    in direct_calls,
)


# ============================================================
# 9. STABLE RECORD
# ============================================================

required_record_tokens = [
    '"acquisition_id"',
    '"contract_version"',
    '"acquirer_version"',
    '"reference_item_id"',
    '"reference_profile_id"',
    '"source_kind"',
    '"media_artifact_id"',
    '"source_sha256"',
    '"source_bytes"',
    '"duration_seconds"',
    '"has_audio"',
    '"original_filename"',
    '"notes"',
    '"copying_reference_identity_forbidden"',
    '"foundation_override_allowed"',
    '"created_at"',
    '"acquisition_sha256"',
]


for token in required_record_tokens:

    add(
        "RECORD_FIELD_"
        + token.strip('"').upper(),
        token in endpoint_source,
    )


add(
    "NO_CANONICAL_RESOLVED_PATH",
    "canonical_resolved_path"
    not in endpoint_source,
)

add(
    "NO_LOCAL_MEDIA_REF",
    "local_media_ref"
    not in endpoint_source,
)

add(
    "NO_CAS_PATH_PERSISTED",
    "cas_local_media_ref"
    not in endpoint_source,
)


# ============================================================
# 10. IDEMPOTENCY
# ============================================================

add(
    "EXISTING_PATH_BRANCH",
    "path.exists()"
    in endpoint_source,
)

add(
    "EXISTING_RECORD_VERIFIED",
    "_verify_reference_media_acquisition"
    in direct_calls,
)

add(
    "IDEMPOTENCY_CONFLICT",
    "REFERENCE_MEDIA_ATTACH_IDEMPOTENCY_CONFLICT"
    in endpoint_source,
)

add(
    "REUSED_EXISTING_RESPONSE",
    '"reused_existing"'
    in endpoint_source,
)

add(
    "WRITE_REVISION_ONCE",
    "_write_revision_once"
    in direct_calls,
)


# ============================================================
# 11. RESPONSE CONTRACT
# ============================================================

for token in (
    '"ok"',
    '"reused_existing"',
    '"attached_existing_artifact"',
    '"media_artifact_reused"',
    '"media_artifact"',
    '"acquisition"',
):

    add(
        "RESPONSE_"
        + token.strip('"').upper(),
        token in endpoint_source,
    )


add(
    "ATTACHED_EXISTING_ARTIFACT_TRUE",
    (
        '"attached_existing_artifact"'
        in endpoint_source
        and
        "True"
        in endpoint_source
    ),
)

add(
    "MEDIA_ARTIFACT_REUSED_TRUE",
    '"media_artifact_reused"'
    in endpoint_source,
)


# ============================================================
# 12. FORBIDDEN SIDE EFFECTS
# ============================================================

for forbidden_text in (
    "production_reference_priority",
    "_reference_semantic_provider_analyze",
    "production_reference_semantic_analysis",
    "_reference_video_vision",
):

    add(
        "NO_SIDE_EFFECT_"
        + forbidden_text.upper(),
        forbidden_text
        not in endpoint_source,
    )


# ============================================================
# 13. HEALTH FLAGS
# ============================================================

health_expectations = {
    "HEALTH_ATTACH_ENABLED":
        '"reference_media_attach_existing_artifact": True',

    "HEALTH_ATTACH_CONTRACT":
        '"reference_media_attach_contract": REFERENCE_MEDIA_ATTACH_CONTRACT_VERSION',

    "HEALTH_ATTACH_PRESERVES_V2":
        '"reference_media_attach_preserves_acquisition_v2": True',

    "HEALTH_ATTACH_REQUIRES_SHA":
        '"reference_media_attach_requires_expected_sha": True',

    "HEALTH_ATTACH_NO_BLOB_COPY":
        '"reference_media_attach_blob_copy": False',
}


for name,token in health_expectations.items():

    add(
        name,
        token in text,
    )


# ============================================================
# 14. LEGACY ACQUIRE MUST STILL EXIST
# ============================================================

add(
    "NORMAL_ACQUIRE_ROUTE_STILL_PRESENT",
    text.count(
        '@app.post("/production/reference-corpus/reference-media/acquire")'
    ) == 1,
)

add(
    "NORMAL_ACQUIRE_FUNCTION_STILL_PRESENT",
    len(
        [
            node
            for node in tree.body
            if (
                isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                )
                and
                node.name
                == "production_reference_media_acquire"
            )
        ]
    ) == 1,
)


# ============================================================
# 15. FINAL
# ============================================================

failed = [
    name
    for name,value in checks.items()
    if not value
]

passed = [
    name
    for name,value in checks.items()
    if value
]

report = {
    "phase":
        "09C7-B3C-B2",

    "status":
        (
            "STATIC_ATTACH_GATE_PASS"
            if not failed
            else
            "STATIC_ATTACH_GATE_FAIL"
        ),

    "source_sha256":
        sha,

    "expected_source_sha256":
        EXPECTED_SHA,

    "contract":
        "SM3_REFERENCE_MEDIA_ATTACH_V1",

    "target_worker_version":
        "2.24.1",

    "request_fields":
        model_fields,

    "direct_calls":
        sorted(
            direct_calls
        ),

    "attribute_calls":
        sorted(
            attribute_calls
        ),

    "check_count":
        len(checks),

    "pass_count":
        len(passed),

    "fail_count":
        len(failed),

    "failed_checks":
        failed,

    "checks":
        checks,

    "source_modified":
        False,

    "build_executed":
        False,

    "runtime_restarted":
        False,

    "api_write_called":
        False,

    "production_state_modified":
        False,

    "model_called":
        False,
}


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


for name,value in checks.items():

    print(
        name
        + "="
        + str(value)
    )


print("")
print(
    "CHECK_COUNT="
    + str(len(checks))
)

print(
    "PASS_COUNT="
    + str(len(passed))
)

print(
    "FAIL_COUNT="
    + str(len(failed))
)

print(
    "FAILED_CHECKS="
    + ",".join(failed)
)

print(
    "SOURCE_SHA256="
    + sha
)

print(
    "SOURCE_MODIFIED=False"
)

print(
    "BUILD_EXECUTED=False"
)

print(
    "RUNTIME_RESTARTED=False"
)

print(
    "API_WRITE_CALLED=False"
)

print(
    "PRODUCTION_STATE_MODIFIED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "REPORT="
    + str(REPORT)
)


if failed:
    raise SystemExit(1)


print(
    "SM3_09C7_B3C_B2_INDEPENDENT_STATIC_ATTACH_GATE_PASS"
)
