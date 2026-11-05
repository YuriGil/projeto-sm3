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

REPORT = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B1C_RSA_VERIFIER_HARDENING.json"
)

EXPECTED_SHA = (
    "9124c4241ada437639de165ff725c92d"
    "73ea46ed0c71969f86a7b41a4076c3c9"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(code: str) -> None:
    raise SystemExit(code)


raw = WORKER.read_bytes()

before_sha = sha256_bytes(raw)


if before_sha != EXPECTED_SHA:
    fail(
        "SM3_09C7_B1C_SOURCE_SHA_INVALID:"
        + before_sha
    )


text = WORKER.read_text(
    encoding="utf-8-sig"
)


if 'WORKER_VERSION = "2.24.0"' not in text:
    fail(
        "SM3_09C7_B1C_VERSION_INVALID"
    )


# ============================================================
# 1. LOCATE EXACT FUNCTION USING AST
# ============================================================

tree = ast.parse(
    text,
    filename=str(WORKER),
)


matches = [
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
        == "_verify_reference_semantic_analysis"
    )
]


if len(matches) != 1:
    fail(
        "SM3_09C7_B1C_VERIFIER_FUNCTION_COUNT_INVALID:"
        + str(len(matches))
    )


node = matches[0]

old_function = ast.get_source_segment(
    text,
    node,
)


if not old_function:
    fail(
        "SM3_09C7_B1C_OLD_FUNCTION_SOURCE_UNAVAILABLE"
    )


# ============================================================
# 2. EXPECT THE TWO KNOWN GAPS BEFORE PATCHING
# ============================================================

old_has_provider_contract = (
    "provider_contract_version"
    in old_function
    and
    "REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION"
    in old_function
)


old_rebuilds_identity = (
    '"RSA_"'
    in old_function
    and
    "mechanical_analysis_sha256"
    in old_function
    and
    "vision_provider"
    in old_function
    and
    "vision_model"
    in old_function
)


if old_has_provider_contract:
    fail(
        "SM3_09C7_B1C_PROVIDER_CONTRACT_ALREADY_VERIFIED"
    )


if old_rebuilds_identity:
    fail(
        "SM3_09C7_B1C_IDENTITY_ALREADY_REBUILT"
    )


# ============================================================
# 3. HARDENED VERIFIER
# ============================================================

