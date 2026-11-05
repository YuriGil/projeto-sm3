from pathlib import Path
from datetime import datetime
import hashlib
import shutil
import codecs
import ast
import os

ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")
WORKER = ROOT / "worker" / "worker_service.py"
BACKUPS = ROOT / "sm3_backups"

EXPECTED_BEFORE_SHA = (
    "6e699119f41fccabd9475b8fb833c22f"
    "53036005920a1fa5d6f93520bd7ae575"
)

if not WORKER.exists():
    raise SystemExit("SM3_09C6_B1_WORKER_NOT_FOUND")

raw = WORKER.read_bytes()

actual_before_sha = hashlib.sha256(raw).hexdigest()

print(f"BEFORE_SHA256={actual_before_sha}")

if actual_before_sha != EXPECTED_BEFORE_SHA:
    raise SystemExit(
        "SM3_09C6_B1_BASELINE_SHA_MISMATCH:"
        f"{actual_before_sha}"
    )

has_bom = raw.startswith(codecs.BOM_UTF8)

if has_bom:
    text = raw[len(codecs.BOM_UTF8):].decode("utf-8")
else:
    text = raw.decode("utf-8")

NL = "\r\n" if "\r\n" in text else "\n"


def once(old: str, new: str, label: str):
    global text

    count = text.count(old)

    print(f"{label}_ANCHOR_COUNT={count}")

    if count != 1:
        raise SystemExit(
            f"SM3_09C6_B1_{label}_ANCHOR_INVALID:{count}"
        )

    text = text.replace(old, new, 1)


# ============================================================
# PRECONDITIONS
# ============================================================

if text.count('WORKER_VERSION = "2.22.0"') != 1:
    raise SystemExit(
        "SM3_09C6_B1_EXPECTED_WORKER_2_22_0_NOT_FOUND"
    )

for forbidden in (
    "SM3_REFERENCE_PRIORITY_DECISION_V1",
    "SM3_REFERENCE_PRIORITY_ENGINE_V1",
    "ReferencePriorityDecisionRequest",
    "production_reference_priority_decision",
    "PRODUCTION_REFERENCE_PRIORITY_DECISIONS",
):
    if forbidden in text:
        raise SystemExit(
            f"SM3_09C6_B1_ALREADY_PATCHED:{forbidden}"
        )


# ============================================================
# 1. STORAGE ROOT
# ============================================================

storage_anchor = (
    'PRODUCTION_REFERENCE_MECHANICAL_ANALYSES = '
    '(PRODUCTION_STATE / "reference_mechanical_analyses").resolve()'
)

storage_replacement = (
    storage_anchor
    + NL
    + 'PRODUCTION_REFERENCE_PRIORITY_DECISIONS = '
      '(PRODUCTION_STATE / "reference_priority_decisions").resolve()'
)

once(
    storage_anchor,
    storage_replacement,
    "STORAGE_ROOT",
)


# ============================================================
# 2. STARTUP ROOT
#    Modify only the directory-init tuple.
# ============================================================

lines = text.splitlines(keepends=True)

startup_matches = []

for idx, line in enumerate(lines):
    if (
        line.lstrip().startswith("for p in (")
        and "PRODUCTION_REFERENCE_MECHANICAL_ANALYSES" in line
        and "p.mkdir" not in line
    ):
        startup_matches.append(idx)

print(
    "STARTUP_ROOT_LINE_MATCH_COUNT="
    f"{len(startup_matches)}"
)

if len(startup_matches) != 1:
    raise SystemExit(
        "SM3_09C6_B1_STARTUP_ROOT_LINE_INVALID:"
        f"{len(startup_matches)}"
    )

startup_idx = startup_matches[0]
startup_line = lines[startup_idx]

if "PRODUCTION_REFERENCE_PRIORITY_DECISIONS" in startup_line:
    raise SystemExit(
        "SM3_09C6_B1_PRIORITY_ROOT_ALREADY_IN_STARTUP"
    )

needle = "PRODUCTION_REFERENCE_MECHANICAL_ANALYSES,"

if startup_line.count(needle) != 1:
    raise SystemExit(
        "SM3_09C6_B1_STARTUP_MECHANICAL_ROOT_INVALID"
    )

lines[startup_idx] = startup_line.replace(
    needle,
    (
        "PRODUCTION_REFERENCE_MECHANICAL_ANALYSES, "
        "PRODUCTION_REFERENCE_PRIORITY_DECISIONS,"
    ),
    1,
)

text = "".join(lines)


# ============================================================
# 3. CONTRACTS + ENGINE CONSTANTS
# ============================================================

contract_anchor = (
    'REFERENCE_MECHANICAL_ANALYZER_VERSION = '
    '"SM3_REFERENCE_MECHANICAL_ANALYZER_V1"'
)

