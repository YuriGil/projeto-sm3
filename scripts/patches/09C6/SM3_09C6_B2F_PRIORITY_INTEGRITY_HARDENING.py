from pathlib import Path
from datetime import datetime
import ast
import codecs
import hashlib
import os
import shutil


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = (
    ROOT
    / "worker"
    / "worker_service.py"
)

BACKUPS = (
    ROOT
    / "sm3_backups"
)

EXPECTED_BEFORE_SHA = (
    "c759258bbfd3d86bc66d8810f2528056"
    "24fb0ed8a9b9b5c7f93c06e5bc086512"
)


# ============================================================
# 1. LOAD EXACT B1 SOURCE
# ============================================================

if not WORKER.exists():
    raise SystemExit(
        "SM3_09C6_B2F_WORKER_NOT_FOUND"
    )

raw = WORKER.read_bytes()

before_sha = hashlib.sha256(
    raw
).hexdigest()

print(
    f"BEFORE_SHA256={before_sha}"
)

if before_sha != EXPECTED_BEFORE_SHA:
    raise SystemExit(
        "SM3_09C6_B2F_BASELINE_SHA_MISMATCH:"
        f"{before_sha}"
    )


has_bom = raw.startswith(
    codecs.BOM_UTF8
)

if has_bom:
    text = raw[
        len(codecs.BOM_UTF8):
    ].decode("utf-8")
else:
    text = raw.decode("utf-8")


NL = (
    "\r\n"
    if "\r\n" in text
    else "\n"
)


if text.count(
    'WORKER_VERSION = "2.23.0"'
) != 1:
    raise SystemExit(
        "SM3_09C6_B2F_EXPECTED_VERSION_2_23_0_NOT_FOUND"
    )


# ============================================================
# 2. SAFE FUNCTION REPLACER
# ============================================================

def replace_function(
    start_marker,
    next_marker,
    replacement,
    label,
):
    global text

    start_count = text.count(
        start_marker
    )

    next_count = text.count(
        next_marker
    )

    print(
        f"{label}_START_COUNT={start_count}"
    )

    print(
        f"{label}_NEXT_COUNT={next_count}"
    )

    if start_count != 1:
        raise SystemExit(
            f"SM3_09C6_B2F_{label}_START_INVALID:"
            f"{start_count}"
        )

    if next_count != 1:
        raise SystemExit(
            f"SM3_09C6_B2F_{label}_NEXT_INVALID:"
            f"{next_count}"
        )

    start = text.index(
        start_marker
    )

    end = text.index(
        next_marker,
        start,
    )

    if end <= start:
        raise SystemExit(
            f"SM3_09C6_B2F_{label}_RANGE_INVALID"
        )

    replacement = (
        replacement
        .replace("\r\n", "\n")
        .replace("\n", NL)
    )

    text = (
        text[:start]
        + replacement
        + NL
        + NL
        + text[end:]
    )


# ============================================================
# 3. HARDEN PRIORITY DECISION VERIFIER
# ============================================================