new_function = r'''
def _verify_reference_semantic_analysis(
    rec: dict[str,Any],
) -> dict[str,Any]:

    # --------------------------------------------------------
    # Contract versions
    # --------------------------------------------------------

    if (
        rec.get("contract_version")
        != REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_MISMATCH",
        )

    if (
        rec.get("analyzer_version")
        != REFERENCE_SEMANTIC_ANALYZER_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYZER_VERSION_MISMATCH",
        )

    if (
        rec.get("semantic_schema_version")
        != REFERENCE_SEMANTIC_SCHEMA_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_SCHEMA_VERSION_MISMATCH",
        )

    if (
        rec.get("semantic_prompt_version")
        != REFERENCE_SEMANTIC_PROMPT_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PROMPT_VERSION_MISMATCH",
        )

    if (
        rec.get("provider_contract_version")
        != REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PROVIDER_CONTRACT_MISMATCH",
        )

    # --------------------------------------------------------
    # Required provenance
    # --------------------------------------------------------

    reference_item_id=str(
        rec.get("reference_item_id")
        or ""
    ).strip()

    reference_profile_id=str(
        rec.get("reference_profile_id")
        or ""
    ).strip()

    acquisition_id=str(
        rec.get("acquisition_id")
        or ""
    ).strip()

    media_artifact_id=str(
        rec.get("media_artifact_id")
        or ""
    ).strip()

    mechanical_analysis_id=str(
        rec.get("mechanical_analysis_id")
        or ""
    ).strip()

    priority_decision_id=str(
        rec.get("priority_decision_id")
        or ""
    ).strip()

    vision_provider=str(
        rec.get("vision_provider")
        or ""
    ).strip()

    vision_model=str(
        rec.get("vision_model")
        or ""
    ).strip()


    required_strings={
        "reference_item_id":
            reference_item_id,

        "reference_profile_id":
            reference_profile_id,

        "acquisition_id":
            acquisition_id,

        "media_artifact_id":
            media_artifact_id,

        "mechanical_analysis_id":
            mechanical_analysis_id,

        "priority_decision_id":
            priority_decision_id,

        "vision_provider":
            vision_provider,

        "vision_model":
            vision_model,
    }


    for field,value in required_strings.items():

        if not value:
            raise HTTPException(
                409,
                (
                    "REFERENCE_SEMANTIC_PROVENANCE_REQUIRED:"
                    + field
                ),
            )


    source_sha=str(
        rec.get("source_sha256")
        or ""
    ).lower()


    if not re.fullmatch(
        r"[a-f0-9]{64}",
        source_sha,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_SOURCE_SHA_INVALID",
        )


    mechanical_sha=str(
        rec.get("mechanical_analysis_sha256")
        or ""
    ).lower()


    if not re.fullmatch(
        r"[a-f0-9]{64}",
        mechanical_sha,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_MECHANICAL_HASH_INVALID",
        )


    priority_fingerprint=str(
        rec.get("priority_evidence_fingerprint")
        or ""
    ).lower()


    if not re.fullmatch(
        r"[a-f0-9]{64}",
        priority_fingerprint,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PRIORITY_EVIDENCE_HASH_INVALID",
        )


    # --------------------------------------------------------
    # Persisted record must never leak local execution paths
    # or preference / learning state.
    # --------------------------------------------------------

    for forbidden_field in (
        "local_media_ref",
        "source_resolved_path",
        "contact_sheet_path",
        "preference_signal",
    ):

        if forbidden_field in rec:
            raise HTTPException(
                409,
                (
                    "REFERENCE_SEMANTIC_FORBIDDEN_PERSISTED_FIELD:"
                    + forbidden_field
                ),
            )


    # --------------------------------------------------------
    # Semantic payload validation against the actual V1 schema.
    #
    # This intentionally validates without an external jsonschema
    # dependency because the schema is fixed and small.
    # --------------------------------------------------------

    semantic=rec.get(
        "semantic"
    )


    if not isinstance(
        semantic,
        dict,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PAYLOAD_INVALID",
        )


    schema=REFERENCE_SEMANTIC_SCHEMA


    expected_fields=set(
        schema.get(
            "properties",
            {},
        ).keys()
    )


    required_fields=set(
        schema.get(
            "required",
            [],
        )
    )


    actual_fields=set(
        semantic.keys()
    )


    if actual_fields!=expected_fields:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PAYLOAD_FIELDS_INVALID",
        )


    if not required_fields.issubset(
        actual_fields
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PAYLOAD_REQUIRED_FIELDS_MISSING",
        )


    nullable_number_fields={
        "hook_duration_s",
        "subject_coverage",
    }


    for field in nullable_number_fields:

        value=semantic.get(
            field
        )

        if value is None:
            continue

        if (
            isinstance(
                value,
                bool,
            )
            or
            not isinstance(
                value,
                (
                    int,
                    float,
                ),
            )
        ):
            raise HTTPException(
                409,
                (
                    "REFERENCE_SEMANTIC_PAYLOAD_TYPE_INVALID:"
                    + field
                ),
            )


    string_fields=(
        expected_fields
        - nullable_number_fields
        - {
            "analysis_confidence"
        }
    )


    for field in string_fields:

        if not isinstance(
            semantic.get(
                field
            ),
            str,
        ):
            raise HTTPException(
                409,
                (
                    "REFERENCE_SEMANTIC_PAYLOAD_TYPE_INVALID:"
                    + field
                ),
            )


    payload_confidence=semantic.get(
        "analysis_confidence"
    )


    if (
        isinstance(
            payload_confidence,
            bool,
        )
        or
        not isinstance(
            payload_confidence,
            int,
        )
        or
        payload_confidence<0
        or
        payload_confidence>100
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_PAYLOAD_CONFIDENCE_INVALID",
        )


    record_confidence=rec.get(
        "semantic_confidence"
    )


    if (
        isinstance(
            record_confidence,
            bool,
        )
        or
        not isinstance(
            record_confidence,
            int,
        )
        or
        record_confidence<0
        or
        record_confidence>100
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_CONFIDENCE_INVALID",
        )


    if record_confidence!=payload_confidence:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_CONFIDENCE_MISMATCH",
        )


    # --------------------------------------------------------
    # Deterministic RSA identity.
    #
    # Acquisition and PriorityDecision remain provenance /
    # authorization only and therefore MUST NOT participate in
    # the semantic identity.
    # --------------------------------------------------------

    identity={
        "reference_item_id":
            reference_item_id,

        "source_sha256":
            source_sha,

        "mechanical_analysis_id":
            mechanical_analysis_id,

        "mechanical_analysis_sha256":
            mechanical_sha,

        "semantic_analyzer_version":
            REFERENCE_SEMANTIC_ANALYZER_VERSION,

        "semantic_schema_version":
            REFERENCE_SEMANTIC_SCHEMA_VERSION,

        "semantic_prompt_version":
            REFERENCE_SEMANTIC_PROMPT_VERSION,

        "vision_provider":
            vision_provider,

        "vision_model":
            vision_model,
    }


    expected_analysis_id=(
        "RSA_"
        + _canonical_sha256(
            identity
        )[:32]
    )


    actual_analysis_id=str(
        rec.get("semantic_analysis_id")
        or ""
    )


    if actual_analysis_id!=expected_analysis_id:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYSIS_IDENTITY_MISMATCH",
        )


    # --------------------------------------------------------
    # Safety policy
    # --------------------------------------------------------

    if rec.get("copying_forbidden") is not True:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_COPYING_POLICY_INVALID",
        )


    if rec.get("foundation_override_allowed") is not False:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_FOUNDATION_POLICY_INVALID",
        )


    # --------------------------------------------------------
    # Canonical record integrity
    # --------------------------------------------------------

    expected_hash=str(
        rec.get("semantic_analysis_sha256")
        or ""
    ).lower()


    if not re.fullmatch(
        r"[a-f0-9]{64}",
        expected_hash,
    ):
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYSIS_HASH_INVALID",
        )


    chk=dict(
        rec
    )


    chk.pop(
        "semantic_analysis_sha256",
        None,
    )


    if _canonical_sha256(chk)!=expected_hash:
        raise HTTPException(
            409,
            "REFERENCE_SEMANTIC_ANALYSIS_INTEGRITY_FAILED",
        )


    return rec
'''.lstrip()