contract_block = NL.join([
    contract_anchor,
    'REFERENCE_PRIORITY_DECISION_CONTRACT_VERSION = '
    '"SM3_REFERENCE_PRIORITY_DECISION_V1"',
    'REFERENCE_PRIORITY_ENGINE_VERSION = '
    '"SM3_REFERENCE_PRIORITY_ENGINE_V1"',
    "REFERENCE_PRIORITY_SEMANTIC_THRESHOLD = 70.0",
    "REFERENCE_PRIORITY_DEFER_THRESHOLD = 40.0",
    "REFERENCE_PRIORITY_WEIGHT_HUMAN = 0.30",
    "REFERENCE_PRIORITY_WEIGHT_METRIC = 0.50",
    "REFERENCE_PRIORITY_WEIGHT_MECHANICAL = 0.20",
])

once(
    contract_anchor,
    contract_block,
    "CONTRACTS",
)


# ============================================================
# 4. WORKER VERSION
# ============================================================

once(
    'WORKER_VERSION = "2.22.0"',
    'WORKER_VERSION = "2.23.0"',
    "WORKER_VERSION",
)


# ============================================================
# 5. PRIORITY GATE IMPLEMENTATION
#    Insert immediately before provider routes.
# ============================================================

provider_anchor = (
    '@app.get("/production/reference-corpus/providers")'
)