priority_verifier = r'''def _verify_reference_priority_decision(
    rec: dict[str,Any],
) -> dict[str,Any]:

    if (
        rec.get("contract_version")
        != REFERENCE_PRIORITY_DECISION_CONTRACT_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_CONTRACT_INVALID",
        )

    if (
        rec.get("engine_version")
        != REFERENCE_PRIORITY_ENGINE_VERSION
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_ENGINE_VERSION_INVALID",
        )


    # --------------------------------------------------------
    # SOURCE + MECHANICAL IDENTITY
    # --------------------------------------------------------

    source_sha=str(
        rec.get("source_sha256") or ""
    ).lower()

    if (
        len(source_sha) != 64
        or any(
            c not in "0123456789abcdef"
            for c in source_sha
        )
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_SOURCE_SHA_INVALID",
        )


    mechanical_id=str(
        rec.get("mechanical_analysis_id") or ""
    )

    if not mechanical_id.startswith(
        "RMA_"
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_MECHANICAL_ID_INVALID",
        )


    mechanical_hash=str(
        rec.get(
            "mechanical_analysis_sha256"
        ) or ""
    ).lower()

    if (
        len(mechanical_hash) != 64
        or any(
            c not in "0123456789abcdef"
            for c in mechanical_hash
        )
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_MECHANICAL_HASH_INVALID",
        )


    # --------------------------------------------------------
    # COMPONENTS MUST EXIST
    # --------------------------------------------------------

    components=rec.get(
        "components"
    )

    if not isinstance(
        components,
        dict,
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_COMPONENTS_INVALID",
        )


    required_components={
        "human_priority",
        "metric_signal",
        "mechanical_evidence_quality",
    }

    if not required_components.issubset(
        set(components.keys())
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_COMPONENTS_INCOMPLETE",
        )


    if not isinstance(
        components.get(
            "human_priority"
        ),
        dict,
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_HUMAN_COMPONENT_INVALID",
        )


    if not isinstance(
        components.get(
            "metric_signal"
        ),
        dict,
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_METRIC_COMPONENT_INVALID",
        )


    if not isinstance(
        components.get(
            "mechanical_evidence_quality"
        ),
        dict,
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_MECHANICAL_COMPONENT_INVALID",
        )


    # --------------------------------------------------------
    # REBUILD EVIDENCE FINGERPRINT
    #
    # This exactly mirrors _reference_priority_current_evidence
    # BEFORE evidence_fingerprint itself is appended.
    # --------------------------------------------------------

    evidence={
        "reference_profile_id":
            rec.get(
                "reference_profile_id"
            ),

        "human_priority":
            components[
                "human_priority"
            ],

        "metric_signal":
            components[
                "metric_signal"
            ],

        "mechanical_evidence_quality":
            components[
                "mechanical_evidence_quality"
            ],
    }


    expected_evidence_fingerprint=(
        _canonical_sha256(
            evidence
        )
    )


    evidence_fingerprint=str(
        rec.get(
            "evidence_fingerprint"
        ) or ""
    ).lower()


    if (
        len(evidence_fingerprint) != 64
        or any(
            c not in "0123456789abcdef"
            for c in evidence_fingerprint
        )
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_EVIDENCE_FINGERPRINT_INVALID",
        )


    if (
        expected_evidence_fingerprint
        != evidence_fingerprint
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_EVIDENCE_FINGERPRINT_MISMATCH",
        )


    # --------------------------------------------------------
    # REBUILD SCORE + EFFECTIVE WEIGHTS
    # --------------------------------------------------------

    recomputed_score,recomputed_weights=(
        _reference_priority_score(
            evidence
        )
    )


    try:
        persisted_score=float(
            rec.get(
                "priority_score"
            )
        )
    except Exception:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_SCORE_INVALID",
        )


    if (
        persisted_score < 0.0
        or persisted_score > 100.0
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_SCORE_RANGE_INVALID",
        )


    if abs(
        persisted_score
        - float(recomputed_score)
    ) > 0.0001:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_SCORE_MISMATCH",
        )


    persisted_weights=rec.get(
        "effective_weights"
    )

    if (
        not isinstance(
            persisted_weights,
            dict,
        )
        or persisted_weights
            != recomputed_weights
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_EFFECTIVE_WEIGHTS_MISMATCH",
        )


    # --------------------------------------------------------
    # REBUILD DECISION FROM SCORE
    # --------------------------------------------------------

    if (
        persisted_score
        >= REFERENCE_PRIORITY_SEMANTIC_THRESHOLD
    ):
        expected_decision=(
            "SEMANTIC_ANALYSIS"
        )

    elif (
        persisted_score
        >= REFERENCE_PRIORITY_DEFER_THRESHOLD
    ):
        expected_decision="DEFER"

    else:
        expected_decision="SKIP"


    decision=rec.get(
        "decision"
    )

    if decision not in {
        "SEMANTIC_ANALYSIS",
        "DEFER",
        "SKIP",
    }:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_INVALID",
        )


    if decision != expected_decision:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_SCORE_MISMATCH",
        )


    eligibility=rec.get(
        "eligibility"
    )

    if eligibility not in {
        "ELIGIBLE",
        "DEFERRED",
        "INELIGIBLE",
    }:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_ELIGIBILITY_INVALID",
        )


    # --------------------------------------------------------
    # SEMANTIC ALLOW MUST BE DERIVED, NEVER ARBITRARY
    # --------------------------------------------------------

    semantic_allowed=bool(
        rec.get(
            "semantic_analysis_allowed"
        )
    )


    expected_semantic_allowed=(
        eligibility == "ELIGIBLE"
        and decision == "SEMANTIC_ANALYSIS"
    )


    if (
        semantic_allowed
        != expected_semantic_allowed
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_SEMANTIC_ALLOW_INVALID",
        )


    # --------------------------------------------------------
    # REBUILD DETERMINISTIC PRIORITY DECISION ID
    # --------------------------------------------------------

    identity={
        "reference_item_id":
            rec.get(
                "reference_item_id"
            ),

        "source_sha256":
            source_sha,

        "mechanical_analysis_id":
            mechanical_id,

        "mechanical_analysis_sha256":
            mechanical_hash,

        "evidence_fingerprint":
            evidence_fingerprint,

        "priority_engine_version":
            rec.get(
                "engine_version"
            ),
    }


    expected_priority_decision_id=(
        "RPD_"
        + _canonical_sha256(
            identity
        )[:32]
    )


    priority_decision_id=str(
        rec.get(
            "priority_decision_id"
        ) or ""
    )


    if (
        priority_decision_id
        != expected_priority_decision_id
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_IDENTITY_MISMATCH",
        )


    # --------------------------------------------------------
    # ENGINE / SAFETY INVARIANTS
    # --------------------------------------------------------

    if rec.get(
        "model_call_used"
    ) is not False:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_MODEL_CALL_POLICY_INVALID",
        )


    if rec.get(
        "copying_forbidden"
    ) is not True:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_COPYING_POLICY_INVALID",
        )


    if rec.get(
        "foundation_override_allowed"
    ) is not False:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_FOUNDATION_POLICY_INVALID",
        )


    reasons=rec.get(
        "reason_codes"
    )

    if (
        not isinstance(
            reasons,
            list,
        )
        or not reasons
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_REASON_CODES_INVALID",
        )


    # --------------------------------------------------------
    # FINAL RECORD HASH
    # --------------------------------------------------------

    expected=str(
        rec.get(
            "priority_decision_sha256"
        ) or ""
    ).lower()


    chk={
        k:v
        for k,v in rec.items()
        if k != "priority_decision_sha256"
    }


    if (
        len(expected) != 64
        or any(
            c not in "0123456789abcdef"
            for c in expected
        )
        or _canonical_sha256(
            chk
        ) != expected
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_INTEGRITY_FAILED",
        )


    return rec
'''