# ============================================================
# 4. REPLACE ONLY THAT FUNCTION
# ============================================================

source_lines = text.splitlines(
    keepends=True
)

start = node.lineno - 1

end = node.end_lineno


candidate = (
    "".join(
        source_lines[:start]
    )
    + new_function.rstrip()
    + "\n\n"
    + "".join(
        source_lines[end:]
    )
)


# ============================================================
# 5. CANDIDATE MUST PARSE BEFORE WRITE
# ============================================================

try:
    candidate_tree = ast.parse(
        candidate,
        filename=str(WORKER),
    )

except SyntaxError as exc:

    fail(
        (
            "SM3_09C7_B1C_CANDIDATE_SYNTAX_ERROR:"
            + str(exc.lineno)
            + ":"
            + str(exc.offset)
            + ":"
            + str(exc.msg)
        )
    )


candidate_functions = {
    n.name:n
    for n in candidate_tree.body
    if isinstance(
        n,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    )
}


verify_node = candidate_functions.get(
    "_verify_reference_semantic_analysis"
)


if verify_node is None:
    fail(
        "SM3_09C7_B1C_VERIFIER_MISSING_AFTER_PATCH"
    )


candidate_lines = candidate.splitlines()


verify_src = "\n".join(
    candidate_lines[
        verify_node.lineno - 1:
        verify_node.end_lineno
    ]
)


# ============================================================
# 6. HARDENING GATE
# ============================================================

checks = []