priority_block = r'''
# ============================================================
# SM3 09C6 - REFERENCE PRIORITY GATE V1
# ============================================================

class ReferencePriorityDecisionRequest(BaseModel):
    reference_item_id: str
    acquisition_id: Optional[str] = None
    mechanical_analysis_id: Optional[str] = None
    use_latest_acquisition: bool = True


def _reference_priority_decision_dir(
    profile_id: str,
    item_id: str,
) -> Path:
    return _ensure_under(
        PRODUCTION_REFERENCE_PRIORITY_DECISIONS
        / _safe_component(profile_id)
        / _safe_component(item_id),
        PRODUCTION_REFERENCE_PRIORITY_DECISIONS,
    )


def _reference_priority_decision_path(
    profile_id: str,
    item_id: str,
    priority_decision_id: str,
) -> Path:
    return _ensure_under(
        _reference_priority_decision_dir(
            profile_id,
            item_id,
        )
        / f"{_safe_component(priority_decision_id)}.json",
        PRODUCTION_REFERENCE_PRIORITY_DECISIONS,
    )


def _verify_reference_priority_decision(
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

    pid=str(rec.get("priority_decision_id") or "")

    if not pid.startswith("RPD_"):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_ID_INVALID",
        )

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

    mechanical_hash=str(
        rec.get("mechanical_analysis_sha256") or ""
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

    evidence_fingerprint=str(
        rec.get("evidence_fingerprint") or ""
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

    if rec.get("eligibility") not in {
        "ELIGIBLE",
        "DEFERRED",
        "INELIGIBLE",
    }:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_ELIGIBILITY_INVALID",
        )

    if rec.get("decision") not in {
        "SEMANTIC_ANALYSIS",
        "DEFER",
        "SKIP",
    }:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_INVALID",
        )

    try:
        score=float(rec.get("priority_score"))
    except Exception:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_SCORE_INVALID",
        )

    if score < 0.0 or score > 100.0:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_SCORE_RANGE_INVALID",
        )

    semantic_allowed=bool(
        rec.get("semantic_analysis_allowed")
    )

    expected_semantic_allowed=(
        rec.get("eligibility") == "ELIGIBLE"
        and rec.get("decision") == "SEMANTIC_ANALYSIS"
    )

    if semantic_allowed != expected_semantic_allowed:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_SEMANTIC_ALLOW_INVALID",
        )

    if rec.get("model_call_used") is not False:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_MODEL_CALL_POLICY_INVALID",
        )

    if rec.get("copying_forbidden") is not True:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_COPYING_POLICY_INVALID",
        )

    if rec.get("foundation_override_allowed") is not False:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_FOUNDATION_POLICY_INVALID",
        )

    reasons=rec.get("reason_codes")

    if not isinstance(reasons,list) or not reasons:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_REASON_CODES_INVALID",
        )

    expected=str(
        rec.get("priority_decision_sha256") or ""
    ).lower()

    chk={
        k:v
        for k,v in rec.items()
        if k != "priority_decision_sha256"
    }

    if (
        len(expected) != 64
        or _canonical_sha256(chk) != expected
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_INTEGRITY_FAILED",
        )

    return rec


def _reference_priority_number(
    value: Any,
) -> Optional[float]:

    if value is None or isinstance(value,bool):
        return None

    try:
        number=float(value)
    except Exception:
        return None

    if number != number:
        return None

    if number in {
        float("inf"),
        float("-inf"),
    }:
        return None

    return number


def _reference_priority_metric_value(
    snapshot: dict[str,Any],
) -> tuple[Optional[str],Optional[float]]:

    engagement=_reference_priority_number(
        snapshot.get("engagement")
    )

    if engagement is not None:
        return "ENGAGEMENT", engagement

    interactions=_reference_priority_number(
        snapshot.get("interactions")
    )

    if interactions is not None:
        return "INTERACTIONS", interactions

    raw=snapshot.get("raw_metrics")

    if not isinstance(raw,dict):
        raw={}

    views=_reference_priority_number(
        raw.get("views")
    )

    if views is not None:
        return "VIEWS", views

    likes=_reference_priority_number(
        snapshot.get("likes")
    )

    comments=_reference_priority_number(
        snapshot.get("comments")
    )

    if likes is not None or comments is not None:
        return (
            "SOCIAL_INTERACTIONS",
            float(likes or 0.0) + float(comments or 0.0),
        )

    return None,None


def _reference_priority_latest_metric_snapshot(
    item_id: str,
) -> Optional[dict[str,Any]]:

    result=production_reference_metric_snapshots(
        item_id
    )

    snapshots=list(
        result.get("snapshots") or []
    )

    if not snapshots:
        return None

    return max(
        snapshots,
        key=lambda r:(
            str(r.get("captured_at") or ""),
            str(r.get("snapshot_id") or ""),
        ),
    )


def _reference_priority_metric_signal(
    item: dict[str,Any],
) -> dict[str,Any]:

    item_id=str(item["reference_item_id"])
    profile_id=str(item["reference_profile_id"])

    target=_reference_priority_latest_metric_snapshot(
        item_id
    )

    if target is None:
        return {
            "available":False,
            "score":None,
            "basis":None,
            "peer_count":0,
            "snapshot_id":None,
            "snapshot_sha256":None,
            "population_fingerprint":None,
        }

    basis,target_value=(
        _reference_priority_metric_value(target)
    )

    if basis is None or target_value is None:
        return {
            "available":False,
            "score":None,
            "basis":None,
            "peer_count":0,
            "snapshot_id":target.get("snapshot_id"),
            "snapshot_sha256":target.get(
                "snapshot_sha256"
            ),
            "population_fingerprint":None,
        }

    active_items=production_reference_items(
        profile_id,
        include_tombstoned=False,
    ).get("items") or []

    population=[]

    for peer in active_items:

        peer_id=str(
            peer.get("reference_item_id") or ""
        )

        if not peer_id:
            continue

        peer_snapshot=(
            _reference_priority_latest_metric_snapshot(
                peer_id
            )
        )

        if peer_snapshot is None:
            continue

        peer_basis,peer_value=(
            _reference_priority_metric_value(
                peer_snapshot
            )
        )

        if (
            peer_basis != basis
            or peer_value is None
        ):
            continue

        population.append({
            "reference_item_id":peer_id,
            "snapshot_id":peer_snapshot.get(
                "snapshot_id"
            ),
            "snapshot_sha256":peer_snapshot.get(
                "snapshot_sha256"
            ),
            "value":round(float(peer_value),8),
        })

    population.sort(
        key=lambda r:(
            str(r.get("reference_item_id") or ""),
            str(r.get("snapshot_id") or ""),
        )
    )

    population_fingerprint=(
        _canonical_sha256({
            "basis":basis,
            "members":population,
        })
        if population
        else None
    )

    peer_values=[
        float(r["value"])
        for r in population
    ]

    if len(peer_values) < 3:
        return {
            "available":False,
            "score":None,
            "basis":basis,
            "peer_count":len(peer_values),
            "snapshot_id":target.get("snapshot_id"),
            "snapshot_sha256":target.get(
                "snapshot_sha256"
            ),
            "population_fingerprint":
                population_fingerprint,
        }

    less=sum(
        1
        for value in peer_values
        if value < float(target_value)
    )

    equal=sum(
        1
        for value in peer_values
        if value == float(target_value)
    )

    percentile=100.0 * (
        float(less) + 0.5 * float(equal)
    ) / float(len(peer_values))

    percentile=max(
        0.0,
        min(100.0,percentile),
    )

    return {
        "available":True,
        "score":round(percentile,4),
        "basis":basis,
        "peer_count":len(peer_values),
        "snapshot_id":target.get("snapshot_id"),
        "snapshot_sha256":target.get(
            "snapshot_sha256"
        ),
        "population_fingerprint":
            population_fingerprint,
    }


def _reference_priority_mechanical_quality(
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
        min(100.0,confidence),
    )

    contact_sha=str(
        mechanical_analysis.get(
            "contact_sheet_sha256"
        ) or ""
    ).lower()

    contact_valid=(
        len(contact_sha) == 64
        and all(
            c in "0123456789abcdef"
            for c in contact_sha
        )
    )

    if not contact_valid:
        confidence=min(confidence,60.0)

    return round(confidence,4)


def _reference_priority_current_evidence(
    item: dict[str,Any],
    mechanical_analysis: dict[str,Any],
) -> dict[str,Any]:

    profile=_load_reference_profile(
        item["reference_profile_id"]
    )

    human_priority=max(
        0,
        min(
            100,
            int(profile.get("human_priority",50)),
        ),
    )

    metric_signal=_reference_priority_metric_signal(
        item
    )

    mechanical_quality=(
        _reference_priority_mechanical_quality(
            mechanical_analysis
        )
    )

    evidence={
        "reference_profile_id":
            item["reference_profile_id"],

        "human_priority":{
            "score":human_priority,
        },

        "metric_signal":metric_signal,

        "mechanical_evidence_quality":{
            "score":mechanical_quality,
            "mechanical_analysis_id":
                mechanical_analysis.get(
                    "mechanical_analysis_id"
                ),
            "mechanical_analysis_sha256":
                mechanical_analysis.get(
                    "mechanical_analysis_sha256"
                ),
        },
    }

    evidence["evidence_fingerprint"]=(
        _canonical_sha256(evidence)
    )

    return evidence


def _reference_priority_score(
    evidence: dict[str,Any],
) -> tuple[float,dict[str,float]]:

    human=float(
        evidence["human_priority"]["score"]
    )

    mechanical=float(
        evidence[
            "mechanical_evidence_quality"
        ]["score"]
    )

    metric_rec=evidence["metric_signal"]

    available={
        "human_priority":(
            human,
            REFERENCE_PRIORITY_WEIGHT_HUMAN,
        ),
        "mechanical_evidence_quality":(
            mechanical,
            REFERENCE_PRIORITY_WEIGHT_MECHANICAL,
        ),
    }

    if (
        metric_rec.get("available")
        and metric_rec.get("score") is not None
    ):
        available["metric_signal"]=(
            float(metric_rec["score"]),
            REFERENCE_PRIORITY_WEIGHT_METRIC,
        )

    weight_total=sum(
        weight
        for _,weight in available.values()
    )

    if weight_total <= 0:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_WEIGHT_TOTAL_INVALID",
        )

    effective_weights={}
    score=0.0

    for name,(value,weight) in available.items():

        normalized=float(weight)/float(
            weight_total
        )

        effective_weights[name]=round(
            normalized,
            6,
        )

        score += float(value) * normalized

    return (
        round(
            max(0.0,min(100.0,score)),
            4,
        ),
        effective_weights,
    )


def _reference_priority_decisions_for_item(
    item_id: str,
) -> list[dict[str,Any]]:

    item=_load_reference_item(item_id)

    d=_reference_priority_decision_dir(
        item["reference_profile_id"],
        item_id,
    )

    out=[]

    if d.exists():

        for p in sorted(d.glob("RPD_*.json")):

            rec=json.loads(
                p.read_text(encoding="utf-8")
            )

            out.append(
                _verify_reference_priority_decision(
                    rec
                )
            )

    out.sort(
        key=lambda r:(
            str(r.get("created_at") or ""),
            str(r.get("priority_decision_id") or ""),
        )
    )

    return out


def _reference_priority_current_mechanical(
    source_sha: str,
) -> dict[str,Any]:

    analysis_id=(
        "RMA_"
        + _canonical_sha256({
            "source_sha256":source_sha,
            "analyzer_version":
                REFERENCE_MECHANICAL_ANALYZER_VERSION,
        })[:32]
    )

    p=_reference_mechanical_analysis_path(
        source_sha,
        analysis_id,
    )

    if not p.exists():
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_MECHANICAL_ANALYSIS_REQUIRED",
        )

    rec=_verify_reference_mechanical_analysis(
        json.loads(
            p.read_text(encoding="utf-8")
        )
    )

    if (
        str(rec.get("source_sha256") or "").lower()
        != source_sha.lower()
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_MECHANICAL_SOURCE_MISMATCH",
        )

    return rec


def _require_reference_priority_semantic_allowed(
    item_id: str,
    source_sha: str,
) -> dict[str,Any]:

    item=_require_reference_item_active(
        item_id
    )

    source_sha=str(source_sha or "").lower()

    mechanical=(
        _reference_priority_current_mechanical(
            source_sha
        )
    )

    evidence=_reference_priority_current_evidence(
        item,
        mechanical,
    )

    current_fingerprint=evidence[
        "evidence_fingerprint"
    ]

    candidates=[
        rec
        for rec in
        _reference_priority_decisions_for_item(
            item_id
        )
        if (
            str(
                rec.get("source_sha256") or ""
            ).lower() == source_sha
            and rec.get("engine_version")
                == REFERENCE_PRIORITY_ENGINE_VERSION
            and rec.get(
                "mechanical_analysis_id"
            )
                == mechanical.get(
                    "mechanical_analysis_id"
                )
        )
    ]

    if not candidates:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_REQUIRED",
        )

    matching=[
        rec
        for rec in candidates
        if rec.get("evidence_fingerprint")
            == current_fingerprint
    ]

    if not matching:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_DECISION_STALE",
        )

    decision=max(
        matching,
        key=lambda r:(
            str(r.get("created_at") or ""),
            str(
                r.get("priority_decision_id")
                or ""
            ),
        ),
    )

    if not bool(
        decision.get(
            "semantic_analysis_allowed"
        )
    ):
        raise HTTPException(
            409,
            (
                "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED:"
                + str(
                    decision.get("decision")
                    or "UNKNOWN"
                )
            ),
        )

    return decision


@app.post(
    "/production/reference-corpus/priority-decision"
)
def production_reference_priority_decision(
    req: ReferencePriorityDecisionRequest,
):

    item=_require_reference_item_active(
        req.reference_item_id
    )

    if item.get("item_type") not in {
        "REEL",
        "VIDEO",
        "STORY",
    }:
        raise HTTPException(
            422,
            "REFERENCE_PRIORITY_ITEM_TYPE_NOT_VIDEO",
        )

    profile_id=item["reference_profile_id"]

    if req.acquisition_id:

        acquisition_path=_reference_media_path(
            profile_id,
            req.reference_item_id,
            req.acquisition_id,
        )

        if not acquisition_path.exists():
            raise HTTPException(
                404,
                "REFERENCE_MEDIA_ACQUISITION_NOT_FOUND",
            )

        acquisition=(
            _verify_reference_media_acquisition(
                json.loads(
                    acquisition_path.read_text(
                        encoding="utf-8"
                    )
                )
            )
        )

    else:

        if not req.use_latest_acquisition:
            raise HTTPException(
                422,
                "REFERENCE_PRIORITY_ACQUISITION_REQUIRED",
            )

        acquisition=(
            _latest_reference_media_for_item(
                req.reference_item_id
            )
        )

        if acquisition is None:
            raise HTTPException(
                404,
                "REFERENCE_MEDIA_ACQUISITION_NOT_FOUND",
            )

    if (
        acquisition.get("reference_item_id")
        != req.reference_item_id
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_ACQUISITION_ITEM_MISMATCH",
        )

    source=_resolve_reference_acquisition_source(
        acquisition
    )

    source_sha=sha256_file(source).lower()

    acquisition_sha=str(
        acquisition.get("source_sha256") or ""
    ).lower()

    if source_sha != acquisition_sha:
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_ACQUISITION_SHA_MISMATCH",
        )

    if req.mechanical_analysis_id:

        mechanical_id=str(
            req.mechanical_analysis_id
        ).strip()

    else:

        mechanical_id=(
            "RMA_"
            + _canonical_sha256({
                "source_sha256":source_sha,
                "analyzer_version":
                    REFERENCE_MECHANICAL_ANALYZER_VERSION,
            })[:32]
        )

    mechanical_path=(
        _reference_mechanical_analysis_path(
            source_sha,
            mechanical_id,
        )
    )

    if not mechanical_path.exists():
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_MECHANICAL_ANALYSIS_REQUIRED",
        )

    mechanical=(
        _verify_reference_mechanical_analysis(
            json.loads(
                mechanical_path.read_text(
                    encoding="utf-8"
                )
            )
        )
    )

    if (
        str(
            mechanical.get("source_sha256")
            or ""
        ).lower()
        != source_sha
    ):
        raise HTTPException(
            409,
            "REFERENCE_PRIORITY_MECHANICAL_SOURCE_MISMATCH",
        )

    evidence=_reference_priority_current_evidence(
        item,
        mechanical,
    )

    priority_score,effective_weights=(
        _reference_priority_score(
            evidence
        )
    )

    metric=evidence["metric_signal"]

    reason_codes=[
        "ITEM_ACTIVE",
        "ACQUISITION_VERIFIED",
        "SOURCE_SHA_VERIFIED",
        "MECHANICAL_ANALYSIS_AVAILABLE",
        "MECHANICAL_SOURCE_MATCH",
        "HUMAN_PRIORITY_APPLIED",
    ]

    if (
        float(
            evidence[
                "mechanical_evidence_quality"
            ]["score"]
        )
        >= 80.0
    ):
        reason_codes.append(
            "MECHANICAL_EVIDENCE_HIGH"
        )
    else:
        reason_codes.append(
            "MECHANICAL_EVIDENCE_PARTIAL"
        )

    if metric.get("available"):
        reason_codes.append(
            "METRIC_SIGNAL_AVAILABLE"
        )
    else:
        reason_codes.append(
            "METRIC_SIGNAL_UNAVAILABLE"
        )

    if (
        priority_score
        >= REFERENCE_PRIORITY_SEMANTIC_THRESHOLD
    ):
        decision="SEMANTIC_ANALYSIS"

        reason_codes.append(
            "PRIORITY_ABOVE_SEMANTIC_THRESHOLD"
        )

    elif (
        priority_score
        >= REFERENCE_PRIORITY_DEFER_THRESHOLD
    ):
        decision="DEFER"

        reason_codes.append(
            "PRIORITY_IN_DEFER_RANGE"
        )

    else:
        decision="SKIP"

        reason_codes.append(
            "PRIORITY_BELOW_SKIP_THRESHOLD"
        )

    eligibility="ELIGIBLE"

    semantic_allowed=(
        decision == "SEMANTIC_ANALYSIS"
    )

    evidence_fingerprint=evidence[
        "evidence_fingerprint"
    ]

    identity={
        "reference_item_id":
            req.reference_item_id,

        "source_sha256":
            source_sha,

        "mechanical_analysis_id":
            mechanical.get(
                "mechanical_analysis_id"
            ),

        "mechanical_analysis_sha256":
            mechanical.get(
                "mechanical_analysis_sha256"
            ),

        "evidence_fingerprint":
            evidence_fingerprint,

        "priority_engine_version":
            REFERENCE_PRIORITY_ENGINE_VERSION,
    }

    priority_decision_id=(
        "RPD_"
        + _canonical_sha256(identity)[:32]
    )

    path=_reference_priority_decision_path(
        profile_id,
        req.reference_item_id,
        priority_decision_id,
    )

    if path.exists():

        old=_verify_reference_priority_decision(
            json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        )

        return {
            "ok":True,
            "reused_existing":True,
            "priority_decision":old,
        }

    rec={
        "ok":True,

        "priority_decision_id":
            priority_decision_id,

        "contract_version":
            REFERENCE_PRIORITY_DECISION_CONTRACT_VERSION,

        "engine_version":
            REFERENCE_PRIORITY_ENGINE_VERSION,

        "reference_item_id":
            req.reference_item_id,

        "reference_profile_id":
            profile_id,

        "acquisition_id":
            acquisition.get(
                "acquisition_id"
            ),

        "acquisition_contract_version":
            acquisition.get(
                "contract_version"
            ),

        "media_artifact_id":
            acquisition.get(
                "media_artifact_id"
            ),

        "source_sha256":
            source_sha,

        "mechanical_analysis_id":
            mechanical.get(
                "mechanical_analysis_id"
            ),

        "mechanical_analysis_sha256":
            mechanical.get(
                "mechanical_analysis_sha256"
            ),

        "evidence_fingerprint":
            evidence_fingerprint,

        "eligibility":
            eligibility,

        "decision":
            decision,

        "priority_score":
            priority_score,

        "components":{
            "human_priority":
                evidence["human_priority"],

            "metric_signal":
                metric,

            "mechanical_evidence_quality":
                evidence[
                    "mechanical_evidence_quality"
                ],
        },

        "effective_weights":
            effective_weights,

        "thresholds":{
            "semantic_analysis":
                REFERENCE_PRIORITY_SEMANTIC_THRESHOLD,

            "defer":
                REFERENCE_PRIORITY_DEFER_THRESHOLD,
        },

        "reason_codes":
            reason_codes,

        "semantic_analysis_allowed":
            semantic_allowed,

        "model_call_used":
            False,

        "novelty_score":
            None,

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "copying_forbidden":
            True,

        "foundation_override_allowed":
            False,
    }

    rec["priority_decision_sha256"]=(
        _canonical_sha256(rec)
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    _write_revision_once(
        path,
        rec,
    )

    persisted=(
        _verify_reference_priority_decision(
            json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        )
    )

    return {
        "ok":True,
        "reused_existing":False,
        "priority_decision":persisted,
    }


@app.get(
    "/production/reference-corpus/item/{item_id}/priority-decisions"
)
def production_reference_priority_decisions(
    item_id: str,
):

    records=(
        _reference_priority_decisions_for_item(
            item_id
        )
    )

    return {
        "ok":True,

        "contract_version":
            REFERENCE_PRIORITY_DECISION_CONTRACT_VERSION,

        "engine_version":
            REFERENCE_PRIORITY_ENGINE_VERSION,

        "reference_item_id":
            item_id,

        "count":
            len(records),

        "priority_decisions":
            records,
    }


@app.get(
    "/production/reference-corpus/item/{item_id}/priority-decision/latest"
)
def production_reference_priority_decision_latest(
    item_id: str,
):

    records=(
        _reference_priority_decisions_for_item(
            item_id
        )
    )

    if not records:
        raise HTTPException(
            404,
            "REFERENCE_PRIORITY_DECISION_NOT_FOUND",
        )

    rec=max(
        records,
        key=lambda r:(
            str(r.get("created_at") or ""),
            str(
                r.get("priority_decision_id")
                or ""
            ),
        ),
    )

    return {
        "ok":True,
        "priority_decision":rec,
    }


# ============================================================
# END SM3 09C6 PRIORITY GATE V1
# ============================================================

'''.replace("\n", NL)