replace_function(
    "def _verify_reference_priority_decision(",
    "def _reference_priority_number(",
    priority_verifier,
    "PRIORITY_VERIFIER",
)


# ============================================================
# 4. PHYSICALLY VERIFY CONTACT SHEET EVIDENCE
# ============================================================

mechanical_quality = r'''def _reference_priority_mechanical_quality(
    mechanical_analysis: dict[str,Any],
) -> float:

    try:
        confidence=float(
            mechanical_analysis.get(
                "mechanical_confidence"
            )
        )
    except Exception:
        confidence=0.0


    confidence=max(
        0.0,
        min(
            100.0,
            confidence,
        ),
    )


    contact_path=str(
        mechanical_analysis.get(
            "contact_sheet_path"
        ) or ""
    ).strip()


    contact_sha=str(
        mechanical_analysis.get(
            "contact_sheet_sha256"
        ) or ""
    ).lower()


    contact_sha_valid=(
        len(contact_sha) == 64
        and all(
            c in "0123456789abcdef"
            for c in contact_sha
        )
    )


    contact_verified=False


    if (
        contact_path
        and contact_sha_valid
    ):

        try:
            contact_file=_ensure_under(
                Path(contact_path),
                CONTACTS,
            )

            if (
                contact_file.exists()
                and contact_file.is_file()
            ):
                actual_contact_sha=(
                    sha256_file(
                        contact_file
                    ).lower()
                )

                contact_verified=(
                    actual_contact_sha
                    == contact_sha
                )

        except Exception:
            contact_verified=False


    # The Priority Engine does not declare the media invalid
    # merely because this derived artifact disappeared.
    #
    # Instead, evidence confidence is capped because the
    # mechanical evidence can no longer be independently
    # reproduced from its contact sheet.
    if not contact_verified:
        confidence=min(
            confidence,
            60.0,
        )


    return round(
        confidence,
        4,
    )
'''


