from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import json
import re
import sys


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = (
    ROOT
    / "worker"
    / "worker_service.py"
)

FREEZE = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B2B_MEDIA_CENTRIC_CONTRACT_FREEZE.json"
)

B2C = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B2C_MEDIA_CENTRIC_IMPLEMENTATION.json"
)

REPORT = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B2D_MEDIA_CENTRIC_STATIC_GATE.json"
)

EXPECTED_SOURCE_SHA = (
    "602775ac25d314491283c5ffaaf0a9c5"
    "4ee41e4828bb4fba9732ff6ef93c8733"
)

EXPECTED_FREEZE_SHA = (
    "c59a5bd49b74ce6bda1a34cbf9b345e"
    "2408b5f53176975fdcde6d5cff7a1c317"
)


def sha256_file(path: Path) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


source_sha = sha256_file(
    WORKER
)


freeze_sha = sha256_file(
    FREEZE
)


if source_sha != EXPECTED_SOURCE_SHA:

    raise SystemExit(
        "SM3_09C7_B2D_SOURCE_SHA_INVALID:"
        + source_sha
    )


if freeze_sha != EXPECTED_FREEZE_SHA:

    raise SystemExit(
        "SM3_09C7_B2D_FREEZE_SHA_INVALID:"
        + freeze_sha
    )


text = WORKER.read_text(
    encoding="utf-8-sig"
)


try:

    tree = ast.parse(
        text,
        filename=str(WORKER),
    )

except SyntaxError as exc:

    raise SystemExit(
        "SM3_09C7_B2D_WORKER_SYNTAX_ERROR:"
        + str(exc)
    )


lines = text.splitlines()


functions = {}

classes = {}

assignments = {}


for node in tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):

        functions[
            node.name
        ] = node

    elif isinstance(
        node,
        ast.ClassDef,
    ):

        classes[
            node.name
        ] = node

    elif isinstance(
        node,
        ast.Assign,
    ):

        for target in node.targets:

            if isinstance(
                target,
                ast.Name,
            ):

                assignments[
                    target.id
                ] = node.value