once(
    provider_anchor,
    priority_block + provider_anchor,
    "PRIORITY_BLOCK",
)


# ============================================================
# 6. FAIL-CLOSED VISION ENFORCEMENT
#
# Cached historical RVA may still be read without a new model
# call. Any NEW call that would reach Vision must pass current
# PriorityDecision evidence.
# ============================================================

lines = text.splitlines(keepends=True)

vision_work_matches=[]

for idx,line in enumerate(lines):

    if (
        'work=_ensure_under(' in line
        and 'CONTACTS/"reference_video_analysis"' in line
    ):
        vision_work_matches.append(idx)

print(
    "VISION_WORK_ANCHOR_COUNT="
    f"{len(vision_work_matches)}"
)

if len(vision_work_matches) != 1:
    raise SystemExit(
        "SM3_09C6_B1_VISION_WORK_ANCHOR_INVALID:"
        f"{len(vision_work_matches)}"
    )

vision_idx=vision_work_matches[0]

guard_lines = [
    "    _require_reference_priority_semantic_allowed(" + NL,
    "        req.reference_item_id," + NL,
    "        source_sha," + NL,
    "    )" + NL,
]

lines[vision_idx:vision_idx] = guard_lines

text="".join(lines)


# ============================================================
# 7. HEALTH CAPABILITIES
# ============================================================