replace_function(
    "def _reference_priority_mechanical_quality(",
    "def _reference_priority_current_evidence(",
    mechanical_quality,
    "MECHANICAL_QUALITY",
)


# ============================================================
# 5. INDEPENDENT LOCAL ASSERTIONS
# ============================================================

ast.parse(
    text
)

compile(
    text,
    str(WORKER),
    "exec",
)


verifier_start=text.index(
    "def _verify_reference_priority_decision("
)

verifier_end=text.index(
    "def _reference_priority_number(",
    verifier_start,
)

verifier_source=text[
    verifier_start:verifier_end
]


mechanical_start=text.index(
    "def _reference_priority_mechanical_quality("
)

mechanical_end=text.index(
    "def _reference_priority_current_evidence(",
    mechanical_start,
)

mechanical_source=text[
    mechanical_start:mechanical_end
]


checks={

    "WORKER_STAYS_2_23":
        text.count(
            'WORKER_VERSION = "2.23.0"'
        ) == 1,


    "VERIFIER_REBUILDS_EVIDENCE":
        (
            "expected_evidence_fingerprint"
            in verifier_source
            and
            "_canonical_sha256("
            in verifier_source
        ),


    "VERIFIER_REBUILDS_SCORE":
        (
            "_reference_priority_score("
            in verifier_source
            and
            "REFERENCE_PRIORITY_SCORE_MISMATCH"
            in verifier_source
        ),


    "VERIFIER_REBUILDS_WEIGHTS":
        (
            "recomputed_weights"
            in verifier_source
            and
            "REFERENCE_PRIORITY_EFFECTIVE_WEIGHTS_MISMATCH"
            in verifier_source
        ),


    "VERIFIER_REBUILDS_DECISION":
        (
            "expected_decision"
            in verifier_source
            and
            "REFERENCE_PRIORITY_DECISION_SCORE_MISMATCH"
            in verifier_source
        ),


    "VERIFIER_REBUILDS_ID":
        (
            "expected_priority_decision_id"
            in verifier_source
            and
            '"RPD_"'
            in verifier_source
            and
            "REFERENCE_PRIORITY_DECISION_IDENTITY_MISMATCH"
            in verifier_source
        ),


    "CONTACT_PATH_CHECK":
        "contact_sheet_path"
        in mechanical_source,


    "CONTACT_PATH_BOUNDARY":
        (
            "_ensure_under("
            in mechanical_source
            and
            "CONTACTS"
            in mechanical_source
        ),


    "CONTACT_EXISTS_CHECK":
        ".exists()"
        in mechanical_source,


    "CONTACT_FILE_CHECK":
        ".is_file()"
        in mechanical_source,


    "CONTACT_SHA_PHYSICAL_CHECK":
        "sha256_file("
        in mechanical_source,


    "VISION_GUARD_PRESERVED":
        text.count(
            "_require_reference_priority_semantic_allowed("
        ) >= 2,


    "PRIORITY_CONTRACT_PRESERVED":
        "SM3_REFERENCE_PRIORITY_DECISION_V1"
        in text,


    "RMA_CONTRACT_PRESERVED":
        "SM3_REFERENCE_MECHANICAL_ANALYSIS_V1"
        in text,


    "MEDIA_ARTIFACT_PRESERVED":
        "SM3_REFERENCE_MEDIA_ARTIFACT_V1"
        in text,


    "CAS_PRESERVED":
        "SM3_REFERENCE_MEDIA_CAS_V1"
        in text,
}


