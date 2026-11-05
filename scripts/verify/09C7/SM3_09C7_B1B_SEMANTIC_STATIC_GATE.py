from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import json
import re
import sys


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = ROOT / "worker" / "worker_service.py"

FREEZE = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_A2_SEMANTIC_CONTRACT_FREEZE.json"
)

B1A = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B1A_STRUCTURAL_IMPLEMENTATION.json"
)

REPORT = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B1B_SEMANTIC_STATIC_GATE.json"
)


EXPECTED_SHA = (
    "9124c4241ada437639de165ff725c92d"
    "73ea46ed0c71969f86a7b41a4076c3c9"
)


raw = WORKER.read_bytes()

sha = hashlib.sha256(raw).hexdigest()

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
        "SM3_09C7_B1B_WORKER_SYNTAX_ERROR:"
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
        functions[node.name] = node

    elif isinstance(
        node,
        ast.ClassDef,
    ):
        classes[node.name] = node

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


def source_of(node):

    if node is None:
        return ""

    return "\n".join(
        lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


def literal_assignment(name):

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


def class_fields(name):

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
    function_name,
    variable_name,
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

        for target in node.targets:

            if (
                isinstance(
                    target,
                    ast.Name,
                )
                and
                target.id == variable_name
            ):

                keys = []

                for key in node.value.keys:

                    if isinstance(
                        key,
                        ast.Constant,
                    ):
                        keys.append(
                            key.value
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


def call_name(call):

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
            reversed(parts)
        )

    return ""


def function_calls(name):

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


def callers_of(target):

    result = []

    for name,fn in functions.items():

        for node in ast.walk(
            fn
        ):

            if not isinstance(
                node,
                ast.Call,
            ):
                continue

            if (
                call_name(node)
                == target
            ):
                result.append(
                    name
                )

    return sorted(
        result
    )


def routes():

    result = []

    for name,fn in functions.items():

        for decorator in fn.decorator_list:

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

            result.append({
                "method":
                    method.split(".")[-1].upper(),

                "path":
                    str(arg.value),

                "function":
                    name,
            })

    return result


checks = []


def add(
    name,
    value,
    detail="",
):

    checks.append({
        "check":
            name,

        "pass":
            bool(value),

        "detail":
            str(detail),
    })


# ============================================================
# 1. SOURCE / PREVIOUS GATES
# ============================================================

add(
    "SOURCE_SHA_EXPECTED",
    sha == EXPECTED_SHA,
    sha,
)


add(
    "WORKER_VERSION_2_24_0",
    text.count(
        'WORKER_VERSION = "2.24.0"'
    ) == 1,
)


freeze = json.loads(
    FREEZE.read_text(
        encoding="utf-8-sig"
    )
)


b1a = json.loads(
    B1A.read_text(
        encoding="utf-8-sig"
    )
)


add(
    "A2_FREEZE_STATUS_FROZEN",
    freeze["freeze"]["status"]
    == "FROZEN",
)


add(
    "A2_CONTRACT_MATCH",
    freeze["freeze"]["contracts"][
        "semantic_analysis_contract"
    ]
    == "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1",
)


add(
    "B1A_STATUS_VALID",
    b1a["status"]
    == "HOST_STRUCTURAL_IMPLEMENTATION_WRITTEN",
)


add(
    "B1A_SOURCE_SHA_MATCH",
    b1a["source_sha_after"]
    == sha,
)


add(
    "B1A_48_OF_48",
    (
        b1a["candidate_check_count"] == 48
        and
        b1a["candidate_pass_count"] == 48
        and
        b1a["candidate_fail_count"] == 0
    ),
)


add(
    "B1A_NO_MODEL_CALL",
    b1a["model_called"] is False,
)


add(
    "B1A_NO_RSA_CREATED",
    b1a["semantic_record_created"] is False,
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
# 3. STORAGE
# ============================================================

add(
    "SEMANTIC_STORAGE_ROOT_DEFINED_ONCE",
    text.count(
        "PRODUCTION_REFERENCE_SEMANTIC_ANALYSES ="
    ) == 1,
)


add(
    "SEMANTIC_STORAGE_ROOT_NAME",
    '"reference_semantic_analyses"'
    in text,
)


startup_match = re.search(
    r"^for p in \((.*?)\):$",
    text,
    re.M,
)


startup_text = (
    startup_match.group(1)
    if startup_match
    else ""
)


add(
    "STARTUP_LOOP_FOUND",
    startup_match is not None,
)


add(
    "SEMANTIC_STORAGE_IN_STARTUP",
    "PRODUCTION_REFERENCE_SEMANTIC_ANALYSES"
    in startup_text,
)


# ============================================================
# 4. REQUEST CONTRACT
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
    "REQUEST_MODEL_PRESENT",
    "ReferenceSemanticAnalysisRequest"
    in classes,
)


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
# 5. ROUTES
# ============================================================

all_routes = routes()


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


route_tuples = {
    (
        row["method"],
        row["path"],
        row["function"],
    )
    for row in all_routes
}


for method,path,function in sorted(
    expected_routes
):

    add(
        (
            "ROUTE_"
            + method
            + "_"
            + function.upper()
        ),
        (
            method,
            path,
            function,
        )
        in route_tuples,
        path,
    )


# ============================================================
# 6. ENGINE / PROVIDER BOUNDARY
# ============================================================

semantic_name = (
    "production_reference_semantic_analysis"
)

provider_name = (
    "_reference_semantic_provider_analyze"
)

semantic_src = source_of(
    functions.get(
        semantic_name
    )
)

provider_src = source_of(
    functions.get(
        provider_name
    )
)


add(
    "SEMANTIC_ENGINE_PRESENT",
    semantic_name
    in functions,
)


add(
    "SEMANTIC_PROVIDER_PRESENT",
    provider_name
    in functions,
)


add(
    "PROVIDER_CALLER_EXACTLY_SEMANTIC_ENGINE",
    callers_of(
        provider_name
    )
    == [
        semantic_name
    ],
    callers_of(
        provider_name
    ),
)


add(
    "SEMANTIC_ENGINE_NO_DIRECT_HTTP",
    "httpx.Client"
    not in semantic_src,
)


add(
    "PROVIDER_OWNS_HTTP",
    "httpx.Client"
    in provider_src,
)


add(
    "PROVIDER_USES_STRICT_SCHEMA",
    (
        '"type":"json_schema"'
        in provider_src
        and
        '"strict":True'
        in provider_src
    ),
)


add(
    "PROVIDER_USES_CANONICAL_CONTACT_SHEET",
    "_image_data_url"
    in provider_src,
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


# ============================================================
# 7. NO MECHANICAL RECOMPUTATION / FEATURE MEMORY
# ============================================================

for forbidden_call in (
    "make_contact_sheet",
    "_reference_cut_metrics",
    "_reference_audio_onsets",
    "_reference_color_stats",
):

    add(
        (
            "SEMANTIC_DOES_NOT_CALL_"
            + forbidden_call.upper()
        ),
        forbidden_call
        not in function_calls(
            semantic_name
        ),
    )


add(
    "SEMANTIC_DOES_NOT_WRITE_FEATURE",
    (
        "production_reference_feature"
        not in function_calls(
            semantic_name
        )
        and
        "ReferenceFeatureObservationRequest"
        not in semantic_src
    ),
)


add(
    "SEMANTIC_DOES_NOT_READ_PREFERENCE_SIGNAL",
    "preference_signal"
    not in semantic_src,
)


add(
    "SEMANTIC_DOES_NOT_READ_REQUEST_NOTES",
    "req.notes"
    not in semantic_src,
)


add(
    "SEMANTIC_REQUEST_HAS_NO_LOCAL_PATH",
    "local_media_ref"
    not in semantic_src,
)


# ============================================================
# 8. CANONICAL SOURCE CHAIN
# ============================================================

semantic_calls = function_calls(
    semantic_name
)


for required_call in (
    "_require_reference_item_active",
    "_reference_semantic_load_acquisition",
    "_resolve_reference_acquisition_source",
    "sha256_file",
    "_reference_semantic_load_mechanical",
    "_reference_semantic_authorizing_priority",
    "_reference_semantic_contact_sheet",
    "_reference_semantic_provider_analyze",
    "_write_revision_once",
    "_verify_reference_semantic_analysis",
):

    add(
        (
            "SEMANTIC_CALLS_"
            + required_call.upper()
        ),
        required_call
        in semantic_calls,
    )


add(
    "SEMANTIC_REQUIRES_MEDIA_ARTIFACT",
    "REFERENCE_SEMANTIC_MEDIA_ARTIFACT_REQUIRED"
    in semantic_src,
)


add(
    "SEMANTIC_VERIFIES_SOURCE_SHA",
    (
        "REFERENCE_SEMANTIC_SOURCE_SHA_MISMATCH"
        in semantic_src
        and
        "sha256_file"
        in semantic_src
    ),
)


add(
    "SEMANTIC_VERIFIES_MEDIA_ARTIFACT_LINK",
    "REFERENCE_SEMANTIC_MEDIA_ARTIFACT_MISMATCH"
    in semantic_src,
)


# ============================================================
# 9. ACQUISITION / RMA / CONTACT VERIFIERS
# ============================================================

acq_src = source_of(
    functions.get(
        "_reference_semantic_load_acquisition"
    )
)


mechanical_src = source_of(
    functions.get(
        "_reference_semantic_load_mechanical"
    )
)


contact_src = source_of(
    functions.get(
        "_reference_semantic_contact_sheet"
    )
)


add(
    "ACQUISITION_EXPLICIT_ID_REQUIRED",
    "REFERENCE_SEMANTIC_ACQUISITION_ID_REQUIRED"
    in acq_src,
)


add(
    "ACQUISITION_ITEM_MATCH_REQUIRED",
    "REFERENCE_SEMANTIC_ACQUISITION_ITEM_MISMATCH"
    in acq_src,
)


add(
    "MECHANICAL_EXPLICIT_ID_REQUIRED",
    "REFERENCE_SEMANTIC_MECHANICAL_ANALYSIS_ID_REQUIRED"
    in mechanical_src,
)


add(
    "MECHANICAL_ID_MATCH_REQUIRED",
    "REFERENCE_SEMANTIC_MECHANICAL_ID_MISMATCH"
    in mechanical_src,
)


add(
    "MECHANICAL_SOURCE_MATCH_REQUIRED",
    "REFERENCE_SEMANTIC_MECHANICAL_SOURCE_MISMATCH"
    in mechanical_src,
)


add(
    "CONTACT_SHEET_REQUIRED",
    "REFERENCE_SEMANTIC_CONTACT_SHEET_REQUIRED"
    in contact_src,
)


add(
    "CONTACT_SHEET_HASH_REQUIRED",
    (
        "REFERENCE_SEMANTIC_CONTACT_SHEET_HASH_INVALID"
        in contact_src
        and
        "REFERENCE_SEMANTIC_CONTACT_SHEET_HASH_MISMATCH"
        in contact_src
    ),
)


add(
    "CONTACT_SHEET_NOT_REGENERATED",
    "make_contact_sheet"
    not in contact_src,
)


# ============================================================
# 10. PRIORITY AUTHORIZATION
# ============================================================

priority_src = source_of(
    functions.get(
        "_reference_semantic_authorizing_priority"
    )
)


add(
    "PRIORITY_EXPLICIT_ID_REQUIRED",
    "REFERENCE_SEMANTIC_PRIORITY_DECISION_ID_REQUIRED"
    in priority_src,
)


add(
    "PRIORITY_RECORD_VERIFIED",
    "_verify_reference_priority_decision"
    in priority_src,
)


add(
    "PRIORITY_SOURCE_MATCH",
    "REFERENCE_SEMANTIC_PRIORITY_SOURCE_MISMATCH"
    in priority_src,
)


add(
    "PRIORITY_MECHANICAL_MATCH",
    "REFERENCE_SEMANTIC_PRIORITY_MECHANICAL_MISMATCH"
    in priority_src,
)


add(
    "PRIORITY_RECOMPUTES_CURRENT_EVIDENCE",
    "_reference_priority_current_evidence"
    in priority_src,
)


add(
    "PRIORITY_EVIDENCE_STALE_FAIL_CLOSED",
    "REFERENCE_PRIORITY_DECISION_STALE"
    in priority_src,
)


add(
    "PRIORITY_ENGINE_VERSION_CURRENT",
    (
        'rec.get(\n                "engine_version"'
        in priority_src
        or
        'rec.get("engine_version")'
        in priority_src
        or
        '"engine_version"'
        in priority_src
    )
    and
    "REFERENCE_PRIORITY_ENGINE_VERSION"
    in priority_src,
)


add(
    "REQUESTED_PRIORITY_MUST_BE_CURRENT",
    "REFERENCE_SEMANTIC_PRIORITY_DECISION_NOT_CURRENT"
    in priority_src,
)


add(
    "SEMANTIC_ALLOW_REQUIRED",
    "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:"
    in priority_src,
)


# ============================================================
# 11. RSA IDENTITY
# ============================================================

identity_keys = assigned_dict_keys(
    semantic_name,
    "identity",
)


expected_identity_keys = [
    "reference_item_id",
    "source_sha256",
    "mechanical_analysis_id",
    "mechanical_analysis_sha256",
    "semantic_analyzer_version",
    "semantic_schema_version",
    "semantic_prompt_version",
    "vision_provider",
    "vision_model",
]


add(
    "RSA_IDENTITY_DICT_FOUND",
    identity_keys is not None,
)


add(
    "RSA_IDENTITY_FIELDS_EXACT",
    identity_keys
    == expected_identity_keys,
    identity_keys,
)


add(
    "RSA_PREFIX_USED",
    '"RSA_"'
    in semantic_src,
)


for excluded in (
    "acquisition_id",
    "priority_decision_id",
    "local_media_ref",
    "source_resolved_path",
    "preference_signal",
    "notes",
    "created_at",
    "provider_response_id",
):

    add(
        (
            "RSA_IDENTITY_EXCLUDES_"
            + excluded.upper()
        ),
        (
            identity_keys is not None
            and
            excluded
            not in identity_keys
        ),
    )


# ============================================================
# 12. OUTPUT RECORD
# ============================================================

record_keys = assigned_dict_keys(
    semantic_name,
    "rec",
)


required_record_keys = {
    "semantic_analysis_id",
    "contract_version",
    "analyzer_version",
    "semantic_schema_version",
    "semantic_prompt_version",
    "reference_item_id",
    "reference_profile_id",
    "acquisition_id",
    "media_artifact_id",
    "source_sha256",
    "mechanical_analysis_id",
    "mechanical_analysis_sha256",
    "priority_decision_id",
    "priority_evidence_fingerprint",
    "vision_provider",
    "vision_model",
    "vision_response_id",
    "semantic_confidence",
    "semantic",
    "created_at",
    "copying_forbidden",
    "foundation_override_allowed",
}


add(
    "RSA_RECORD_DICT_FOUND",
    record_keys is not None,
)


add(
    "RSA_REQUIRED_PROVENANCE_PRESENT",
    (
        record_keys is not None
        and
        required_record_keys.issubset(
            set(record_keys)
        )
    ),
    (
        sorted(
            set(record_keys or [])
            - required_record_keys
        )
    ),
)


add(
    "RSA_PROVIDER_CONTRACT_PERSISTED",
    (
        record_keys is not None
        and
        "provider_contract_version"
        in record_keys
    ),
)


for forbidden in (
    "local_media_ref",
    "source_resolved_path",
    "contact_sheet_path",
    "preference_signal",
):

    add(
        (
            "RSA_RECORD_FORBIDS_"
            + forbidden.upper()
        ),
        (
            record_keys is not None
            and
            forbidden
            not in record_keys
        ),
    )


add(
    "RSA_RECORD_HASH_COMPUTED",
    (
        'rec[\n        "semantic_analysis_sha256"\n    ]=_canonical_sha256('
        in semantic_src
        or
        "semantic_analysis_sha256"
        in semantic_src
    ),
)


add(
    "RSA_WRITE_ONCE",
    "_write_revision_once"
    in semantic_calls,
)


# ============================================================
# 13. PERSISTED RECORD VERIFIER
# ============================================================

verify_src = source_of(
    functions.get(
        "_verify_reference_semantic_analysis"
    )
)


add(
    "RSA_VERIFIER_PRESENT",
    "_verify_reference_semantic_analysis"
    in functions,
)


add(
    "RSA_VERIFIER_CHECKS_CONTRACT",
    "REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION"
    in verify_src,
)


add(
    "RSA_VERIFIER_CHECKS_ANALYZER",
    "REFERENCE_SEMANTIC_ANALYZER_VERSION"
    in verify_src,
)


add(
    "RSA_VERIFIER_CHECKS_SCHEMA_VERSION",
    "REFERENCE_SEMANTIC_SCHEMA_VERSION"
    in verify_src,
)


add(
    "RSA_VERIFIER_CHECKS_PROMPT_VERSION",
    "REFERENCE_SEMANTIC_PROMPT_VERSION"
    in verify_src,
)


add(
    "RSA_VERIFIER_CHECKS_RECORD_HASH",
    (
        "semantic_analysis_sha256"
        in verify_src
        and
        "_canonical_sha256"
        in verify_src
    ),
)


add(
    "RSA_VERIFIER_CHECKS_COPY_POLICY",
    "REFERENCE_SEMANTIC_COPYING_POLICY_INVALID"
    in verify_src,
)


add(
    "RSA_VERIFIER_CHECKS_FOUNDATION_POLICY",
    "REFERENCE_SEMANTIC_FOUNDATION_POLICY_INVALID"
    in verify_src,
)


# Strong deterministic-record requirements.
# These deliberately go beyond the patcher's first-pass checks.

identity_markers = (
    "semantic_analysis_id",
    "reference_item_id",
    "source_sha256",
    "mechanical_analysis_id",
    "mechanical_analysis_sha256",
    "semantic_schema_version",
    "semantic_prompt_version",
    "vision_provider",
    "vision_model",
)


add(
    "RSA_VERIFIER_REBUILDS_DETERMINISTIC_IDENTITY",
    (
        all(
            marker
            in verify_src
            for marker
            in identity_markers
        )
        and
        '"RSA_"'
        in verify_src
        and
        "_canonical_sha256"
        in verify_src
    ),
)


add(
    "RSA_VERIFIER_CHECKS_PROVIDER_CONTRACT",
    (
        "provider_contract_version"
        in verify_src
        and
        "REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION"
        in verify_src
    ),
)


add(
    "RSA_VERIFIER_VALIDATES_SEMANTIC_PAYLOAD",
    (
        "semantic"
        in verify_src
        and
        "REFERENCE_SEMANTIC_SCHEMA"
        in verify_src
    ),
)


# ============================================================
# 14. SEMANTIC SCHEMA BOUNDARY
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


schema_properties = (
    set(
        schema.get(
            "properties",
            {},
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
            [],
        )
    )
    if isinstance(
        schema,
        dict,
    )
    else set()
)


add(
    "SEMANTIC_SCHEMA_LITERAL_FOUND",
    isinstance(
        schema,
        dict,
    ),
)


add(
    "SEMANTIC_SCHEMA_FIELDS_EXACT",
    schema_properties
    == expected_semantic_fields,
    sorted(
        schema_properties
    ),
)


add(
    "SEMANTIC_SCHEMA_REQUIRED_EXACT",
    schema_required
    == expected_semantic_fields,
)


add(
    "SEMANTIC_SCHEMA_NO_ADDITIONAL_PROPERTIES",
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
        (
            "SEMANTIC_SCHEMA_FORBIDS_"
            + objective.upper()
        ),
        objective
        not in schema_properties,
    )


# ============================================================
# 15. LEGACY VIDEO WRITE MUST BE DEAD
# ============================================================

legacy_name = (
    "production_reference_video_analysis"
)

legacy_src = source_of(
    functions.get(
        legacy_name
    )
)


add(
    "LEGACY_VIDEO_ENDPOINT_PRESENT",
    legacy_name
    in functions,
)


add(
    "LEGACY_VIDEO_WRITE_DISABLED",
    "REFERENCE_VIDEO_ANALYSIS_LEGACY_WRITE_DISABLED_USE_SEMANTIC_ANALYSIS"
    in legacy_src,
)


add(
    "LEGACY_VIDEO_DOES_NOT_CALL_VISION",
    "_reference_video_vision"
    not in function_calls(
        legacy_name
    ),
)


add(
    "LEGACY_VIDEO_DOES_NOT_RECOMPUTE_MECHANICAL",
    all(
        name
        not in function_calls(
            legacy_name
        )
        for name in (
            "make_contact_sheet",
            "_reference_cut_metrics",
            "_reference_audio_onsets",
            "_reference_color_stats",
        )
    ),
)


add(
    "LEGACY_VIDEO_DOES_NOT_WRITE_FEATURE",
    "production_reference_feature"
    not in function_calls(
        legacy_name
    ),
)


add(
    "LEGACY_VISION_HELPER_HAS_ZERO_CALLERS",
    callers_of(
        "_reference_video_vision"
    ) == [],
    callers_of(
        "_reference_video_vision"
    ),
)


add(
    "LEGACY_VIDEO_HISTORICAL_GET_PRESERVED",
    "production_reference_video_analysis_latest"
    in functions,
)


# ============================================================
# 16. SEMANTIC READERS
# ============================================================

add(
    "SEMANTIC_LIST_READER_PRESENT",
    "production_reference_semantic_analyses"
    in functions,
)


add(
    "SEMANTIC_LATEST_READER_PRESENT",
    "production_reference_semantic_analysis_latest"
    in functions,
)


list_src = source_of(
    functions.get(
        "production_reference_semantic_analyses"
    )
)


latest_src = source_of(
    functions.get(
        "production_reference_semantic_analysis_latest"
    )
)


add(
    "SEMANTIC_LIST_VERIFIES_RECORDS",
    "_verify_reference_semantic_analysis"
    in list_src,
)


add(
    "SEMANTIC_LATEST_USES_VERIFIED_LIST",
    "production_reference_semantic_analyses"
    in latest_src,
)


# ============================================================
# 17. HEALTH CAPABILITIES
# ============================================================

health_src = source_of(
    functions.get(
        "health"
    )
)


health_markers = {
    "HEALTH_SEMANTIC_ENABLED":
        '"reference_semantic_analysis": True',

    "HEALTH_EXPLICIT_IDS":
        '"reference_semantic_requires_explicit_ids": True',

    "HEALTH_CURRENT_PRIORITY":
        '"reference_semantic_requires_current_priority": True',

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
    if not row["pass"]
]


report = {
    "phase":
        "09C7-B1B",

    "worker_sha256":
        sha,

    "worker_version":
        "2.24.0",

    "check_count":
        len(checks),

    "pass_count":
        len(checks)
        - len(failed),

    "fail_count":
        len(failed),

    "failed_checks":[
        row["check"]
        for row in failed
    ],

    "provider_callers":
        callers_of(
            provider_name
        ),

    "legacy_vision_callers":
        callers_of(
            "_reference_video_vision"
        ),

    "request_fields":
        request_fields,

    "identity_fields":
        identity_keys,

    "record_fields":
        record_keys,

    "checks":
        checks,

    "all_passed":
        not failed,

    "runtime_deployed":
        False,

    "model_called":
        False,
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
    "=== SM3 09C7-B1B STATIC CHECKS ==="
)


for row in checks:

    print(
        (
            f"{row['check']}="
            f"{row['pass']}"
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
        len(checks)
    )
)

print(
    "PASS_COUNT="
    + str(
        len(checks)
        - len(failed)
    )
)

print(
    "FAIL_COUNT="
    + str(
        len(failed)
    )
)

print(
    "FAILED_CHECKS="
    + ",".join(
        row["check"]
        for row in failed
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
    "MODEL_CALLED=False"
)

print(
    "RUNTIME_DEPLOYED=False"
)

print(
    "REPORT="
    + str(
        REPORT
    )
)


if failed:

    print(
        "SM3_09C7_B1B_SEMANTIC_STATIC_GATE_FAIL"
    )

    sys.exit(1)


print(
    "SM3_09C7_B1B_SEMANTIC_STATIC_GATE_PASS"
)

sys.exit(0)