def source_of(name: str) -> str:

    node = functions.get(
        name
    )

    if node is None:
        return ""

    return "\n".join(
        lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


def function_args(
    name: str,
) -> list[str]:

    node = functions.get(
        name
    )

    if node is None:
        return []

    return [
        arg.arg
        for arg in node.args.args
    ]


def class_fields(
    name: str,
) -> list[str]:

    node = classes.get(
        name
    )

    if node is None:
        return []

    result = []

    for child in node.body:

        if (
            isinstance(
                child,
                ast.AnnAssign,
            )
            and
            isinstance(
                child.target,
                ast.Name,
            )
        ):

            result.append(
                child.target.id
            )

    return result


def assigned_dict_keys(
    function_name: str,
    variable_name: str,
):

    fn = functions.get(
        function_name
    )

    if fn is None:
        return None

    matches = []

    for node in ast.walk(
        fn
    ):

        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if not isinstance(
            node.value,
            ast.Dict,
        ):
            continue

        if not any(
            isinstance(
                target,
                ast.Name,
            )
            and
            target.id == variable_name
            for target in node.targets
        ):
            continue

        keys = []

        for key in node.value.keys:

            if isinstance(
                key,
                ast.Constant,
            ):

                keys.append(
                    str(
                        key.value
                    )
                )

            else:

                keys.append(
                    None
                )

        matches.append(
            keys
        )

    if len(matches) != 1:
        return None

    return matches[0]


def literal_assignment(
    name: str,
):

    node = assignments.get(
        name
    )

    if node is None:
        return None

    try:

        return ast.literal_eval(
            node
        )

    except Exception:

        return None


def call_name(call: ast.Call) -> str:

    fn = call.func

    if isinstance(
        fn,
        ast.Name,
    ):
        return fn.id

    if isinstance(
        fn,
        ast.Attribute,
    ):

        parts = []

        cur = fn

        while isinstance(
            cur,
            ast.Attribute,
        ):

            parts.append(
                cur.attr
            )

            cur = cur.value

        if isinstance(
            cur,
            ast.Name,
        ):

            parts.append(
                cur.id
            )

        return ".".join(
            reversed(
                parts
            )
        )

    return ""


def function_calls(
    name: str,
) -> list[str]:

    fn = functions.get(
        name
    )

    if fn is None:
        return []

    result = []

    for node in ast.walk(
        fn
    ):

        if isinstance(
            node,
            ast.Call,
        ):

            result.append(
                call_name(
                    node
                )
            )

    return result


def callers_of(
    target: str,
) -> list[str]:

    result = []

    for name,node in functions.items():

        for child in ast.walk(
            node
        ):

            if not isinstance(
                child,
                ast.Call,
            ):
                continue

            if call_name(
                child
            ) == target:

                result.append(
                    name
                )

    return sorted(
        result
    )


def routes():

    result = []

    for name,node in functions.items():

        for decorator in node.decorator_list:

            if not isinstance(
                decorator,
                ast.Call,
            ):
                continue

            method = call_name(
                decorator
            )

            if method not in {
                "app.get",
                "app.post",
                "app.put",
                "app.delete",
                "app.patch",
            }:
                continue

            if not decorator.args:
                continue

            arg = decorator.args[0]

            if not isinstance(
                arg,
                ast.Constant,
            ):
                continue

            result.append(
                (
                    method.split(".")[-1].upper(),
                    str(arg.value),
                    name,
                )
            )

    return result


checks = []


def add(
    name: str,
    passed: bool,
    detail="",
) -> None:

    checks.append({
        "check":
            name,

        "pass":
            bool(
                passed
            ),

        "detail":
            str(
                detail
            ),
    })


# ============================================================
# 1. LINEAGE / FREEZE
# ============================================================

freeze = json.loads(
    FREEZE.read_text(
        encoding="utf-8-sig"
    )
)


b2c = json.loads(
    B2C.read_text(
        encoding="utf-8-sig"
    )
)


add(
    "SOURCE_SHA_EXPECTED",
    source_sha
    == EXPECTED_SOURCE_SHA,
    source_sha,
)


add(
    "FREEZE_SHA_EXPECTED",
    freeze_sha
    == EXPECTED_FREEZE_SHA,
    freeze_sha,
)


add(
    "WORKER_VERSION_2_24_0",
    text.count(
        'WORKER_VERSION = "2.24.0"'
    ) == 1,
)


add(
    "FREEZE_STATUS_MEDIA_CENTRIC",
    freeze[
        "status"
    ]
    == "FROZEN_MEDIA_CENTRIC_V1",
)


add(
    "FREEZE_CONTRACT_STILL_V1",
    freeze[
        "freeze"
    ][
        "contract_version"
    ]
    == "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1",
)


add(
    "FREEZE_MEDIA_CENTRIC_TRUE",
    freeze[
        "freeze"
    ][
        "identity"
    ][
        "media_centric"
    ]
    is True,
)


add(
    "FREEZE_PROVIDER_ITEM_CONTEXT_FALSE",
    freeze[
        "freeze"
    ][
        "provider"
    ][
        "item_argument_allowed"
    ]
    is False,
)


add(
    "FREEZE_STORAGE_MEDIA_CENTRIC_TRUE",
    freeze[
        "freeze"
    ][
        "storage"
    ][
        "media_centric"
    ]
    is True,
)


add(
    "B2C_STATUS_VALID",
    b2c[
        "status"
    ]
    == "MEDIA_CENTRIC_V1_IMPLEMENTED_HOST_ONLY",
)


add(
    "B2C_PARENT_MATCHES_FREEZE_SOURCE",
    b2c[
        "source_sha_before"
    ]
    == freeze[
        "host_sha256"
    ],
)


add(
    "B2C_SOURCE_MATCHES_CURRENT",
    b2c[
        "source_sha_after"
    ]
    == source_sha,
)


add(
    "B2C_45_OF_45",
    (
        b2c[
            "check_count"
        ]
        == 45
        and
        b2c[
            "pass_count"
        ]
        == 45
        and
        b2c[
            "fail_count"
        ]
        == 0
    ),
)


# ============================================================
# 2. CONTRACT CONSTANTS
# ============================================================

expected_constants = {
    "REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION":
        "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1",

    "REFERENCE_SEMANTIC_ANALYZER_VERSION":
        "SM3_REFERENCE_SEMANTIC_ANALYZER_V1",

    "REFERENCE_SEMANTIC_SCHEMA_VERSION":
        "SM3_REFERENCE_SEMANTIC_SCHEMA_V1",

    "REFERENCE_SEMANTIC_PROMPT_VERSION":
        "SM3_REFERENCE_SEMANTIC_PROMPT_V1",

    "REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION":
        "SM3_REFERENCE_SEMANTIC_PROVIDER_V1",
}


for name,expected in expected_constants.items():

    actual = literal_assignment(
        name
    )

    add(
        "CONSTANT_" + name,
        actual == expected,
        actual,
    )


# ============================================================
# 3. REQUEST MODEL
# ============================================================

request_fields = class_fields(
    "ReferenceSemanticAnalysisRequest"
)


expected_request_fields = [
    "reference_item_id",
    "acquisition_id",
    "mechanical_analysis_id",
    "priority_decision_id",
]


add(
    "REQUEST_FIELDS_EXACT",
    request_fields
    == expected_request_fields,
    request_fields,
)


for forbidden in (
    "local_media_ref",
    "source_resolved_path",
    "preference_signal",
    "notes",
    "use_latest_acquisition",
    "use_latest_mechanical",
    "use_latest_priority",
):

    add(
        "REQUEST_FORBIDS_"
        + forbidden.upper(),
        forbidden
        not in request_fields,
    )


# ============================================================
# 4. ROUTES
# ============================================================

route_set = set(
    routes()
)


expected_routes = {
    (
        "POST",
        "/production/reference-corpus/semantic-analysis",
        "production_reference_semantic_analysis",
    ),

    (
        "GET",
        "/production/reference-corpus/item/{item_id}/semantic-analyses",
        "production_reference_semantic_analyses",
    ),

    (
        "GET",
        "/production/reference-corpus/item/{item_id}/semantic-analysis/latest",
        "production_reference_semantic_analysis_latest",
    ),
}


for route in expected_routes:

    add(
        (
            "ROUTE_"
            + route[0]
            + "_"
            + route[2].upper()
        ),
        route
        in route_set,
        route[1],
    )


# ============================================================
# 5. MEDIA-CENTRIC STORAGE
# ============================================================

storage_dir_src = source_of(
    "_reference_semantic_analysis_dir"
)


storage_path_src = source_of(
    "_reference_semantic_analysis_path"
)


source_view_src = source_of(
    "_reference_semantic_source_shas_for_item"
)


add(
    "STORAGE_DIR_SIGNATURE_SOURCE_ONLY",
    function_args(
        "_reference_semantic_analysis_dir"
    )
    == [
        "source_sha256"
    ],
)


add(
    "STORAGE_PATH_SIGNATURE_MEDIA_CENTRIC",
    function_args(
        "_reference_semantic_analysis_path"
    )
    == [
        "source_sha256",
        "analysis_id",
    ],
)


add(
    "STORAGE_USES_SHA_PREFIX",
    (
        "source_sha[:2]"
        in storage_dir_src
        and
        "/ source_sha"
        in storage_dir_src
    ),
)


add(
    "STORAGE_NO_PROFILE_ID",
    "profile_id"
    not in storage_dir_src,
)


add(
    "STORAGE_NO_ITEM_ID",
    "item_id"
    not in storage_dir_src,
)


add(
    "ITEM_SOURCE_VIEW_HELPER_PRESENT",
    "_reference_semantic_source_shas_for_item"
    in functions,
)


add(
    "ITEM_SOURCE_VIEW_LOADS_HISTORICAL_ITEM",
    "_load_reference_item"
    in source_view_src,
)


add(
    "ITEM_SOURCE_VIEW_NOT_ACTIVE_GATE",
    "_require_reference_item_active"
    not in source_view_src,
)


add(
    "ITEM_SOURCE_VIEW_READS_EXPLICIT_ACQUISITIONS",
    (
        "_reference_media_dir"
        in source_view_src
        and
        "RM_*.json"
        in source_view_src
    ),
)


add(
    "ITEM_SOURCE_VIEW_VERIFIES_ACQUISITIONS",
    "_verify_reference_media_acquisition"
    in source_view_src,
)


add(
    "ITEM_SOURCE_VIEW_VALIDATES_ITEM_MATCH",
    "REFERENCE_SEMANTIC_READER_ACQUISITION_ITEM_MISMATCH"
    in source_view_src,
)


add(
    "ITEM_SOURCE_VIEW_VALIDATES_SOURCE_SHA",
    "REFERENCE_SEMANTIC_READER_SOURCE_SHA_INVALID"
    in source_view_src,
)


# ============================================================
# 6. ENGINE
# ============================================================

engine_name = (
    "production_reference_semantic_analysis"
)

engine_src = source_of(
    engine_name
)

engine_calls = function_calls(
    engine_name
)


for required_call in (
    "_require_reference_item_active",
    "_reference_semantic_load_acquisition",
    "_resolve_reference_acquisition_source",
    "sha256_file",
    "_reference_semantic_load_mechanical",
    "_reference_semantic_contact_sheet",
    "_reference_semantic_analysis_path",
    "_verify_reference_semantic_analysis",
    "_reference_semantic_authorizing_priority",
    "_reference_semantic_provider_analyze",
    "_write_revision_once",
):

    add(
        "ENGINE_CALLS_"
        + required_call.upper(),
        required_call
        in engine_calls,
    )


add(
    "ENGINE_REQUIRES_MEDIA_ARTIFACT",
    "REFERENCE_SEMANTIC_MEDIA_ARTIFACT_REQUIRED"
    in engine_src,
)


add(
    "ENGINE_VERIFIES_SOURCE_SHA",
    "REFERENCE_SEMANTIC_SOURCE_SHA_MISMATCH"
    in engine_src,
)


add(
    "ENGINE_VERIFIES_MEDIA_ARTIFACT_LINK",
    "REFERENCE_SEMANTIC_MEDIA_ARTIFACT_MISMATCH"
    in engine_src,
)


add(
    "ENGINE_EXPLICIT_PRIORITY_ID_REQUIRED",
    "REFERENCE_SEMANTIC_PRIORITY_DECISION_ID_REQUIRED"
    in engine_src,
)


add(
    "ENGINE_NO_DIRECT_HTTP",
    "httpx.Client"
    not in engine_src,
)


# ============================================================
# 7. IDENTITY
# ============================================================

expected_identity = [
    "source_sha256",
    "mechanical_analysis_id",
    "mechanical_analysis_sha256",
    "contact_sheet_sha256",
    "semantic_analyzer_version",
    "semantic_schema_version",
    "semantic_prompt_version",
    "semantic_provider_contract_version",
    "vision_provider",
    "vision_model",
]


engine_identity = assigned_dict_keys(
    engine_name,
    "identity",
)


verifier_identity = assigned_dict_keys(
    "_verify_reference_semantic_analysis",
    "identity",
)


add(
    "ENGINE_IDENTITY_EXACT",
    engine_identity
    == expected_identity,
    engine_identity,
)


add(
    "VERIFIER_IDENTITY_EXACT",
    verifier_identity
    == expected_identity,
    verifier_identity,
)


for forbidden in (
    "reference_item_id",
    "reference_profile_id",
    "acquisition_id",
    "priority_decision_id",
    "priority_evidence_fingerprint",
    "network",
    "item_type",
    "caption",
    "local_media_ref",
    "source_resolved_path",
    "contact_sheet_path",
    "preference_signal",
    "notes",
    "created_at",
    "vision_response_id",
):

    add(
        "IDENTITY_EXCLUDES_"
        + forbidden.upper(),
        (
            engine_identity is not None
            and
            forbidden
            not in engine_identity
        ),
    )


# ============================================================
# 8. CONTACT SHEET BINDING
# ============================================================

contact_src = source_of(
    "_reference_semantic_contact_sheet"
)


add(
    "CONTACT_HELPER_REQUIRES_PATH",
    "REFERENCE_SEMANTIC_CONTACT_SHEET_REQUIRED"
    in contact_src,
)


add(
    "CONTACT_HELPER_REQUIRES_HASH",
    "REFERENCE_SEMANTIC_CONTACT_SHEET_HASH_INVALID"
    in contact_src,
)


add(
    "CONTACT_HELPER_VERIFIES_PHYSICAL_HASH",
    (
        "sha256_file"
        in contact_src
        and
        "REFERENCE_SEMANTIC_CONTACT_SHEET_HASH_MISMATCH"
        in contact_src
    ),
)


add(
    "CONTACT_HASH_EXPLICITLY_IN_ENGINE_IDENTITY",
    (
        engine_identity is not None
        and
        "contact_sheet_sha256"
        in engine_identity
    ),
)


# ============================================================
# 9. PROVIDER INPUT BOUNDARY
# ============================================================

provider_name = (
    "_reference_semantic_provider_analyze"
)

provider_src = source_of(
    provider_name
)


add(
    "PROVIDER_ARGS_EXACT_MEDIA_ONLY",
    function_args(
        provider_name
    )
    == [
        "contact_sheet",
        "mechanical",
    ],
)


add(
    "PROVIDER_CALLER_EXACTLY_ENGINE",
    callers_of(
        provider_name
    )
    == [
        engine_name
    ],
    callers_of(
        provider_name
    ),
)


add(
    "PROVIDER_OWNS_HTTP",
    "httpx.Client"
    in provider_src,
)


add(
    "PROVIDER_USES_CANONICAL_CONTACT_IMAGE",
    "_image_data_url"
    in provider_src,
)


add(
    "PROVIDER_USES_MECHANICAL_PAYLOAD",
    (
        'mechanical.get('
        in provider_src
        and
        '"mechanical"'
        in provider_src
    ),
)


add(
    "PROVIDER_HAS_NO_ITEM_ARGUMENT",
    "item"
    not in function_args(
        provider_name
    ),
)


add(
    "PROVIDER_HAS_NO_ITEM_GET",
    "item.get("
    not in provider_src,
)


add(
    "PROVIDER_HAS_NO_PROFILE_CONTEXT",
    "reference_profile_id"
    not in provider_src,
)


add(
    "PROVIDER_HAS_NO_REQUEST_CONTEXT",
    "reference_item_id"
    not in provider_src,
)


add(
    "PROVIDER_PROMPT_FORBIDS_ITEM_CONTEXT",
    (
        "Não utilize caption"
        in provider_src
        and
        "ReferenceItem"
        in provider_src
    ),
)


add(
    "PROVIDER_PROMPT_NO_PERSON_IDENTIFICATION",
    "NÃO identifique pessoas"
    in provider_src,
)


add(
    "PROVIDER_PROMPT_COPYING_FORBIDDEN",
    "NÃO copie"
    in provider_src,
)


add(
    "PROVIDER_PROMPT_FOUNDATION_PROTECTED",
    "NÃO altere a FOUNDATION"
    in provider_src,
)


add(
    "PROVIDER_CLIENT_REQUEST_ID_MEDIA_BASED",
    "source_sha[:16]"
    in provider_src,
)


# ============================================================
# 10. CACHE / PRIORITY / PROVIDER ORDERING
# ============================================================

cache_index = engine_src.find(
    "if path.exists():"
)


priority_index = engine_src.find(
    "_reference_semantic_authorizing_priority("
)


provider_index = engine_src.find(
    "_reference_semantic_provider_analyze("
)


write_index = engine_src.find(
    "_write_revision_once("
)


add(
    "CACHE_BRANCH_FOUND",
    cache_index >= 0,
    cache_index,
)


add(
    "CACHE_BEFORE_PRIORITY",
    (
        cache_index >= 0
        and
        priority_index > cache_index
    ),
    (
        str(cache_index)
        + ":"
        + str(priority_index)
    ),
)


add(
    "PRIORITY_BEFORE_PROVIDER",
    (
        priority_index >= 0
        and
        provider_index > priority_index
    ),
)


add(
    "PROVIDER_BEFORE_WRITE",
    (
        provider_index >= 0
        and
        write_index > provider_index
    ),
)


cache_segment = (
    engine_src[
        cache_index:
        priority_index
    ]
    if (
        cache_index >= 0
        and
        priority_index > cache_index
    )
    else ""
)


add(
    "CACHE_HIT_NO_PRIORITY_GENERATION_GATE",
    "_reference_semantic_authorizing_priority"
    not in cache_segment,
)


add(
    "CACHE_HIT_NO_PROVIDER_CALL",
    "_reference_semantic_provider_analyze"
    not in cache_segment,
)


add(
    "CACHE_HIT_NO_WRITE",
    "_write_revision_once"
    not in cache_segment,
)


add(
    "CACHE_HIT_MARKS_PROVIDER_FALSE",
    (
        '"provider_called"'
        in cache_segment
        and
        "False"
        in cache_segment
    ),
)


add(
    "CACHE_HIT_MARKS_PRIORITY_ALLOW_FALSE",
    (
        '"priority_generation_allow_checked"'
        in cache_segment
        and
        "False"
        in cache_segment
    ),
)


miss_segment = (
    engine_src[
        priority_index:
    ]
    if priority_index >= 0
    else ""
)


add(
    "CACHE_MISS_PRIORITY_GATE_PRESENT",
    "_reference_semantic_authorizing_priority"
    in miss_segment,
)


add(
    "CACHE_MISS_PROVIDER_PRESENT",
    "_reference_semantic_provider_analyze"
    in miss_segment,
)


add(
    "CACHE_MISS_MARKS_PROVIDER_TRUE",
    (
        '"provider_called"'
        in miss_segment
        and
        "True"
        in miss_segment
    ),
)


add(
    "CACHE_MISS_MARKS_PRIORITY_ALLOW_TRUE",
    (
        '"priority_generation_allow_checked"'
        in miss_segment
        and
        "True"
        in miss_segment
    ),
)


# ============================================================
# 11. PRIORITY FAIL-CLOSED GENERATION GATE
# ============================================================

priority_src = source_of(
    "_reference_semantic_authorizing_priority"
)


for marker in (
    "REFERENCE_SEMANTIC_PRIORITY_DECISION_ID_REQUIRED",
    "REFERENCE_SEMANTIC_PRIORITY_DECISION_NOT_FOUND",
    "REFERENCE_SEMANTIC_PRIORITY_SOURCE_MISMATCH",
    "REFERENCE_SEMANTIC_PRIORITY_MECHANICAL_MISMATCH",
    "REFERENCE_PRIORITY_DECISION_STALE",
    "REFERENCE_SEMANTIC_PRIORITY_DECISION_NOT_CURRENT",
    "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:",
):

    add(
        "PRIORITY_GATE_HAS_"
        + re.sub(
            r"[^A-Z0-9]+",
            "_",
            marker.upper(),
        ).strip("_"),
        marker
        in priority_src,
    )


add(
    "PRIORITY_GATE_RECOMPUTES_CURRENT_EVIDENCE",
    "_reference_priority_current_evidence"
    in priority_src,
)


add(
    "PRIORITY_GATE_USES_CURRENT_ENGINE_VERSION",
    "REFERENCE_PRIORITY_ENGINE_VERSION"
    in priority_src,
)


# ============================================================
# 12. RSA RECORD
# ============================================================

record_keys = assigned_dict_keys(
    engine_name,
    "rec",
)


required_creation_fields = {
    "creation_reference_item_id",
    "creation_reference_profile_id",
    "creation_acquisition_id",
    "creation_priority_decision_id",
    "creation_priority_evidence_fingerprint",
}


add(
    "RSA_RECORD_FOUND",
    record_keys is not None,
)


add(
    "RSA_CREATION_PROVENANCE_COMPLETE",
    (
        record_keys is not None
        and
        required_creation_fields.issubset(
            set(
                record_keys
            )
        )
    ),
    record_keys,
)


for forbidden in (
    "reference_item_id",
    "reference_profile_id",
    "acquisition_id",
    "priority_decision_id",
    "priority_evidence_fingerprint",
    "local_media_ref",
    "source_resolved_path",
    "contact_sheet_path",
    "preference_signal",
    "network",
    "item_type",
    "caption",
):

    add(
        "RSA_RECORD_FORBIDS_DIRECT_"
        + forbidden.upper(),
        (
            record_keys is not None
            and
            forbidden
            not in record_keys
        ),
    )


for required in (
    "semantic_analysis_id",
    "provider_contract_version",
    "media_artifact_id",
    "source_sha256",
    "mechanical_analysis_id",
    "mechanical_analysis_sha256",
    "contact_sheet_sha256",
    "vision_provider",
    "vision_model",
    "vision_response_id",
    "semantic_confidence",
    "semantic",
    "created_at",
    "copying_forbidden",
    "foundation_override_allowed",
):

    add(
        "RSA_RECORD_HAS_"
        + required.upper(),
        (
            record_keys is not None
            and
            required
            in record_keys
        ),
    )


add(
    "RSA_RECORD_CANONICAL_HASH_COMPUTED",
    "semantic_analysis_sha256"
    in engine_src,
)


add(
    "RSA_WRITE_ONCE",
    "_write_revision_once"
    in engine_calls,
)


# ============================================================
# 13. RSA VERIFIER
# ============================================================

verifier_src = source_of(
    "_verify_reference_semantic_analysis"
)


for marker in (
    "REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_MISMATCH",
    "REFERENCE_SEMANTIC_ANALYZER_VERSION_MISMATCH",
    "REFERENCE_SEMANTIC_SCHEMA_VERSION_MISMATCH",
    "REFERENCE_SEMANTIC_PROMPT_VERSION_MISMATCH",
    "REFERENCE_SEMANTIC_PROVIDER_CONTRACT_MISMATCH",
    "REFERENCE_SEMANTIC_SOURCE_SHA_INVALID",
    "REFERENCE_SEMANTIC_MECHANICAL_HASH_INVALID",
    "REFERENCE_SEMANTIC_CONTACT_SHEET_HASH_INVALID",
    "REFERENCE_SEMANTIC_PRIORITY_EVIDENCE_HASH_INVALID",
    "REFERENCE_SEMANTIC_PAYLOAD_INVALID",
    "REFERENCE_SEMANTIC_PAYLOAD_FIELDS_INVALID",
    "REFERENCE_SEMANTIC_PAYLOAD_TYPE_INVALID",
    "REFERENCE_SEMANTIC_PAYLOAD_CONFIDENCE_INVALID",
    "REFERENCE_SEMANTIC_CONFIDENCE_MISMATCH",
    "REFERENCE_SEMANTIC_ANALYSIS_IDENTITY_MISMATCH",
    "REFERENCE_SEMANTIC_COPYING_POLICY_INVALID",
    "REFERENCE_SEMANTIC_FOUNDATION_POLICY_INVALID",
    "REFERENCE_SEMANTIC_ANALYSIS_INTEGRITY_FAILED",
):

    add(
        "VERIFIER_HAS_"
        + re.sub(
            r"[^A-Z0-9]+",
            "_",
            marker.upper(),
        ).strip("_"),
        marker
        in verifier_src,
    )


add(
    "VERIFIER_USES_ACTUAL_SCHEMA",
    "schema=REFERENCE_SEMANTIC_SCHEMA"
    in verifier_src,
)


add(
    "VERIFIER_REBUILDS_MEDIA_IDENTITY",
    verifier_identity
    == expected_identity,
)


add(
    "VERIFIER_REJECTS_OLD_DIRECT_CONTEXT",
    (
        "REFERENCE_SEMANTIC_FORBIDDEN_PERSISTED_FIELD"
        in verifier_src
        and
        '"reference_item_id"'
        in verifier_src
        and
        '"caption"'
        in verifier_src
    ),
)


add(
    "VERIFIER_CHECKS_CANONICAL_RECORD_HASH",
    (
        "semantic_analysis_sha256"
        in verifier_src
        and
        "_canonical_sha256"
        in verifier_src
    ),
)


# ============================================================
# 14. SEMANTIC SCHEMA
# ============================================================

schema = literal_assignment(
    "REFERENCE_SEMANTIC_SCHEMA"
)


expected_semantic_fields = {
    "hook_duration_s",
    "camera_motion",
    "subject_scale",
    "subject_coverage",
    "text_density",
    "text_position",
    "transition_style",
    "speed_ramp",
    "identity_usage",
    "tattoo_presentation",
    "story_structure",
    "analysis_confidence",
    "notes",
}


schema_fields = (
    set(
        schema.get(
            "properties",
            {}
        ).keys()
    )
    if isinstance(
        schema,
        dict,
    )
    else set()
)


schema_required = (
    set(
        schema.get(
            "required",
            []
        )
    )
    if isinstance(
        schema,
        dict,
    )
    else set()
)


add(
    "SEMANTIC_SCHEMA_FIELDS_EXACT",
    schema_fields
    == expected_semantic_fields,
    sorted(
        schema_fields
    ),
)


add(
    "SEMANTIC_SCHEMA_REQUIRED_EXACT",
    schema_required
    == expected_semantic_fields,
)


add(
    "SEMANTIC_SCHEMA_ADDITIONAL_PROPERTIES_FALSE",
    (
        isinstance(
            schema,
            dict,
        )
        and
        schema.get(
            "additionalProperties"
        )
        is False
    ),
)


for objective in (
    "cuts_per_10s",
    "median_shot_s",
    "beat_sync",
    "color_contrast",
    "color_saturation",
    "color_temperature",
    "sharpness_grain",
):

    add(
        "SCHEMA_FORBIDS_OBJECTIVE_"
        + objective.upper(),
        objective
        not in schema_fields,
    )


# ============================================================
# 15. READERS
# ============================================================

reader_src = source_of(
    "production_reference_semantic_analyses"
)


latest_src = source_of(
    "production_reference_semantic_analysis_latest"
)


add(
    "READER_USES_ITEM_SOURCE_VIEW",
    "_reference_semantic_source_shas_for_item"
    in reader_src,
)


add(
    "READER_USES_MEDIA_STORAGE",
    "_reference_semantic_analysis_dir"
    in reader_src,
)


add(
    "READER_VERIFIES_RSA",
    "_verify_reference_semantic_analysis"
    in reader_src,
)


add(
    "READER_DEDUPLICATES_RSA_IDS",
    "seen_ids"
    in reader_src,
)


add(
    "READER_CHECKS_STORAGE_SOURCE_MATCH",
    "REFERENCE_SEMANTIC_READER_STORAGE_SOURCE_MISMATCH"
    in reader_src,
)


add(
    "READER_HISTORICAL_NO_ACTIVE_GATE",
    "_require_reference_item_active"
    not in reader_src,
)


add(
    "LATEST_USES_CONTEXTUAL_READER",
    "production_reference_semantic_analyses"
    in latest_src,
)


# ============================================================
# 16. NO OLD RECOMPUTATION / FEATURE MEMORY
# ============================================================

for forbidden_call in (
    "make_contact_sheet",
    "_reference_cut_metrics",
    "_reference_audio_onsets",
    "_reference_color_stats",
):

    add(
        "ENGINE_NO_"
        + forbidden_call.upper(),
        forbidden_call
        not in engine_calls,
    )


add(
    "ENGINE_NO_FEATURE_WRITE",
    (
        "production_reference_feature"
        not in engine_calls
        and
        "ReferenceFeatureObservationRequest"
        not in engine_src
    ),
)


add(
    "ENGINE_NO_PREFERENCE_SIGNAL",
    "preference_signal"
    not in engine_src,
)


add(
    "ENGINE_NO_REQUEST_NOTES",
    "req.notes"
    not in engine_src,
)


# ============================================================
# 17. LEGACY WRITE PATH
# ============================================================

legacy_src = source_of(
    "production_reference_video_analysis"
)


add(
    "LEGACY_VIDEO_WRITE_DISABLED",
    "REFERENCE_VIDEO_ANALYSIS_LEGACY_WRITE_DISABLED_USE_SEMANTIC_ANALYSIS"
    in legacy_src,
)


add(
    "LEGACY_VIDEO_NO_VISION_CALL",
    "_reference_video_vision"
    not in function_calls(
        "production_reference_video_analysis"
    ),
)


add(
    "LEGACY_VISION_ZERO_CALLERS",
    callers_of(
        "_reference_video_vision"
    )
    == [],
    callers_of(
        "_reference_video_vision"
    ),
)


add(
    "LEGACY_HISTORICAL_GET_PRESERVED",
    "production_reference_video_analysis_latest"
    in functions,
)


# ============================================================
# 18. HEALTH
# ============================================================

health_src = source_of(
    "health"
)


health_markers = {
    "HEALTH_MEDIA_CENTRIC":
        '"reference_semantic_media_centric": True',

    "HEALTH_PROVIDER_ITEM_CONTEXT_FALSE":
        '"reference_semantic_item_context_in_provider": False',

    "HEALTH_CONTACT_HASH_IDENTITY":
        '"reference_semantic_contact_sheet_hash_in_identity": True',

    "HEALTH_STORAGE_MEDIA_CENTRIC":
        '"reference_semantic_storage_media_centric": True',

    "HEALTH_GENERATION_REQUIRES_CURRENT_PRIORITY":
        '"reference_semantic_generation_requires_current_priority": True',

    "HEALTH_CACHE_HIT_NO_GENERATION_ALLOW":
        '"reference_semantic_cache_hit_requires_generation_allow": False',

    "HEALTH_NO_MECHANICAL_RECALC":
        '"reference_semantic_recalculates_mechanical": False',

    "HEALTH_NO_FEATURE_WRITE":
        '"reference_semantic_writes_feature_observation": False',

    "HEALTH_NO_LOCAL_PATH":
        '"reference_semantic_local_path_persisted": False',

    "HEALTH_LEGACY_WRITE_DISABLED":
        '"reference_video_analysis_legacy_write_disabled": True',
}


for name,marker in health_markers.items():

    add(
        name,
        marker
        in health_src,
    )


# ============================================================
# RESULT
# ============================================================

failed = [
    row
    for row in checks
    if not row[
        "pass"
    ]
]


report = {
    "phase":
        "09C7-B2D",

    "worker_version":
        "2.24.0",

    "source_sha256":
        source_sha,

    "freeze_sha256":
        freeze_sha,

    "check_count":
        len(
            checks
        ),

    "pass_count":
        len(
            checks
        )
        - len(
            failed
        ),

    "fail_count":
        len(
            failed
        ),

    "failed_checks":[
        row[
            "check"
        ]
        for row in failed
    ],

    "identity_fields":
        engine_identity,

    "provider_callers":
        callers_of(
            provider_name
        ),

    "legacy_vision_callers":
        callers_of(
            "_reference_video_vision"
        ),

    "storage_dir_args":
        function_args(
            "_reference_semantic_analysis_dir"
        ),

    "storage_path_args":
        function_args(
            "_reference_semantic_analysis_path"
        ),

    "runtime_deployed":
        False,

    "build_executed":
        False,

    "api_called":
        False,

    "model_called":
        False,

    "checks":
        checks,

    "all_passed":
        not failed,
}


REPORT.parent.mkdir(
    parents=True,
    exist_ok=True,
)


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "=== SM3 09C7-B2D STATIC CHECKS ==="
)


