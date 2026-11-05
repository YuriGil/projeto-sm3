from __future__ import annotations

import copy
import hashlib
import inspect
import json
import sys
import tempfile

from pathlib import Path

sys.path.insert(
    0,
    "/app",
)

from fastapi import HTTPException

import worker_service as ws


EXPECTED_SOURCE_SHA = (
    "602775ac25d314491283c5ffaaf0a9c5"
    "4ee41e4828bb4fba9732ff6ef93c8733"
)

REPORT = Path(
    "/tmp/SM3_09C7_B2E_MEDIA_CENTRIC_DYNAMIC_PROBE.json"
)


checks=[]


def add(
    name: str,
    passed: bool,
    detail="",
) -> None:

    checks.append({
        "check":
            name,

        "pass":
            bool(passed),

        "detail":
            str(detail),
    })


def canonical_file_sha(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def semantic_payload(
    confidence: int=88,
) -> dict:

    return {
        "hook_duration_s":
            None,

        "camera_motion":
            "UNKNOWN",

        "subject_scale":
            "UNKNOWN",

        "subject_coverage":
            None,

        "text_density":
            "UNKNOWN",

        "text_position":
            "UNKNOWN",

        "transition_style":
            "UNKNOWN",

        "speed_ramp":
            "UNKNOWN",

        "identity_usage":
            "UNKNOWN",

        "tattoo_presentation":
            "UNKNOWN",

        "story_structure":
            "UNKNOWN",

        "analysis_confidence":
            confidence,

        "notes":
            "UNKNOWN",
    }


def media_identity(
    source_sha: str,
    mechanical_id: str,
    mechanical_sha: str,
    contact_sha: str,
) -> dict:

    return {
        "source_sha256":
            source_sha,

        "mechanical_analysis_id":
            mechanical_id,

        "mechanical_analysis_sha256":
            mechanical_sha,

        "contact_sheet_sha256":
            contact_sha,

        "semantic_analyzer_version":
            ws.REFERENCE_SEMANTIC_ANALYZER_VERSION,

        "semantic_schema_version":
            ws.REFERENCE_SEMANTIC_SCHEMA_VERSION,

        "semantic_prompt_version":
            ws.REFERENCE_SEMANTIC_PROMPT_VERSION,

        "semantic_provider_contract_version":
            ws.REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION,

        "vision_provider":
            ws.VISION_PROVIDER,

        "vision_model":
            ws.VISION_MODEL,
    }


def analysis_id_for(
    source_sha: str,
    mechanical_id: str,
    mechanical_sha: str,
    contact_sha: str,
) -> str:

    identity=media_identity(
        source_sha,
        mechanical_id,
        mechanical_sha,
        contact_sha,
    )

    return (
        "RSA_"
        + ws._canonical_sha256(
            identity
        )[:32]
    )


def build_record(
    *,
    source_sha: str,
    mechanical_id: str,
    mechanical_sha: str,
    contact_sha: str,
    item_id: str,
    profile_id: str,
    acquisition_id: str,
    priority_id: str,
    priority_fingerprint: str,
    media_artifact_id: str,
    created_at: str,
) -> dict:

    semantic=semantic_payload()

    rec={
        "ok":
            True,

        "semantic_analysis_id":
            analysis_id_for(
                source_sha,
                mechanical_id,
                mechanical_sha,
                contact_sha,
            ),

        "contract_version":
            ws.REFERENCE_SEMANTIC_ANALYSIS_CONTRACT_VERSION,

        "analyzer_version":
            ws.REFERENCE_SEMANTIC_ANALYZER_VERSION,

        "semantic_schema_version":
            ws.REFERENCE_SEMANTIC_SCHEMA_VERSION,

        "semantic_prompt_version":
            ws.REFERENCE_SEMANTIC_PROMPT_VERSION,

        "provider_contract_version":
            ws.REFERENCE_SEMANTIC_PROVIDER_CONTRACT_VERSION,

        "creation_reference_item_id":
            item_id,

        "creation_reference_profile_id":
            profile_id,

        "creation_acquisition_id":
            acquisition_id,

        "creation_priority_decision_id":
            priority_id,

        "creation_priority_evidence_fingerprint":
            priority_fingerprint,

        "media_artifact_id":
            media_artifact_id,

        "source_sha256":
            source_sha,

        "mechanical_analysis_id":
            mechanical_id,

        "mechanical_analysis_sha256":
            mechanical_sha,

        "contact_sheet_sha256":
            contact_sha,

        "vision_provider":
            ws.VISION_PROVIDER,

        "vision_model":
            ws.VISION_MODEL,

        "vision_response_id":
            "resp-isolated",

        "semantic_confidence":
            semantic[
                "analysis_confidence"
            ],

        "semantic":
            semantic,

        "created_at":
            created_at,

        "copying_forbidden":
            True,

        "foundation_override_allowed":
            False,
    }

    rec[
        "semantic_analysis_sha256"
    ]=ws._canonical_sha256(
        rec
    )

    return rec


def expect_409(
    name: str,
    candidate: dict,
    detail: str,
) -> None:

    try:

        ws._verify_reference_semantic_analysis(
            candidate
        )

    except HTTPException as exc:

        add(
            name,
            (
                exc.status_code==409
                and
                exc.detail==detail
            ),
            (
                str(exc.status_code)
                + ":"
                + str(exc.detail)
            ),
        )

        return

    except Exception as exc:

        add(
            name,
            False,
            (
                type(exc).__name__
                + ":"
                + str(exc)
            ),
        )

        return

    add(
        name,
        False,
        "NO_EXCEPTION",
    )


# ============================================================
# 1. IMAGE IDENTITY / CONTRACT
# ============================================================

worker_path=Path(
    "/app/worker_service.py"
)


image_source_sha=canonical_file_sha(
    worker_path
)


add(
    "IMAGE_SOURCE_SHA_MATCH",
    image_source_sha
    == EXPECTED_SOURCE_SHA,
    image_source_sha,
)


add(
    "WORKER_VERSION_2_24_0",
    ws.WORKER_VERSION
    == "2.24.0",
    ws.WORKER_VERSION,
)


provider_signature=list(
    inspect.signature(
        ws._reference_semantic_provider_analyze
    ).parameters.keys()
)


add(
    "PROVIDER_SIGNATURE_MEDIA_ONLY",
    provider_signature
    == [
        "contact_sheet",
        "mechanical",
    ],
    provider_signature,
)


storage_signature=list(
    inspect.signature(
        ws._reference_semantic_analysis_dir
    ).parameters.keys()
)


add(
    "STORAGE_SIGNATURE_SOURCE_ONLY",
    storage_signature
    == [
        "source_sha256"
    ],
    storage_signature,
)


# ============================================================
# 2. VALID MEDIA-CENTRIC RSA
# ============================================================

source_sha="1"*64
mechanical_sha="2"*64
contact_sha="3"*64
priority_hash="4"*64
mechanical_id="RMA_B2E_SYNTHETIC"


record_a=build_record(
    source_sha=source_sha,
    mechanical_id=mechanical_id,
    mechanical_sha=mechanical_sha,
    contact_sha=contact_sha,
    item_id="RI_B2E_A",
    profile_id="RP_B2E_A",
    acquisition_id="RM_B2E_A",
    priority_id="RPD_B2E_A",
    priority_fingerprint=priority_hash,
    media_artifact_id="MA_B2E",
    created_at="2026-09-24T00:00:00+00:00",
)


try:

    verified=(
        ws._verify_reference_semantic_analysis(
            copy.deepcopy(
                record_a
            )
        )
    )

    add(
        "VALID_MEDIA_CENTRIC_RSA_ACCEPTED",
        verified[
            "semantic_analysis_id"
        ]
        == record_a[
            "semantic_analysis_id"
        ],
        verified.get(
            "semantic_analysis_id"
        ),
    )

except Exception as exc:

    add(
        "VALID_MEDIA_CENTRIC_RSA_ACCEPTED",
        False,
        (
            type(exc).__name__
            + ":"
            + str(exc)
        ),
    )


# ============================================================
# 3. CREATION CONTEXT DOES NOT CHANGE RSA IDENTITY
# ============================================================

record_b=build_record(
    source_sha=source_sha,
    mechanical_id=mechanical_id,
    mechanical_sha=mechanical_sha,
    contact_sha=contact_sha,
    item_id="RI_B2E_B",
    profile_id="RP_B2E_B",
    acquisition_id="RM_B2E_B",
    priority_id="RPD_B2E_B",
    priority_fingerprint="5"*64,
    media_artifact_id="MA_B2E",
    created_at="2026-09-24T00:01:00+00:00",
)


add(
    "DIFFERENT_CREATION_CONTEXT_SAME_RSA_ID",
    (
        record_a[
            "semantic_analysis_id"
        ]
        ==
        record_b[
            "semantic_analysis_id"
        ]
    ),
    (
        record_a[
            "semantic_analysis_id"
        ]
        + ":"
        + record_b[
            "semantic_analysis_id"
        ]
    ),
)


try:

    ws._verify_reference_semantic_analysis(
        copy.deepcopy(
            record_b
        )
    )

    add(
        "SECOND_CREATION_CONTEXT_VALID",
        True,
    )

except Exception as exc:

    add(
        "SECOND_CREATION_CONTEXT_VALID",
        False,
        (
            type(exc).__name__
            + ":"
            + str(exc)
        ),
    )


# ============================================================
# 4. CONTACT SHEET HASH IS IDENTITY-BOUND
# ============================================================

bad_contact=copy.deepcopy(
    record_a
)

bad_contact[
    "contact_sheet_sha256"
]="6"*64

bad_contact[
    "semantic_analysis_sha256"
]=ws._canonical_sha256(
    {
        key:value
        for key,value in bad_contact.items()
        if key!="semantic_analysis_sha256"
    }
)


expect_409(
    "CONTACT_HASH_IDENTITY_MUTATION_REJECTED",
    bad_contact,
    "REFERENCE_SEMANTIC_ANALYSIS_IDENTITY_MISMATCH",
)


# ============================================================
# 5. PROVIDER CONTRACT FAIL-CLOSED
# ============================================================

bad_provider=copy.deepcopy(
    record_a
)

bad_provider[
    "provider_contract_version"
]="BROKEN"

bad_provider[
    "semantic_analysis_sha256"
]=ws._canonical_sha256(
    {
        key:value
        for key,value in bad_provider.items()
        if key!="semantic_analysis_sha256"
    }
)


expect_409(
    "PROVIDER_CONTRACT_MUTATION_REJECTED",
    bad_provider,
    "REFERENCE_SEMANTIC_PROVIDER_CONTRACT_MISMATCH",
)


# ============================================================
# 6. OLD DIRECT ITEM CONTEXT IS FORBIDDEN
# ============================================================

bad_item_context=copy.deepcopy(
    record_a
)

bad_item_context[
    "reference_item_id"
]="RI_FORBIDDEN_DIRECT"

bad_item_context[
    "semantic_analysis_sha256"
]=ws._canonical_sha256(
    {
        key:value
        for key,value in bad_item_context.items()
        if key!="semantic_analysis_sha256"
    }
)


expect_409(
    "OLD_DIRECT_ITEM_CONTEXT_REJECTED",
    bad_item_context,
    "REFERENCE_SEMANTIC_FORBIDDEN_PERSISTED_FIELD:reference_item_id",
)


# ============================================================
# 7. PAYLOAD FAIL-CLOSED
# ============================================================

bad_payload=copy.deepcopy(
    record_a
)

bad_payload[
    "semantic"
][
    "unexpected_field"
]="INVALID"

bad_payload[
    "semantic_analysis_sha256"
]=ws._canonical_sha256(
    {
        key:value
        for key,value in bad_payload.items()
        if key!="semantic_analysis_sha256"
    }
)


expect_409(
    "SEMANTIC_EXTRA_FIELD_REJECTED",
    bad_payload,
    "REFERENCE_SEMANTIC_PAYLOAD_FIELDS_INVALID",
)


# ============================================================
# 8. CONFIDENCE CROSS-CHECK
# ============================================================

bad_confidence=copy.deepcopy(
    record_a
)

bad_confidence[
    "semantic_confidence"
]=87

bad_confidence[
    "semantic_analysis_sha256"
]=ws._canonical_sha256(
    {
        key:value
        for key,value in bad_confidence.items()
        if key!="semantic_analysis_sha256"
    }
)


expect_409(
    "CONFIDENCE_MISMATCH_REJECTED",
    bad_confidence,
    "REFERENCE_SEMANTIC_CONFIDENCE_MISMATCH",
)


# ============================================================
# 9. RECORD HASH FAIL-CLOSED
# ============================================================

bad_record_hash=copy.deepcopy(
    record_a
)

bad_record_hash[
    "created_at"
]="2026-09-24T02:00:00+00:00"


expect_409(
    "RECORD_INTEGRITY_MUTATION_REJECTED",
    bad_record_hash,
    "REFERENCE_SEMANTIC_ANALYSIS_INTEGRITY_FAILED",
)


# ============================================================
# 10. STORAGE PATH IS MEDIA-CENTRIC
# ============================================================

storage_path=(
    ws._reference_semantic_analysis_path(
        source_sha,
        record_a[
            "semantic_analysis_id"
        ],
    )
)


storage_path_text=str(
    storage_path
)


add(
    "STORAGE_PATH_CONTAINS_SOURCE_SHA",
    source_sha
    in storage_path_text,
    storage_path_text,
)


add(
    "STORAGE_PATH_HAS_SHA_PREFIX",
    (
        (
            "/"
            + source_sha[:2]
            + "/"
            + source_sha
            + "/"
        )
        in storage_path_text.replace(
            "\\",
            "/",
        )
    ),
    storage_path_text,
)


add(
    "STORAGE_PATH_HAS_NO_ITEM_ID",
    (
        "RI_B2E_A"
        not in storage_path_text
        and
        "RP_B2E_A"
        not in storage_path_text
    ),
    storage_path_text,
)


# ============================================================
# 11. BEHAVIORAL ENGINE TESTS IN /tmp ONLY
# ============================================================

with tempfile.TemporaryDirectory(
    prefix="sm3_b2e_"
) as tmp_raw:

    tmp=Path(
        tmp_raw
    )

    source_path=(
        tmp
        / "source.mp4"
    )

    source_path.write_bytes(
        b"SM3-B2E-SYNTHETIC-MEDIA"
    )

    real_source_sha=canonical_file_sha(
        source_path
    )


    contact_path=(
        tmp
        / "contact.jpg"
    )

    contact_path.write_bytes(
        b"SM3-B2E-SYNTHETIC-CONTACT"
    )

    real_contact_sha=canonical_file_sha(
        contact_path
    )


    mechanical={
        "mechanical_analysis_id":
            "RMA_B2E_ENGINE",

        "mechanical_analysis_sha256":
            "7"*64,

        "contact_sheet_sha256":
            real_contact_sha,

        "source_sha256":
            real_source_sha,

        "mechanical":{
            "duration_seconds":
                12.0,
        },
    }


    media_artifact={
        "media_artifact_id":
            "MA_B2E_ENGINE",
    }


    cache_path=(
        tmp
        / "RSA_ENGINE.json"
    )


    originals={
        "_require_reference_item_active":
            ws._require_reference_item_active,

        "_reference_semantic_load_acquisition":
            ws._reference_semantic_load_acquisition,

        "_resolve_reference_acquisition_source":
            ws._resolve_reference_acquisition_source,

        "_reference_semantic_load_mechanical":
            ws._reference_semantic_load_mechanical,

        "_reference_semantic_contact_sheet":
            ws._reference_semantic_contact_sheet,

        "_reference_semantic_analysis_path":
            ws._reference_semantic_analysis_path,

        "_reference_semantic_authorizing_priority":
            ws._reference_semantic_authorizing_priority,

        "_reference_semantic_provider_analyze":
            ws._reference_semantic_provider_analyze,
    }


    state={
        "priority_calls":
            0,

        "provider_calls":
            0,

        "active_item":
            "RI_B2E_ENGINE_A",
    }


    def fake_active(
        item_id,
    ):

        return {
            "reference_item_id":
                item_id,

            "reference_profile_id":
                (
                    "RP_B2E_ENGINE_A"
                    if item_id
                    == "RI_B2E_ENGINE_A"
                    else
                    "RP_B2E_ENGINE_B"
                ),

            "item_type":
                "VIDEO",
        }


    def fake_acquisition(
        item,
        acquisition_id,
    ):

        return {
            "acquisition_id":
                acquisition_id,

            "reference_item_id":
                item[
                    "reference_item_id"
                ],

            "media_artifact_id":
                "MA_B2E_ENGINE",

            "source_sha256":
                real_source_sha,
        }


    def fake_priority_forbidden(
        *args,
        **kwargs,
    ):

        state[
            "priority_calls"
        ]+=1

        raise AssertionError(
            "PRIORITY_CALLED_ON_CACHE_HIT"
        )


    def fake_provider_forbidden(
        *args,
        **kwargs,
    ):

        state[
            "provider_calls"
        ]+=1

        raise AssertionError(
            "PROVIDER_CALLED_ON_CACHE_HIT"
        )


    try:

        ws._require_reference_item_active=(
            fake_active
        )

        ws._reference_semantic_load_acquisition=(
            fake_acquisition
        )

        ws._resolve_reference_acquisition_source=(
            lambda acquisition:(
                source_path,
                media_artifact,
            )
        )

        ws._reference_semantic_load_mechanical=(
            lambda source_sha,mechanical_analysis_id:
                mechanical
        )

        ws._reference_semantic_contact_sheet=(
            lambda mechanical_rec:
                contact_path
        )

        ws._reference_semantic_analysis_path=(
            lambda source_sha,analysis_id:
                cache_path
        )


        # ----------------------------------------------------
        # 11A. CROSS-ITEM CACHE HIT
        # Existing RSA was created under Item A.
        # Request comes from Item B with the same media.
        # Priority/provider must NOT be called.
        # ----------------------------------------------------

        existing=build_record(
            source_sha=
                real_source_sha,

            mechanical_id=
                mechanical[
                    "mechanical_analysis_id"
                ],

            mechanical_sha=
                mechanical[
                    "mechanical_analysis_sha256"
                ],

            contact_sha=
                real_contact_sha,

            item_id=
                "RI_B2E_ENGINE_A",

            profile_id=
                "RP_B2E_ENGINE_A",

            acquisition_id=
                "RM_B2E_ENGINE_A",

            priority_id=
                "RPD_B2E_ENGINE_A",

            priority_fingerprint=
                "8"*64,

            media_artifact_id=
                "MA_B2E_ENGINE",

            created_at=
                "2026-09-24T00:10:00+00:00",
        )


        cache_path.write_text(
            json.dumps(
                existing,
                ensure_ascii=False,
                separators=(",",":"),
            ),
            encoding="utf-8",
        )


        ws._reference_semantic_authorizing_priority=(
            fake_priority_forbidden
        )

        ws._reference_semantic_provider_analyze=(
            fake_provider_forbidden
        )


        req_b=(
            ws.ReferenceSemanticAnalysisRequest(
                reference_item_id=
                    "RI_B2E_ENGINE_B",

                acquisition_id=
                    "RM_B2E_ENGINE_B",

                mechanical_analysis_id=
                    mechanical[
                        "mechanical_analysis_id"
                    ],

                priority_decision_id=
                    "RPD_B2E_ENGINE_B",
            )
        )


        cache_result=(
            ws.production_reference_semantic_analysis(
                req_b
            )
        )


        add(
            "CROSS_ITEM_CACHE_HIT_REUSED",
            cache_result.get(
                "reused_existing"
            )
            is True,
            cache_result,
        )


        add(
            "CROSS_ITEM_CACHE_HIT_PROVIDER_FALSE",
            cache_result.get(
                "provider_called"
            )
            is False,
        )


        add(
            "CROSS_ITEM_CACHE_HIT_PRIORITY_ALLOW_FALSE",
            cache_result.get(
                "priority_generation_allow_checked"
            )
            is False,
        )


        add(
            "CROSS_ITEM_CACHE_HIT_ZERO_PRIORITY_CALLS",
            state[
                "priority_calls"
            ]
            == 0,
            state[
                "priority_calls"
            ],
        )


        add(
            "CROSS_ITEM_CACHE_HIT_ZERO_PROVIDER_CALLS",
            state[
                "provider_calls"
            ]
            == 0,
            state[
                "provider_calls"
            ],
        )


        add(
            "CROSS_ITEM_CACHE_PRESERVES_CREATION_PROVENANCE",
            (
                cache_result[
                    "analysis"
                ][
                    "creation_reference_item_id"
                ]
                ==
                "RI_B2E_ENGINE_A"
            ),
            cache_result[
                "analysis"
            ].get(
                "creation_reference_item_id"
            ),
        )


        # ----------------------------------------------------
        # 11B. CACHE MISS
        # Must call Priority exactly once and provider exactly once.
        # ----------------------------------------------------

        cache_path.unlink()


        state[
            "priority_calls"
        ]=0

        state[
            "provider_calls"
        ]=0


        def fake_priority_allowed(
            item,
            source_sha,
            mechanical_rec,
            priority_id,
        ):

            state[
                "priority_calls"
            ]+=1

            return {
                "priority_decision_id":
                    priority_id,

                "evidence_fingerprint":
                    "9"*64,

                "semantic_analysis_allowed":
                    True,

                "decision":
                    "SEMANTIC_ANALYSIS",
            }


        def fake_provider(
            contact_sheet,
            mechanical_rec,
        ):

            state[
                "provider_calls"
            ]+=1

            return (
                semantic_payload(
                    91
                ),
                "resp-b2e-cache-miss",
            )


        ws._reference_semantic_authorizing_priority=(
            fake_priority_allowed
        )

        ws._reference_semantic_provider_analyze=(
            fake_provider
        )


        req_a=(
            ws.ReferenceSemanticAnalysisRequest(
                reference_item_id=
                    "RI_B2E_ENGINE_A",

                acquisition_id=
                    "RM_B2E_ENGINE_A",

                mechanical_analysis_id=
                    mechanical[
                        "mechanical_analysis_id"
                    ],

                priority_decision_id=
                    "RPD_B2E_ENGINE_A",
            )
        )


        miss_result=(
            ws.production_reference_semantic_analysis(
                req_a
            )
        )


        add(
            "CACHE_MISS_CREATED_NEW_RSA",
            miss_result.get(
                "reused_existing"
            )
            is False,
        )


        add(
            "CACHE_MISS_PROVIDER_TRUE",
            miss_result.get(
                "provider_called"
            )
            is True,
        )


        add(
            "CACHE_MISS_PRIORITY_ALLOW_TRUE",
            miss_result.get(
                "priority_generation_allow_checked"
            )
            is True,
        )


        add(
            "CACHE_MISS_PRIORITY_CALLED_ONCE",
            state[
                "priority_calls"
            ]
            == 1,
            state[
                "priority_calls"
            ],
        )


        add(
            "CACHE_MISS_PROVIDER_CALLED_ONCE",
            state[
                "provider_calls"
            ]
            == 1,
            state[
                "provider_calls"
            ],
        )


        add(
            "CACHE_MISS_RSA_PERSISTED_ONLY_IN_TMP",
            cache_path.exists(),
            cache_path,
        )


        persisted=json.loads(
            cache_path.read_text(
                encoding="utf-8"
            )
        )


        try:

            ws._verify_reference_semantic_analysis(
                persisted
            )

            add(
                "CACHE_MISS_PERSISTED_RSA_VALID",
                True,
            )

        except Exception as exc:

            add(
                "CACHE_MISS_PERSISTED_RSA_VALID",
                False,
                (
                    type(exc).__name__
                    + ":"
                    + str(exc)
                ),
            )


        # ----------------------------------------------------
        # 11C. SECOND ITEM REUSES RSA JUST CREATED BY ITEM A
        # ----------------------------------------------------

        state[
            "priority_calls"
        ]=0

        state[
            "provider_calls"
        ]=0


        ws._reference_semantic_authorizing_priority=(
            fake_priority_forbidden
        )

        ws._reference_semantic_provider_analyze=(
            fake_provider_forbidden
        )


        second_item_result=(
            ws.production_reference_semantic_analysis(
                req_b
            )
        )


        add(
            "POST_GENERATION_SECOND_ITEM_REUSES_RSA",
            second_item_result.get(
                "reused_existing"
            )
            is True,
        )


        add(
            "POST_GENERATION_SECOND_ITEM_NO_PRIORITY_CALL",
            state[
                "priority_calls"
            ]
            == 0,
            state[
                "priority_calls"
            ],
        )


        add(
            "POST_GENERATION_SECOND_ITEM_NO_PROVIDER_CALL",
            state[
                "provider_calls"
            ]
            == 0,
            state[
                "provider_calls"
            ],
        )


        add(
            "POST_GENERATION_RSA_CREATION_OWNER_REMAINS_ITEM_A",
            (
                second_item_result[
                    "analysis"
                ][
                    "creation_reference_item_id"
                ]
                ==
                "RI_B2E_ENGINE_A"
            ),
        )


        # ----------------------------------------------------
        # 11D. ACTIVE GATE REMAINS BEFORE CACHE REUSE
        # ----------------------------------------------------

        def tombstoned(
            item_id,
        ):

            raise HTTPException(
                409,
                (
                    "REFERENCE_ITEM_TOMBSTONED:"
                    + item_id
                ),
            )


        ws._require_reference_item_active=(
            tombstoned
        )


        try:

            ws.production_reference_semantic_analysis(
                req_b
            )


        except HTTPException as exc:

            add(
                "TOMBSTONED_ITEM_BLOCKS_CACHE_REUSE",
                (
                    exc.status_code==409
                    and
                    exc.detail
                    ==
                    "REFERENCE_ITEM_TOMBSTONED:RI_B2E_ENGINE_B"
                ),
                (
                    str(exc.status_code)
                    + ":"
                    + str(exc.detail)
                ),
            )

        except Exception as exc:

            add(
                "TOMBSTONED_ITEM_BLOCKS_CACHE_REUSE",
                False,
                (
                    type(exc).__name__
                    + ":"
                    + str(exc)
                ),
            )

        else:

            add(
                "TOMBSTONED_ITEM_BLOCKS_CACHE_REUSE",
                False,
                "NO_EXCEPTION",
            )


    finally:

        for name,value in originals.items():

            setattr(
                ws,
                name,
                value,
            )


# ============================================================
# RESULT
# ============================================================

failed=[
    row
    for row in checks
    if not row[
        "pass"
    ]
]


report={
    "phase":
        "09C7-B2E",

    "environment":
        "ISOLATED_EPHEMERAL_CONTAINER",

    "image_source_sha256":
        image_source_sha,

    "worker_version":
        ws.WORKER_VERSION,

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

    "production_volume_mounted":
        False,

    "real_semantic_api_called":
        False,

    "real_provider_called":
        False,

    "real_model_called":
        False,

    "production_record_created":
        False,

    "checks":
        checks,

    "all_passed":
        not failed,
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
    "=== SM3 09C7-B2E ISOLATED DYNAMIC CHECKS ==="
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
                if row[
                    "detail"
                ]
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
    "IMAGE_SOURCE_SHA256="
    + image_source_sha
)

print(
    "WORKER_VERSION="
    + ws.WORKER_VERSION
)

print(
    "PRODUCTION_VOLUME_MOUNTED=False"
)

print(
    "REAL_SEMANTIC_API_CALLED=False"
)

print(
    "REAL_PROVIDER_CALLED=False"
)

print(
    "REAL_MODEL_CALLED=False"
)

print(
    "PRODUCTION_RECORD_CREATED=False"
)

print(
    "REPORT="
    + str(
        REPORT
    )
)


if failed:

    print(
        "SM3_09C7_B2E_ISOLATED_DYNAMIC_PROBE_FAIL"
    )

    sys.exit(1)


print(
    "SM3_09C7_B2E_ISOLATED_DYNAMIC_PROBE_PASS"
)

sys.exit(0)