health_anchor = (
    '        "reference_video_learning_priority": True,'
)

health_block = NL.join([
    '        "reference_priority_gate": True,',
    '        "reference_priority_decision_contract": '
    'REFERENCE_PRIORITY_DECISION_CONTRACT_VERSION,',
    '        "reference_priority_engine_version": '
    'REFERENCE_PRIORITY_ENGINE_VERSION,',
    '        "reference_priority_engine_deterministic": True,',
    '        "reference_priority_engine_model_call": False,',
    '        "reference_priority_semantic_fail_closed": True,',
    '        "reference_priority_novelty_v1": False,',
    health_anchor,
])

once(
    health_anchor,
    health_block,
    "HEALTH",
)


# ============================================================
# 8. STATIC ARCHITECTURE ASSERTIONS
# ============================================================

required_markers = {
    "VERSION":
        'WORKER_VERSION = "2.23.0"',

    "STORAGE":
        'PRODUCTION_REFERENCE_PRIORITY_DECISIONS = '
        '(PRODUCTION_STATE / "reference_priority_decisions").resolve()',

    "CONTRACT":
        'SM3_REFERENCE_PRIORITY_DECISION_V1',

    "ENGINE":
        'SM3_REFERENCE_PRIORITY_ENGINE_V1',

    "REQUEST_MODEL":
        'class ReferencePriorityDecisionRequest(BaseModel):',

    "VERIFIER":
        'def _verify_reference_priority_decision(',

    "EVIDENCE":
        'def _reference_priority_current_evidence(',

    "SCORER":
        'def _reference_priority_score(',

    "SEMANTIC_GATE":
        'def _require_reference_priority_semantic_allowed(',

    "POST_ROUTE":
        '"/production/reference-corpus/priority-decision"',

    "LIST_ROUTE":
        '"/production/reference-corpus/item/{item_id}/priority-decisions"',

    "LATEST_ROUTE":
        '"/production/reference-corpus/item/{item_id}/priority-decision/latest"',

    "VISION_GUARD_CALL":
        '_require_reference_priority_semantic_allowed(',

    "NO_NOVELTY_IMPLEMENTATION":
        '"novelty_score":',

    "MODEL_CALL_FALSE":
        '"model_call_used":',

    "FAIL_CLOSED_HEALTH":
        '"reference_priority_semantic_fail_closed": True',
}