def add(name: str, value: bool) -> None:

    checks.append({
        "check":name,
        "pass":bool(value),
    })


add(
    "PROVIDER_CONTRACT_VERIFIED",
    (
        "provider_contract_version"
        in verify_src
        and
        "REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION"
        in verify_src
        and
        "REFERENCE_SEMANTIC_PROVIDER_CONTRACT_MISMATCH"
        in verify_src
    ),
)


identity_fields = (
    "reference_item_id",
    "source_sha256",
    "mechanical_analysis_id",
    "mechanical_analysis_sha256",
    "semantic_analyzer_version",
    "semantic_schema_version",
    "semantic_prompt_version",
    "vision_provider",
    "vision_model",
)


add(
    "DETERMINISTIC_IDENTITY_REBUILT",
    (
        all(
            field
            in verify_src
            for field in identity_fields
        )
        and
        '"RSA_"'
        in verify_src
        and
        "_canonical_sha256"
        in verify_src
        and
        "REFERENCE_SEMANTIC_ANALYSIS_IDENTITY_MISMATCH"
        in verify_src
    ),
)


add(
    "SEMANTIC_SCHEMA_ACTUALLY_REFERENCED",
    "schema=REFERENCE_SEMANTIC_SCHEMA"
    in verify_src,
)


add(
    "SEMANTIC_PAYLOAD_MUST_BE_DICT",
    "REFERENCE_SEMANTIC_PAYLOAD_INVALID"
    in verify_src,
)


add(
    "SEMANTIC_PAYLOAD_EXACT_FIELDS",
    "REFERENCE_SEMANTIC_PAYLOAD_FIELDS_INVALID"
    in verify_src,
)


add(
    "SEMANTIC_PAYLOAD_REQUIRED_FIELDS",
    "REFERENCE_SEMANTIC_PAYLOAD_REQUIRED_FIELDS_MISSING"
    in verify_src,
)


add(
    "SEMANTIC_PAYLOAD_TYPES_VALIDATED",
    "REFERENCE_SEMANTIC_PAYLOAD_TYPE_INVALID"
    in verify_src,
)


add(
    "PAYLOAD_CONFIDENCE_VALIDATED",
    "REFERENCE_SEMANTIC_PAYLOAD_CONFIDENCE_INVALID"
    in verify_src,
)


add(
    "TOP_LEVEL_CONFIDENCE_VALIDATED",
    "REFERENCE_SEMANTIC_CONFIDENCE_INVALID"
    in verify_src,
)


add(
    "CONFIDENCE_CROSSCHECKED",
    "REFERENCE_SEMANTIC_CONFIDENCE_MISMATCH"
    in verify_src,
)


add(
    "SOURCE_SHA_VALIDATED",
    "REFERENCE_SEMANTIC_SOURCE_SHA_INVALID"
    in verify_src,
)


add(
    "MECHANICAL_HASH_VALIDATED",
    "REFERENCE_SEMANTIC_MECHANICAL_HASH_INVALID"
    in verify_src,
)


add(
    "PRIORITY_EVIDENCE_HASH_VALIDATED",
    "REFERENCE_SEMANTIC_PRIORITY_EVIDENCE_HASH_INVALID"
    in verify_src,
)


add(
    "FORBIDDEN_FIELDS_REJECTED",
    (
        "local_media_ref"
        in verify_src
        and
        "source_resolved_path"
        in verify_src
        and
        "contact_sheet_path"
        in verify_src
        and
        "preference_signal"
        in verify_src
        and
        "REFERENCE_SEMANTIC_FORBIDDEN_PERSISTED_FIELD"
        in verify_src
    ),
)


add(
    "COPYING_POLICY_VERIFIED",
    "REFERENCE_SEMANTIC_COPYING_POLICY_INVALID"
    in verify_src,
)


add(
    "FOUNDATION_POLICY_VERIFIED",
    "REFERENCE_SEMANTIC_FOUNDATION_POLICY_INVALID"
    in verify_src,
)


