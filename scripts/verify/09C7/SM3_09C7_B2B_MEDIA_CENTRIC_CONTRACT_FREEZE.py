from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import json
import re
import subprocess
import sys


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = (
    ROOT
    / "worker"
    / "worker_service.py"
)

REPORT = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B2B_MEDIA_CENTRIC_CONTRACT_FREEZE.json"
)

CONTAINER = "deployment-media-worker-1"

EXPECTED_HOST_SHA = (
    "8ca08d498d41cb732341c368d8aaa03e"
    "252a4c6eeef81a430201199a2e05f882"
)

EXPECTED_RUNTIME_SHA = (
    "3af5412234de7a7faa0e8b23116027b7"
    "cad25fe308698ca9188649ca3b1df8ba"
)

A2_REPORT_SHA = (
    "aceb5921e7f3629b8454ce09d4b9d3b"
    "2171e2aa8f9c2c5c2bf2c27c4f6c15c8e"
)

RMA_ID = (
    "RMA_0072a9689863b956298a9ec34f01bd0e"
)


def docker(*args: str) -> str:

    result = subprocess.run(
        [
            "docker",
            *args,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:

        raise SystemExit(
            "SM3_09C7_B2B_DOCKER_FAILED:"
            + " ".join(args)
            + ":"
            + result.stderr.strip()
        )

    return result.stdout.strip()


# ============================================================
# 1. CURRENT SOURCE EVIDENCE
# ============================================================

raw = WORKER.read_bytes()

host_sha = hashlib.sha256(
    raw
).hexdigest()


runtime_line = docker(
    "exec",
    CONTAINER,
    "sha256sum",
    "/app/worker_service.py",
)


runtime_sha = (
    runtime_line.split()[0]
    .strip()
    .lower()
)


semantic_count = int(
    docker(
        "exec",
        CONTAINER,
        "sh",
        "-lc",
        (
            "find "
            "/data/media/production_state/"
            "reference_semantic_analyses "
            "-type f -name 'RSA_*.json' "
            "2>/dev/null | wc -l"
        ),
    )
)


text = WORKER.read_text(
    encoding="utf-8-sig"
)


tree = ast.parse(
    text,
    filename=str(WORKER),
)


functions = {
    node.name:node
    for node in tree.body
    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    )
}


lines = text.splitlines()


def source_of(name: str) -> str:

    node=functions.get(name)

    if node is None:
        return ""

    return "\n".join(
        lines[
            node.lineno-1:
            node.end_lineno
        ]
    )


semantic_node = functions.get(
    "production_reference_semantic_analysis"
)


current_identity=[]


if semantic_node is not None:

    for node in ast.walk(
        semantic_node
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
            target.id=="identity"
            for target in node.targets
        ):
            continue

        current_identity=[
            str(key.value)
            for key in node.value.keys
            if isinstance(
                key,
                ast.Constant,
            )
        ]


provider_src=source_of(
    "_reference_semantic_provider_analyze"
)


current_provider_item_dependencies=[
    field
    for field in (
        "network",
        "item_type",
        "caption",
    )
    if (
        f'item.get("{field}")'
        in provider_src
        or
        f"item.get('{field}')"
        in provider_src
    )
]


semantic_dir_node=functions.get(
    "_reference_semantic_analysis_dir"
)


semantic_dir_args=[]


if semantic_dir_node is not None:

    semantic_dir_args=[
        arg.arg
        for arg in semantic_dir_node.args.args
    ]


# ============================================================
# 2. CANONICAL RMA EVIDENCE
# ============================================================

rma_paths=docker(
    "exec",
    CONTAINER,
    "sh",
    "-lc",
    (
        "grep -RIl '"
        + RMA_ID
        + "' "
        "/data/media/production_state/"
        "reference_mechanical_analyses "
        "2>/dev/null"
    ),
).splitlines()


rma_paths=[
    row.strip()
    for row in rma_paths
    if row.strip()
]


if len(rma_paths)!=1:

    raise SystemExit(
        "SM3_09C7_B2B_RMA_PATH_COUNT_INVALID:"
        + str(len(rma_paths))
    )


rma=json.loads(
    docker(
        "exec",
        CONTAINER,
        "cat",
        rma_paths[0],
    )
)


contact_sha=str(
    rma.get(
        "contact_sheet_sha256"
    )
    or ""
).lower()


mechanical_sha=str(
    rma.get(
        "mechanical_analysis_sha256"
    )
    or ""
).lower()


source_sha=str(
    rma.get(
        "source_sha256"
    )
    or ""
).lower()


# ============================================================
# 3. CORRECTED V1 FREEZE
# ============================================================

request_ids=[
    "reference_item_id",
    "acquisition_id",
    "mechanical_analysis_id",
    "priority_decision_id",
]


identity_fields=[
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


identity_excluded=[
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
]


creation_provenance=[
    "creation_reference_item_id",
    "creation_reference_profile_id",
    "creation_acquisition_id",
    "creation_priority_decision_id",
    "creation_priority_evidence_fingerprint",
]


freeze={
    "status":
        "FROZEN_MEDIA_CENTRIC_V1",

    "contract_version":
        "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1",

    "contract_version_changed":
        False,

    "reason_contract_version_unchanged":
        (
            "No semantic RSA has been persisted or deployed; "
            "this amendment corrects V1 before activation."
        ),

    "supersedes":{
        "phase":
            "09C7-A2",

        "report":
            "SM3_09C7_A2_SEMANTIC_CONTRACT_FREEZE.json",

        "report_sha256":
            A2_REPORT_SHA,

        "scope":[
            "semantic input boundary",
            "RSA identity",
            "semantic storage scope",
            "cache authorization semantics",
            "creation provenance naming",
        ],
    },

    "request":{
        "required_ids":
            request_ids,

        "ids_are_authorization_context":
            True,

        "ids_define_semantic_identity":
            False,

        "implicit_latest_allowed":
            False,

        "local_media_ref_allowed":
            False,

        "preference_signal_allowed":
            False,

        "notes_allowed":
            False,
    },

    "semantic_input":{
        "canonical_contact_sheet":
            True,

        "canonical_mechanical_payload":
            True,

        "reference_item_context_allowed":
            False,

        "network_allowed":
            False,

        "item_type_allowed":
            False,

        "caption_allowed":
            False,

        "profile_context_allowed":
            False,

        "metric_context_allowed":
            False,

        "preference_context_allowed":
            False,

        "notes_context_allowed":
            False,

        "person_identification_allowed":
            False,
    },

    "identity":{
        "media_centric":
            True,

        "fields":
            identity_fields,

        "excluded":
            identity_excluded,

        "contact_sheet_sha256_explicit":
            True,

        "relies_on_transitive_rma_contact_commitment":
            False,

        "reference_item_id_participates":
            False,

        "acquisition_id_participates":
            False,

        "priority_decision_id_participates":
            False,
    },

    "storage":{
        "root":
            "reference_semantic_analyses",

        "media_centric":
            True,

        "layout":
            "<source_sha256[:2]>/<source_sha256>/RSA_<identity>.json",

        "profile_scoped":
            False,

        "item_scoped":
            False,

        "immutable":
            True,

        "write_once":
            True,
    },

    "creation_provenance":{
        "fields":
            creation_provenance,

        "participates_in_identity":
            False,

        "immutable":
            True,

        "meaning":
            "Context that authorized the first provider generation only.",
    },

    "cache_policy":{
        "existing_RSA_reused":
            True,

        "cache_hit_calls_provider":
            False,

        "cache_hit_requires_active_item":
            True,

        "cache_hit_requires_acquisition_source_match":
            True,

        "cache_hit_requires_mechanical_match":
            True,

        "cache_hit_requires_priority_generation_allow":
            False,

        "cache_miss_requires_current_priority":
            True,

        "cache_miss_requires_semantic_analysis_allowed":
            True,

        "priority_controls_expensive_generation":
            True,

        "priority_controls_historical_read":
            False,

        "same_identity_provider_recall_allowed":
            False,

        "reanalyze_requires_version_or_model_change":
            True,
    },

    "provider":{
        "boundary":
            "SM3_REFERENCE_SEMANTIC_PROVIDER_V1",

        "item_argument_allowed":
            False,

        "item_context_in_prompt":
            False,

        "direct_HTTP_from_semantic_engine":
            False,

        "descriptive_only":
            True,

        "copying_forbidden":
            True,

        "foundation_override_allowed":
            False,
    },

    "mechanical":{
        "recalculate":
            False,

        "regenerate_contact_sheet":
            False,

        "contact_sheet_hash_verified":
            True,

        "contact_sheet_hash_in_identity":
            True,
    },

    "feature_memory":{
        "semantic_writes_feature_observation":
            False,

        "semantic_writes_preference":
            False,

        "deferred_to":
            "09C8",
    },

    "legacy":{
        "new_video_analysis_generation_allowed":
            False,

        "historical_get_preserved":
            True,
    },

    "readers":{
        "item_reader_is_contextual_view":
            True,

        "item_reader_resolves_item_source_shas":
            True,

        "RSA_ownership_bound_to_creation_item":
            False,

        "historical_RSA_read_requires_active_item":
            False,
    },
}


# ============================================================
# 4. FREEZE ASSERTIONS
# ============================================================

checks=[]


def add(
    name: str,
    value: bool,
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


add(
    "HOST_SHA_EXPECTED",
    host_sha==EXPECTED_HOST_SHA,
    host_sha,
)


add(
    "RUNTIME_SHA_EXPECTED",
    runtime_sha==EXPECTED_RUNTIME_SHA,
    runtime_sha,
)


add(
    "NO_EXISTING_RSA",
    semantic_count==0,
    semantic_count,
)


add(
    "CURRENT_WORKER_VERSION_2_24_0",
    text.count(
        'WORKER_VERSION = "2.24.0"'
    )==1,
)


add(
    "PRE_AMENDMENT_IDENTITY_CONFIRMED",
    current_identity==[
        "reference_item_id",
        "source_sha256",
        "mechanical_analysis_id",
        "mechanical_analysis_sha256",
        "semantic_analyzer_version",
        "semantic_schema_version",
        "semantic_prompt_version",
        "vision_provider",
        "vision_model",
    ],
    current_identity,
)


add(
    "PRE_AMENDMENT_MUTABLE_ITEM_INPUT_CONFIRMED",
    current_provider_item_dependencies==[
        "network",
        "item_type",
        "caption",
    ],
    current_provider_item_dependencies,
)


add(
    "PRE_AMENDMENT_STORAGE_ITEM_SCOPED_CONFIRMED",
    (
        "profile_id"
        in semantic_dir_args
        and
        "item_id"
        in semantic_dir_args
    ),
    semantic_dir_args,
)


add(
    "CANONICAL_RMA_SOURCE_SHA_VALID",
    bool(
        re.fullmatch(
            r"[a-f0-9]{64}",
            source_sha,
        )
    ),
    source_sha,
)


add(
    "CANONICAL_RMA_MECHANICAL_SHA_VALID",
    bool(
        re.fullmatch(
            r"[a-f0-9]{64}",
            mechanical_sha,
        )
    ),
    mechanical_sha,
)


add(
    "CANONICAL_RMA_CONTACT_SHA_VALID",
    bool(
        re.fullmatch(
            r"[a-f0-9]{64}",
            contact_sha,
        )
    ),
    contact_sha,
)


add(
    "V1_CONTRACT_VERSION_RETAINED",
    freeze[
        "contract_version"
    ]
    == "SM3_REFERENCE_SEMANTIC_ANALYSIS_V1",
)


add(
    "IDENTITY_NOW_MEDIA_CENTRIC",
    freeze[
        "identity"
    ][
        "media_centric"
    ]
    is True,
)


add(
    "IDENTITY_EXCLUDES_REFERENCE_ITEM",
    "reference_item_id"
    not in identity_fields,
)


add(
    "IDENTITY_INCLUDES_CONTACT_HASH",
    "contact_sheet_sha256"
    in identity_fields,
)


add(
    "IDENTITY_INCLUDES_PROVIDER_CONTRACT",
    "semantic_provider_contract_version"
    in identity_fields,
)


add(
    "PROVIDER_ITEM_CONTEXT_FORBIDDEN",
    (
        freeze[
            "semantic_input"
        ][
            "reference_item_context_allowed"
        ]
        is False
        and
        freeze[
            "provider"
        ][
            "item_argument_allowed"
        ]
        is False
    ),
)


add(
    "STORAGE_NOW_MEDIA_CENTRIC",
    (
        freeze[
            "storage"
        ][
            "media_centric"
        ]
        is True
        and
        freeze[
            "storage"
        ][
            "item_scoped"
        ]
        is False
    ),
)


add(
    "PRIORITY_GATES_PROVIDER_GENERATION_ONLY",
    (
        freeze[
            "cache_policy"
        ][
            "cache_hit_requires_priority_generation_allow"
        ]
        is False
        and
        freeze[
            "cache_policy"
        ][
            "cache_miss_requires_semantic_analysis_allowed"
        ]
        is True
    ),
)


add(
    "CACHE_HIT_NEVER_CALLS_PROVIDER",
    freeze[
        "cache_policy"
    ][
        "cache_hit_calls_provider"
    ]
    is False,
)


add(
    "CREATION_PROVENANCE_EXCLUDED_FROM_IDENTITY",
    all(
        field not in identity_fields
        for field in creation_provenance
    ),
)


add(
    "NO_MECHANICAL_RECALCULATION",
    freeze[
        "mechanical"
    ][
        "recalculate"
    ]
    is False,
)


add(
    "NO_FEATURE_MEMORY_WRITE",
    freeze[
        "feature_memory"
    ][
        "semantic_writes_feature_observation"
    ]
    is False,
)


add(
    "LEGACY_NEW_GENERATION_DISABLED",
    freeze[
        "legacy"
    ][
        "new_video_analysis_generation_allowed"
    ]
    is False,
)


failed=[
    row
    for row in checks
    if not row["pass"]
]


report={
    "phase":
        "09C7-B2B",

    "status":
        (
            "FROZEN_MEDIA_CENTRIC_V1"
            if not failed
            else
            "FREEZE_REJECTED"
        ),

    "host_sha256":
        host_sha,

    "runtime_sha256":
        runtime_sha,

    "semantic_count":
        semantic_count,

    "evidence":{
        "current_identity_fields":
            current_identity,

        "current_provider_item_dependencies":
            current_provider_item_dependencies,

        "current_semantic_storage_helper_args":
            semantic_dir_args,

        "canonical_rma_id":
            RMA_ID,

        "canonical_source_sha256":
            source_sha,

        "canonical_mechanical_analysis_sha256":
            mechanical_sha,

        "canonical_contact_sheet_sha256":
            contact_sha,
    },

    "freeze":
        freeze,

    "check_count":
        len(checks),

    "pass_count":
        len(checks)-len(failed),

    "fail_count":
        len(failed),

    "failed_checks":[
        row["check"]
        for row in failed
    ],

    "checks":
        checks,

    "source_modified":
        False,

    "runtime_modified":
        False,

    "api_called":
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
    "=== SM3 09C7-B2B MEDIA-CENTRIC FREEZE ==="
)


print(
    "CONTRACT="
    + freeze[
        "contract_version"
    ]
)


print(
    "CONTRACT_VERSION_CHANGED=False"
)


print(
    "IDENTITY_FIELDS="
    + ",".join(
        identity_fields
    )
)


print(
    "IDENTITY_REFERENCE_ITEM_ID=False"
)


print(
    "IDENTITY_CONTACT_SHEET_SHA256=True"
)


print(
    "PROVIDER_ITEM_CONTEXT_ALLOWED=False"
)


print(
    "STORAGE_MEDIA_CENTRIC=True"
)


print(
    "CACHE_HIT_PROVIDER_CALL=False"
)


print(
    "CACHE_HIT_PRIORITY_GENERATION_ALLOW_REQUIRED=False"
)


print(
    "CACHE_MISS_PRIORITY_GENERATION_ALLOW_REQUIRED=True"
)


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
    "SOURCE_MODIFIED=False"
)


print(
    "RUNTIME_MODIFIED=False"
)


print(
    "API_CALLED=False"
)


print(
    "MODEL_CALLED=False"
)


print(
    "REPORT="
    + str(REPORT)
)


if failed:

    print(
        "SM3_09C7_B2B_MEDIA_CENTRIC_CONTRACT_FREEZE_FAIL"
    )

    sys.exit(1)


print(
    "SM3_09C7_B2B_MEDIA_CENTRIC_CONTRACT_FREEZE_PASS"
)

sys.exit(0)