for label,marker in required_markers.items():

    count=text.count(marker)

    print(f"{label}_COUNT={count}")

    if count < 1:
        raise SystemExit(
            f"SM3_09C6_B1_REQUIRED_MARKER_MISSING:{label}"
        )


if (
    text.count(
        'WORKER_VERSION = "2.23.0"'
    ) != 1
):
    raise SystemExit(
        "SM3_09C6_B1_VERSION_COUNT_INVALID"
    )


if (
    "PRODUCTION_REFERENCE_PRIORITY_DECISIONS"
    not in next(
        line
        for line in text.splitlines()
        if line.lstrip().startswith("for p in (")
    )
):
    raise SystemExit(
        "SM3_09C6_B1_PRIORITY_ROOT_NOT_IN_STARTUP"
    )


# Priority block must not call model/provider.
block_start=text.index(
    "# SM3 09C6 - REFERENCE PRIORITY GATE V1"
)

block_end=text.index(
    "# END SM3 09C6 PRIORITY GATE V1"
)

priority_source=text[
    block_start:block_end
]

for forbidden in (
    "httpx.",
    "OPENAI_API_KEY",
    "VISION_MODEL",
    "_reference_video_vision(",
):
    if forbidden in priority_source:
        raise SystemExit(
            "SM3_09C6_B1_PRIORITY_ENGINE_MODEL_COUPLING:"
            f"{forbidden}"
        )