for row in checks:

    print(
        (
            row["check"]
            + "="
            + str(
                row["pass"]
            )
            + (
                (
                    " | "
                    + row["detail"]
                )
                if row["detail"]
                else ""
            )
        )
    )


print()

print(
    "CHECK_COUNT="
    + str(
        len(
            checks
        )
    )
)

print(
    "PASS_COUNT="
    + str(
        len(
            checks
        )
        - len(
            failed
        )
    )
)

print(
    "FAIL_COUNT="
    + str(
        len(
            failed
        )
    )
)

print(
    "FAILED_CHECKS="
    + ",".join(
        row[
            "check"
        ]
        for row in failed
    )
)

print(
    "IDENTITY_FIELDS="
    + ",".join(
        engine_identity
        or []
    )
)

print(
    "PROVIDER_CALLERS="
    + ",".join(
        callers_of(
            provider_name
        )
    )
)

print(
    "LEGACY_VISION_CALLERS="
    + ",".join(
        callers_of(
            "_reference_video_vision"
        )
    )
)

print(
    "BUILD_EXECUTED=False"
)

print(
    "RUNTIME_DEPLOYED=False"
)

print(
    "API_CALLED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "REPORT="
    + str(
        REPORT
    )
)


if failed:

    print(
        "SM3_09C7_B2D_MEDIA_CENTRIC_STATIC_GATE_FAIL"
    )

    sys.exit(1)


print(
    "SM3_09C7_B2D_MEDIA_CENTRIC_STATIC_GATE_PASS"
)

sys.exit(0)