add(
    "RECORD_HASH_VERIFIED",
    (
        "semantic_analysis_sha256"
        in verify_src
        and
        "REFERENCE_SEMANTIC_ANALYSIS_INTEGRITY_FAILED"
        in verify_src
    ),
)


add(
    "WORKER_REMAINS_2_24_0",
    candidate.count(
        'WORKER_VERSION = "2.24.0"'
    ) == 1,
)


add(
    "SEMANTIC_POST_ROUTE_PRESERVED",
    candidate.count(
        '@app.post("/production/reference-corpus/semantic-analysis")'
    ) == 1,
)


add(
    "SEMANTIC_LIST_ROUTE_PRESERVED",
    candidate.count(
        '@app.get("/production/reference-corpus/item/{item_id}/semantic-analyses")'
    ) == 1,
)


add(
    "SEMANTIC_LATEST_ROUTE_PRESERVED",
    candidate.count(
        '@app.get("/production/reference-corpus/item/{item_id}/semantic-analysis/latest")'
    ) == 1,
)


failed = [
    row
    for row in checks
    if not row["pass"]
]


if failed:

    REPORT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT.write_text(
        json.dumps(
            {
                "phase":
                    "09C7-B1C",

                "status":
                    "CANDIDATE_REJECTED",

                "source_sha_before":
                    before_sha,

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

                "host_written":
                    False,

                "checks":
                    checks,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    fail(
        "SM3_09C7_B1C_CANDIDATE_GATE_FAILED:"
        + ",".join(
            row["check"]
            for row in failed
        )
    )


# ============================================================
# 7. ATOMIC WRITE
# ============================================================

candidate_bytes = candidate.encode(
    "utf-8"
)


candidate_sha = sha256_bytes(
    candidate_bytes
)


tmp = WORKER.with_name(
    WORKER.name
    + ".09C7_B1C.tmp"
)


tmp.write_bytes(
    candidate_bytes
)


# Parse exact bytes that will become authoritative source.

ast.parse(
    tmp.read_text(
        encoding="utf-8"
    ),
    filename=str(tmp),
)


tmp.replace(
    WORKER
)


after_sha = sha256_bytes(
    WORKER.read_bytes()
)


if after_sha != candidate_sha:
    fail(
        "SM3_09C7_B1C_POST_WRITE_SHA_MISMATCH"
    )


if after_sha == before_sha:
    fail(
        "SM3_09C7_B1C_SOURCE_DID_NOT_CHANGE"
    )


# ============================================================
# 8. REPORT
# ============================================================

REPORT.parent.mkdir(
    parents=True,
    exist_ok=True,
)


report = {
    "phase":
        "09C7-B1C",

    "status":
        "RSA_VERIFIER_HARDENED",

    "worker_version":
        "2.24.0",

    "source_sha_before":
        before_sha,

    "source_sha_after":
        after_sha,

    "check_count":
        len(checks),

    "pass_count":
        len(checks),

    "fail_count":
        0,

    "provider_contract_verified":
        True,

    "deterministic_identity_rebuilt":
        True,

    "semantic_payload_actually_validated":
        True,

    "local_paths_rejected":
        True,

    "preference_state_rejected":
        True,

    "runtime_deployed":
        False,

    "model_called":
        False,

    "semantic_record_created":
        False,

    "checks":
        checks,
}


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "SM3_09C7_B1C_PATCHER_PASS"
)

print(
    "HOST_SHA_BEFORE="
    + before_sha
)

print(
    "HOST_SHA_AFTER="
    + after_sha
)

print(
    "CHECK_COUNT="
    + str(len(checks))
)

print(
    "PASS_COUNT="
    + str(len(checks))
)

print(
    "FAIL_COUNT=0"
)

print(
    "PROVIDER_CONTRACT_VERIFIED=True"
)

print(
    "DETERMINISTIC_IDENTITY_REBUILT=True"
)

print(
    "SEMANTIC_PAYLOAD_ACTUALLY_VALIDATED=True"
)

print(
    "RUNTIME_DEPLOYED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "SEMANTIC_RECORD_CREATED=False"
)

print(
    "REPORT="
    + str(REPORT)
)

sys.exit(0)