# Vision call still exists, but only after the gate.
video_start=text.index(
    'def production_reference_video_analysis('
)

video_end=text.index(
    '@app.get("/production/reference-corpus/video-analysis/{item_id}/latest")'
)

video_source=text[
    video_start:video_end
]

guard_pos=video_source.find(
    "_require_reference_priority_semantic_allowed("
)

vision_pos=video_source.find(
    "_reference_video_vision("
)

print(f"VIDEO_GUARD_POSITION={guard_pos}")
print(f"VIDEO_VISION_POSITION={vision_pos}")

if guard_pos < 0:
    raise SystemExit(
        "SM3_09C6_B1_VIDEO_GATE_MISSING"
    )

if vision_pos < 0:
    raise SystemExit(
        "SM3_09C6_B1_VIDEO_VISION_CALL_MISSING"
    )

if guard_pos >= vision_pos:
    raise SystemExit(
        "SM3_09C6_B1_VIDEO_GATE_AFTER_VISION"
    )


# Mechanical identity must remain media-centric.
#
# Normalize whitespace and quote style before checking because
# the canonical RMA identity is intentionally formatted across
# multiple source lines.
mechanical_start = text.index(
    "def production_reference_mechanical_analysis("
)

mechanical_end = text.index(
    '@app.post("/production/reference-corpus/video-analysis")',
    mechanical_start,
)

mechanical_source = text[
    mechanical_start:mechanical_end
]

mechanical_compact = "".join(
    mechanical_source.split()
).replace('"', "'")