for label,value in checks.items():

    print(
        f"{label}={value}"
    )


if False in checks.values():
    raise SystemExit(
        "SM3_09C6_B2F_STATIC_HARDENING_CHECK_FAILED"
    )


# ============================================================
# 6. ENSURE VISION CALL GRAPH IS STILL SINGLE-SITE
# ============================================================

tree=ast.parse(
    text
)


functions={
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


vision_callers=[]


for function_name,node in functions.items():

    for child in ast.walk(node):

        if not isinstance(
            child,
            ast.Call,
        ):
            continue

        func=child.func

        if (
            isinstance(
                func,
                ast.Name,
            )
            and
            func.id
            == "_reference_video_vision"
        ):
            vision_callers.append(
                function_name
            )


print(
    "VISION_CALLERS="
    f"{vision_callers}"
)


if vision_callers != [
    "production_reference_video_analysis"
]:
    raise SystemExit(
        "SM3_09C6_B2F_VISION_CALL_GRAPH_CHANGED"
    )


# ============================================================
# 7. BACKUP + ATOMIC INSTALL
# ============================================================

BACKUPS.mkdir(
    parents=True,
    exist_ok=True,
)


stamp=datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)


backup=(
    BACKUPS
    / (
        "worker_2_23_0_pre_09C6_B2_hardening_"
        + stamp
        + ".py"
    )
)


shutil.copy2(
    WORKER,
    backup,
)


encoded=text.encode(
    "utf-8"
)

if has_bom:
    encoded=(
        codecs.BOM_UTF8
        + encoded
    )


tmp=WORKER.with_name(
    WORKER.name
    + ".09C6_B2F.tmp"
)


tmp.write_bytes(
    encoded
)


tmp_raw=tmp.read_bytes()

tmp_text=tmp_raw

if tmp_text.startswith(
    codecs.BOM_UTF8
):
    tmp_text=tmp_text[
        len(codecs.BOM_UTF8):
    ]


compile(
    tmp_text.decode(
        "utf-8"
    ),
    str(WORKER),
    "exec",
)


os.replace(
    tmp,
    WORKER,
)


# ============================================================
# 8. FINAL PERSISTENCE VERIFY
# ============================================================

final_raw=WORKER.read_bytes()

after_sha=hashlib.sha256(
    final_raw
).hexdigest()


final_text=WORKER.read_text(
    encoding="utf-8-sig"
)


ast.parse(
    final_text
)

compile(
    final_text,
    str(WORKER),
    "exec",
)


if after_sha == before_sha:
    raise SystemExit(
        "SM3_09C6_B2F_SOURCE_UNCHANGED"
    )


if final_text.count(
    'WORKER_VERSION = "2.23.0"'
) != 1:
    raise SystemExit(
        "SM3_09C6_B2F_FINAL_VERSION_INVALID"
    )


print()
print(
    f"BACKUP={backup}"
)

print(
    f"BEFORE_SHA256={before_sha}"
)

print(
    f"AFTER_SHA256={after_sha}"
)

print(
    "WORKER_VERSION=2.23.0"
)

print(
    "CONTACT_SHEET_PHYSICAL_VERIFICATION=True"
)

print(
    "DECISION_IDENTITY_RECOMPUTED=True"
)

print(
    "EVIDENCE_FINGERPRINT_RECOMPUTED=True"
)

print(
    "PRIORITY_SCORE_RECOMPUTED=True"
)

print(
    "EFFECTIVE_WEIGHTS_RECOMPUTED=True"
)

print(
    "DECISION_FROM_SCORE_RECOMPUTED=True"
)

print(
    "VISION_CALL_GRAPH_CHANGED=False"
)

print(
    "CONTAINER_DEPLOYED=False"
)

print()

print(
    "SM3_09C6_B2F_PRIORITY_INTEGRITY_HARDENING_PASS"
)