mechanical_identity_marker = (
    "analysis_id='RMA_'+_canonical_sha256({"
    "'source_sha256':source_sha,"
    "'analyzer_version':REFERENCE_MECHANICAL_ANALYZER_VERSION,"
    "})[:32]"
)

print(
    "RMA_MEDIA_CENTRIC_IDENTITY_PRESENT="
    f"{mechanical_identity_marker in mechanical_compact}"
)

if mechanical_identity_marker not in mechanical_compact:
    raise SystemExit(
        "SM3_09C6_B1_RMA_IDENTITY_CHANGED"
    )


# Existing MediaArtifact architecture must remain.
for marker in (
    "SM3_REFERENCE_MEDIA_ARTIFACT_V1",
    "SM3_REFERENCE_MEDIA_CAS_V1",
    "SM3_REFERENCE_MEDIA_ACQUISITION_V2",
):
    if marker not in text:
        raise SystemExit(
            "SM3_09C6_B1_09C5_ARCHITECTURE_MISSING:"
            f"{marker}"
        )


# ============================================================
# 9. PYTHON SYNTAX GATE BEFORE TOUCHING HOST SOURCE
# ============================================================

ast.parse(text)

compile(
    text,
    str(WORKER),
    "exec",
)

print("PYTHON_SYNTAX=PASS")


# ============================================================
# 10. BACKUP + ATOMIC SOURCE REPLACEMENT
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
        "worker_2_22_0_pre_09C6_priority_gate_"
        + stamp
        + ".py"
    )
)

shutil.copy2(
    WORKER,
    backup,
)


encoded=text.encode("utf-8")

if has_bom:
    encoded=codecs.BOM_UTF8 + encoded

tmp=WORKER.with_name(
    WORKER.name
    + ".09C6_B1.tmp"
)

tmp.write_bytes(encoded)

written=tmp.read_bytes()

if hashlib.sha256(written).hexdigest() == actual_before_sha:
    raise SystemExit(
        "SM3_09C6_B1_PATCH_DID_NOT_CHANGE_SOURCE"
    )

# Compile exactly what will be installed.
written_text=written

if written_text.startswith(codecs.BOM_UTF8):
    written_text=written_text[len(codecs.BOM_UTF8):]

compile(
    written_text.decode("utf-8"),
    str(WORKER),
    "exec",
)

os.replace(
    tmp,
    WORKER,
)


# ============================================================
# 11. FINAL VERIFY
# ============================================================

final_raw=WORKER.read_bytes()

final_sha=hashlib.sha256(
    final_raw
).hexdigest()

final_text=WORKER.read_text(
    encoding="utf-8-sig"
)

ast.parse(final_text)

compile(
    final_text,
    str(WORKER),
    "exec",
)

final_checks = {
    "VERSION_2_23":
        final_text.count(
            'WORKER_VERSION = "2.23.0"'
        ) == 1,

    "PRIORITY_CONTRACT":
        final_text.count(
            "SM3_REFERENCE_PRIORITY_DECISION_V1"
        ) >= 1,

    "PRIORITY_ENGINE":
        final_text.count(
            "SM3_REFERENCE_PRIORITY_ENGINE_V1"
        ) >= 1,

    "PRIORITY_POST":
        final_text.count(
            '"/production/reference-corpus/priority-decision"'
        ) == 1,

    "PRIORITY_LIST":
        final_text.count(
            '"/production/reference-corpus/item/{item_id}/priority-decisions"'
        ) == 1,

    "PRIORITY_LATEST":
        final_text.count(
            '"/production/reference-corpus/item/{item_id}/priority-decision/latest"'
        ) == 1,

    "VISION_FAIL_CLOSED":
        final_text.count(
            "_require_reference_priority_semantic_allowed("
        ) >= 2,

    "MEDIA_ARTIFACT_PRESERVED":
        "SM3_REFERENCE_MEDIA_ARTIFACT_V1"
        in final_text,

    "RMA_PRESERVED":
        "SM3_REFERENCE_MECHANICAL_ANALYSIS_V1"
        in final_text,
}

for label,value in final_checks.items():
    print(f"FINAL_{label}={value}")

if False in final_checks.values():
    raise SystemExit(
        "SM3_09C6_B1_FINAL_STATIC_CHECK_FAILED"
    )


print()
print(f"BACKUP={backup}")
print(f"BEFORE_SHA256={actual_before_sha}")
print(f"AFTER_SHA256={final_sha}")
print("NEW_VERSION=2.23.0")
print(
    "PRIORITY_CONTRACT="
    "SM3_REFERENCE_PRIORITY_DECISION_V1"
)
print(
    "PRIORITY_ENGINE="
    "SM3_REFERENCE_PRIORITY_ENGINE_V1"
)
print("VISION_FAIL_CLOSED=True")
print("PRIORITY_ENGINE_MODEL_CALL=False")
print("NOVELTY_IMPLEMENTED_V1=False")
print("RMA_IDENTITY_CHANGED=False")
print("MEDIA_ARTIFACT_ARCHITECTURE_CHANGED=False")
print()
print(
    "SM3_09C6_B1_PRIORITY_GATE_SOURCE_PATCH_PASS"
)
