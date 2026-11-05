from pathlib import Path
import ast
import hashlib
import json
import re
import sys

ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = ROOT / "worker" / "worker_service.py"

REPORT = (
    ROOT
    / "reports"
    / "09C6"
    / "SM3_09C6_B2_PRIORITY_STATIC_GATE.json"
)

EXPECTED_SHA = (
    "227ecf9eefcdb020f1da6917a30d3271"
    "7d8f10d7addc2d615d044b4ef7ce39d7"
)


# ============================================================
# LOAD
# ============================================================

if not WORKER.exists():
    raise SystemExit(
        "SM3_09C6_B2_WORKER_NOT_FOUND"
    )

raw = WORKER.read_bytes()

source_sha = hashlib.sha256(
    raw
).hexdigest()

text = WORKER.read_text(
    encoding="utf-8-sig"
)

lines = text.splitlines()

tree = ast.parse(
    text,
    filename=str(WORKER),
)

compile(
    text,
    str(WORKER),
    "exec",
)


# ============================================================
# INDEX
# ============================================================

functions = {
    node.name: node
    for node in tree.body
    if isinstance(
        node,
        (ast.FunctionDef, ast.AsyncFunctionDef),
    )
}

classes = {
    node.name: node
    for node in tree.body
    if isinstance(node, ast.ClassDef)
}


def node_source(node):
    if node is None:
        return ""

    start = int(node.lineno) - 1
    end = int(
        getattr(
            node,
            "end_lineno",
            node.lineno,
        )
    )

    return "\n".join(
        lines[start:end]
    )


def compact(value):
    return "".join(
        str(value).split()
    ).replace('"', "'")


def call_name(call):
    func = call.func

    if isinstance(func, ast.Name):
        return func.id

    if isinstance(func, ast.Attribute):
        parts = [func.attr]
        value = func.value

        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value

        if isinstance(value, ast.Name):
            parts.append(value.id)

        return ".".join(
            reversed(parts)
        )

    return ""


def calls_in(function_name):
    node = functions.get(
        function_name
    )

    if node is None:
        return []

    return [
        n
        for n in ast.walk(node)
        if isinstance(n, ast.Call)
    ]


def called(function_name, target):
    return any(
        call_name(call) == target
        for call in calls_in(
            function_name
        )
    )


# ------------------------------------------------------------
# Top-level constants
# ------------------------------------------------------------

constants = {}

for node in tree.body:

    if isinstance(node, ast.Assign):

        if len(node.targets) != 1:
            continue

        target = node.targets[0]

        if not isinstance(
            target,
            ast.Name,
        ):
            continue

        try:
            constants[target.id] = (
                ast.literal_eval(
                    node.value
                )
            )
        except Exception:
            pass

    if isinstance(
        node,
        ast.AnnAssign,
    ):

        target = node.target

        if not isinstance(
            target,
            ast.Name,
        ):
            continue

        try:
            constants[target.id] = (
                ast.literal_eval(
                    node.value
                )
            )
        except Exception:
            pass


# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------

routes = set()

for function_name,node in functions.items():

    for decorator in node.decorator_list:

        if not isinstance(
            decorator,
            ast.Call,
        ):
            continue

        if not isinstance(
            decorator.func,
            ast.Attribute,
        ):
            continue

        owner = decorator.func.value

        if not (
            isinstance(owner,ast.Name)
            and owner.id == "app"
        ):
            continue

        if not decorator.args:
            continue

        first = decorator.args[0]

        if not (
            isinstance(first,ast.Constant)
            and isinstance(first.value,str)
        ):
            continue

        routes.add(
            (
                decorator.func.attr.lower(),
                first.value,
                function_name,
            )
        )


# ============================================================
# CHECK FRAMEWORK
# ============================================================

checks = []


def check(name, value, detail=""):

    checks.append({
        "check": name,
        "pass": bool(value),
        "detail": str(detail),
    })


# ============================================================
# A. SOURCE IDENTITY / SYNTAX
# ============================================================

check(
    "SOURCE_SHA_MATCH_B1",
    source_sha == EXPECTED_SHA,
    source_sha,
)

check(
    "WORKER_VERSION_2_23",
    constants.get(
        "WORKER_VERSION"
    ) == "2.23.0",
    constants.get(
        "WORKER_VERSION"
    ),
)

check(
    "PRIORITY_ROOT_DEFINED",
    (
        'PRODUCTION_REFERENCE_PRIORITY_DECISIONS = '
        '(PRODUCTION_STATE / "reference_priority_decisions").resolve()'
        in text
    ),
)

startup_lines = [
    line
    for line in lines
    if line.lstrip().startswith(
        "for p in ("
    )
]

check(
    "ONE_STARTUP_ROOT_TUPLE",
    len(startup_lines) == 1,
    len(startup_lines),
)

check(
    "PRIORITY_ROOT_IN_STARTUP",
    (
        len(startup_lines) == 1
        and
        "PRODUCTION_REFERENCE_PRIORITY_DECISIONS"
        in startup_lines[0]
    ),
)


# ============================================================
# B. CONTRACTS / ENGINE CONFIG
# ============================================================

check(
    "PRIORITY_CONTRACT_V1",
    constants.get(
        "REFERENCE_PRIORITY_DECISION_CONTRACT_VERSION"
    )
    == "SM3_REFERENCE_PRIORITY_DECISION_V1",
)

check(
    "PRIORITY_ENGINE_V1",
    constants.get(
        "REFERENCE_PRIORITY_ENGINE_VERSION"
    )
    == "SM3_REFERENCE_PRIORITY_ENGINE_V1",
)

check(
    "SEMANTIC_THRESHOLD_70",
    constants.get(
        "REFERENCE_PRIORITY_SEMANTIC_THRESHOLD"
    ) == 70.0,
)

check(
    "DEFER_THRESHOLD_40",
    constants.get(
        "REFERENCE_PRIORITY_DEFER_THRESHOLD"
    ) == 40.0,
)

check(
    "HUMAN_WEIGHT_030",
    constants.get(
        "REFERENCE_PRIORITY_WEIGHT_HUMAN"
    ) == 0.30,
)

check(
    "METRIC_WEIGHT_050",
    constants.get(
        "REFERENCE_PRIORITY_WEIGHT_METRIC"
    ) == 0.50,
)

check(
    "MECHANICAL_WEIGHT_020",
    constants.get(
        "REFERENCE_PRIORITY_WEIGHT_MECHANICAL"
    ) == 0.20,
)


# ============================================================
# C. REQUEST MODEL
# ============================================================

request_model = classes.get(
    "ReferencePriorityDecisionRequest"
)

check(
    "REQUEST_MODEL_EXISTS",
    request_model is not None,
)

request_fields = set()

if request_model is not None:

    for node in request_model.body:

        if isinstance(
            node,
            ast.AnnAssign,
        ):

            if isinstance(
                node.target,
                ast.Name,
            ):

                request_fields.add(
                    node.target.id
                )


for field in (
    "reference_item_id",
    "acquisition_id",
    "mechanical_analysis_id",
    "use_latest_acquisition",
):

    check(
        "REQUEST_FIELD_"
        + field.upper(),
        field in request_fields,
    )


# ============================================================
# D. REQUIRED HELPERS
# ============================================================

required_functions = (
    "_reference_priority_decision_dir",
    "_reference_priority_decision_path",
    "_verify_reference_priority_decision",
    "_reference_priority_number",
    "_reference_priority_metric_value",
    "_reference_priority_latest_metric_snapshot",
    "_reference_priority_metric_signal",
    "_reference_priority_mechanical_quality",
    "_reference_priority_current_evidence",
    "_reference_priority_score",
    "_reference_priority_decisions_for_item",
    "_reference_priority_current_mechanical",
    "_require_reference_priority_semantic_allowed",
    "production_reference_priority_decision",
    "production_reference_priority_decisions",
    "production_reference_priority_decision_latest",
)

for function_name in required_functions:

    check(
        "FUNCTION_"
        + function_name.upper(),
        function_name in functions,
    )


# ============================================================
# E. ROUTES
# ============================================================

check(
    "ROUTE_PRIORITY_POST",
    (
        "post",
        "/production/reference-corpus/priority-decision",
        "production_reference_priority_decision",
    )
    in routes,
)

check(
    "ROUTE_PRIORITY_LIST_GET",
    (
        "get",
        "/production/reference-corpus/item/{item_id}/priority-decisions",
        "production_reference_priority_decisions",
    )
    in routes,
)

check(
    "ROUTE_PRIORITY_LATEST_GET",
    (
        "get",
        "/production/reference-corpus/item/{item_id}/priority-decision/latest",
        "production_reference_priority_decision_latest",
    )
    in routes,
)


# ============================================================
# F. PRIORITY ENGINE BOUNDARY
# ============================================================

priority_start = text.find(
    "# SM3 09C6 - REFERENCE PRIORITY GATE V1"
)

priority_end = text.find(
    "# END SM3 09C6 PRIORITY GATE V1"
)

priority_block = ""

if (
    priority_start >= 0
    and priority_end > priority_start
):
    priority_block = text[
        priority_start:priority_end
    ]


check(
    "PRIORITY_BLOCK_FOUND",
    bool(priority_block),
)


for forbidden in (
    "_reference_video_vision(",
    "OPENAI_API_KEY",
    "VISION_MODEL",
    "httpx.",
    "production_reference_feature(",
    "ReferenceFeatureObservationRequest(",
    "production_reference_metric_snapshot(",
    "make_contact_sheet(",
    "_reference_cut_metrics(",
    "_reference_audio_onsets(",
):

    check(
        "ENGINE_BOUNDARY_NO_"
        + re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            forbidden,
        ).strip("_").upper(),
        forbidden not in priority_block,
        forbidden,
    )


check(
    "ENGINE_NO_PREFERENCE_SIGNAL",
    "preference_signal"
    not in priority_block,
)


check(
    "ENGINE_NO_PROVIDER_EXECUTION_STATE",
    (
        "_provider_available("
        not in priority_block
        and
        "_provider_state("
        not in priority_block
    ),
)


# ============================================================
# G. EVALUATION ENDPOINT PRECONDITIONS
# ============================================================

eval_src = node_source(
    functions.get(
        "production_reference_priority_decision"
    )
)

check(
    "EVALUATION_REQUIRES_ACTIVE_ITEM",
    "_require_reference_item_active("
    in eval_src,
)

check(
    "EVALUATION_VERIFIES_ACQUISITION",
    "_verify_reference_media_acquisition("
    in eval_src,
)

check(
    "EVALUATION_USES_DUAL_SOURCE_RESOLVER",
    "_resolve_reference_acquisition_source("
    in eval_src,
)

check(
    "EVALUATION_HASHES_REAL_SOURCE",
    "sha256_file(source)"
    in eval_src,
)

check(
    "EVALUATION_CHECKS_ACQUISITION_SHA",
    "REFERENCE_PRIORITY_ACQUISITION_SHA_MISMATCH"
    in eval_src,
)

check(
    "EVALUATION_VERIFIES_MECHANICAL",
    "_verify_reference_mechanical_analysis("
    in eval_src,
)

check(
    "EVALUATION_CHECKS_MECHANICAL_SOURCE",
    "REFERENCE_PRIORITY_MECHANICAL_SOURCE_MISMATCH"
    in eval_src,
)


# ============================================================
# H. EVIDENCE SOURCES
# ============================================================

evidence_src = node_source(
    functions.get(
        "_reference_priority_current_evidence"
    )
)

check(
    "HUMAN_PRIORITY_FROM_PROFILE",
    (
        "_load_reference_profile("
        in evidence_src
        and
        "profile.get('human_priority',50)"
        in compact(evidence_src)
    ),
)


metric_src = node_source(
    functions.get(
        "_reference_priority_metric_signal"
    )
)

check(
    "METRIC_PROFILE_RELATIVE_POPULATION",
    "production_reference_items("
    in metric_src,
)

check(
    "METRIC_ACTIVE_POPULATION_ONLY",
    "include_tombstoned=False"
    in compact(metric_src),
)

check(
    "METRIC_REQUIRES_MINIMUM_POPULATION",
    "len(peer_values)<3"
    in compact(metric_src),
)

check(
    "METRIC_POPULATION_FINGERPRINT",
    "population_fingerprint"
    in metric_src,
)

check(
    "METRIC_PERCENTILE_CALCULATION",
    (
        "less=sum("
        in compact(metric_src)
        and
        "equal=sum("
        in compact(metric_src)
        and
        "percentile=100.0*("
        in compact(metric_src)
    ),
)


mechanical_quality_src = node_source(
    functions.get(
        "_reference_priority_mechanical_quality"
    )
)

check(
    "MECHANICAL_QUALITY_USES_CONFIDENCE",
    "mechanical_confidence"
    in mechanical_quality_src,
)


# Stronger independent invariant:
# a contact sheet cannot count as verified merely because a
# 64-character hash string exists. The file itself must be
# inspected before treating that evidence as reliable.

contact_physical_verify = (
    "contact_sheet_path"
    in mechanical_quality_src
    and
    "Path("
    in mechanical_quality_src
    and
    ".exists("
    in mechanical_quality_src
    and
    "sha256_file("
    in mechanical_quality_src
)

check(
    "MECHANICAL_CONTACT_SHEET_PHYSICALLY_VERIFIED",
    contact_physical_verify,
)


# ============================================================
# I. SCORE / RENORMALIZATION / DECISIONS
# ============================================================

score_src = node_source(
    functions.get(
        "_reference_priority_score"
    )
)

score_compact = compact(
    score_src
)

check(
    "SCORE_RENORMALIZES_AVAILABLE_WEIGHTS",
    (
        "weight_total=sum("
        in score_compact
        and
        "normalized=float(weight)/float(weight_total)"
        in score_compact
    ),
)

check(
    "MISSING_METRIC_NOT_FORCED",
    (
        'if(metric_rec.get("available")'
        in score_compact
        or
        "if(metric_rec.get('available')"
        in score_compact
    ),
)

check(
    "SCORE_CLAMPED_0_100",
    (
        "max(0.0,min(100.0,score))"
        in score_compact
    ),
)

eval_compact = compact(
    eval_src
)

check(
    "SEMANTIC_THRESHOLD_USED",
    "REFERENCE_PRIORITY_SEMANTIC_THRESHOLD"
    in eval_src,
)

check(
    "DEFER_THRESHOLD_USED",
    "REFERENCE_PRIORITY_DEFER_THRESHOLD"
    in eval_src,
)

check(
    "DECISION_SEMANTIC_EXISTS",
    "SEMANTIC_ANALYSIS"
    in eval_src,
)

check(
    "DECISION_DEFER_EXISTS",
    '"DEFER"'
    in eval_src
    or "'DEFER'"
    in eval_src,
)

check(
    "DECISION_SKIP_EXISTS",
    '"SKIP"'
    in eval_src
    or "'SKIP'"
    in eval_src,
)

check(
    "REASON_CODES_PERSISTED",
    "reason_codes"
    in eval_src,
)

check(
    "NO_NOVELTY_SCORE_V1",
    (
        '"novelty_score":'
        in eval_compact
        or
        "'novelty_score':"
        in eval_compact
    )
    and
    (
        '"novelty_score":None'
        in eval_compact
        or
        "'novelty_score':None"
        in eval_compact
    ),
)

check(
    "MODEL_CALL_USED_FALSE",
    (
        '"model_call_used":False'
        in eval_compact
        or
        "'model_call_used':False"
        in eval_compact
    ),
)


# ============================================================
# J. IMMUTABILITY / IDENTITY
# ============================================================

path_exists_pos = eval_src.find(
    "if path.exists()"
)

write_once_pos = eval_src.find(
    "_write_revision_once("
)

check(
    "IMMUTABLE_REUSE_BEFORE_WRITE",
    (
        path_exists_pos >= 0
        and write_once_pos >= 0
        and path_exists_pos < write_once_pos
    ),
)


identity_start = eval_src.find(
    "identity={"
)

identity_end = eval_src.find(
    "priority_decision_id=(",
    identity_start,
)

identity_src = ""

if (
    identity_start >= 0
    and identity_end > identity_start
):
    identity_src = eval_src[
        identity_start:identity_end
    ]

identity_compact = compact(
    identity_src
)

for field in (
    "reference_item_id",
    "source_sha256",
    "mechanical_analysis_id",
    "mechanical_analysis_sha256",
    "evidence_fingerprint",
    "priority_engine_version",
):

    check(
        "IDENTITY_INCLUDES_"
        + field.upper(),
        field in identity_src,
    )


for forbidden in (
    "acquisition_id",
    "media_artifact_id",
    "local_media_ref",
    "resolved_path",
    "preference_signal",
):

    check(
        "IDENTITY_EXCLUDES_"
        + forbidden.upper(),
        forbidden not in identity_src,
    )


# ============================================================
# K. VERIFIER MUST VERIFY CONTRACT, NOT ONLY RECORD HASH
# ============================================================

verifier_src = node_source(
    functions.get(
        "_verify_reference_priority_decision"
    )
)

verifier_compact = compact(
    verifier_src
)


check(
    "VERIFIER_CHECKS_RECORD_HASH",
    (
        "priority_decision_sha256"
        in verifier_src
        and
        "_canonical_sha256("
        in verifier_src
    ),
)


# Deterministic identity must be re-derived when reading.
# Merely requiring an RPD_ prefix is not enough.

check(
    "VERIFIER_RECOMPUTES_DECISION_IDENTITY",
    (
        (
            "'RPD_'+_canonical_sha256("
            in verifier_compact
            or
            '"RPD_"+_canonical_sha256('
            in verifier_compact
        )
        and
        "reference_item_id"
        in verifier_src
        and
        "source_sha256"
        in verifier_src
        and
        "mechanical_analysis_id"
        in verifier_src
        and
        "mechanical_analysis_sha256"
        in verifier_src
        and
        "evidence_fingerprint"
        in verifier_src
    ),
)


# The evidence fingerprint must itself be derived from the
# persisted evidence components, not merely checked as 64 hex.

check(
    "VERIFIER_RECOMPUTES_EVIDENCE_FINGERPRINT",
    (
        "components"
        in verifier_src
        and
        "evidence_fingerprint"
        in verifier_src
        and
        "_canonical_sha256("
        in verifier_src
    ),
)


# A deterministic engine should reject a persisted score that
# does not reproduce from its own evidence.

check(
    "VERIFIER_RECOMPUTES_PRIORITY_SCORE",
    "_reference_priority_score("
    in verifier_src,
)


check(
    "VERIFIER_SEMANTIC_ALLOW_INVARIANT",
    (
        "expected_semantic_allowed"
        in verifier_src
        and
        "REFERENCE_PRIORITY_SEMANTIC_ALLOW_INVALID"
        in verifier_src
    ),
)

check(
    "VERIFIER_REJECTS_MODEL_CALL_USED",
    "REFERENCE_PRIORITY_MODEL_CALL_POLICY_INVALID"
    in verifier_src,
)

check(
    "VERIFIER_REJECTS_COPYING_ALLOWED",
    "REFERENCE_PRIORITY_COPYING_POLICY_INVALID"
    in verifier_src,
)

check(
    "VERIFIER_REJECTS_FOUNDATION_OVERRIDE",
    "REFERENCE_PRIORITY_FOUNDATION_POLICY_INVALID"
    in verifier_src,
)


# ============================================================
# L. NO ABSOLUTE PATH IN PRIORITY DECISION RECORD
# ============================================================

for forbidden_key in (
    "source_resolved_path",
    "canonical_resolved_path",
    "local_media_ref",
    "contact_sheet_path",
):

    check(
        "DECISION_DOES_NOT_PERSIST_"
        + forbidden_key.upper(),
        (
            f'"{forbidden_key}"'
            not in eval_src
            and
            f"'{forbidden_key}'"
            not in eval_src
        ),
    )


# ============================================================
# M. CURRENT / STALE EVIDENCE ENFORCEMENT
# ============================================================

semantic_gate_src = node_source(
    functions.get(
        "_require_reference_priority_semantic_allowed"
    )
)

check(
    "SEMANTIC_GATE_REQUIRES_ACTIVE_ITEM",
    "_require_reference_item_active("
    in semantic_gate_src,
)

check(
    "SEMANTIC_GATE_REQUIRES_CURRENT_MECHANICAL",
    "_reference_priority_current_mechanical("
    in semantic_gate_src,
)

check(
    "SEMANTIC_GATE_REBUILDS_CURRENT_EVIDENCE",
    "_reference_priority_current_evidence("
    in semantic_gate_src,
)

check(
    "SEMANTIC_GATE_MATCHES_EVIDENCE_FINGERPRINT",
    "evidence_fingerprint"
    in semantic_gate_src,
)

check(
    "SEMANTIC_GATE_MISSING_DECISION_FAILS",
    "REFERENCE_PRIORITY_DECISION_REQUIRED"
    in semantic_gate_src,
)

check(
    "SEMANTIC_GATE_STALE_DECISION_FAILS",
    "REFERENCE_PRIORITY_DECISION_STALE"
    in semantic_gate_src,
)

check(
    "SEMANTIC_GATE_NON_ALLOWED_FAILS",
    "REFERENCE_PRIORITY_SEMANTIC_NOT_ALLOWED"
    in semantic_gate_src,
)


current_mechanical_src = node_source(
    functions.get(
        "_reference_priority_current_mechanical"
    )
)

check(
    "CURRENT_MECHANICAL_USES_ANALYZER_VERSION",
    "REFERENCE_MECHANICAL_ANALYZER_VERSION"
    in current_mechanical_src,
)

check(
    "CURRENT_MECHANICAL_VERIFIED",
    "_verify_reference_mechanical_analysis("
    in current_mechanical_src,
)


# ============================================================
# N. GLOBAL VISION CALL GRAPH
# ============================================================

vision_callers = []

for function_name in functions:

    for call in calls_in(
        function_name
    ):

        if (
            call_name(call)
            == "_reference_video_vision"
        ):

            vision_callers.append({
                "function":
                    function_name,

                "line":
                    int(
                        getattr(
                            call,
                            "lineno",
                            -1,
                        )
                    ),
            })


check(
    "ONE_GLOBAL_VISION_CALL_SITE",
    len(vision_callers) == 1,
    vision_callers,
)

check(
    "VISION_CALLER_ONLY_VIDEO_ANALYSIS",
    (
        len(vision_callers) == 1
        and
        vision_callers[0]["function"]
        == "production_reference_video_analysis"
    ),
    vision_callers,
)


video_node = functions.get(
    "production_reference_video_analysis"
)

video_src = node_source(
    video_node
)

guard_lines = []
vision_lines = []

if video_node is not None:

    for call in ast.walk(
        video_node
    ):

        if not isinstance(
            call,
            ast.Call,
        ):
            continue

        name = call_name(
            call
        )

        if (
            name
            == "_require_reference_priority_semantic_allowed"
        ):
            guard_lines.append(
                int(call.lineno)
            )

        if (
            name
            == "_reference_video_vision"
        ):
            vision_lines.append(
                int(call.lineno)
            )


check(
    "VIDEO_ANALYSIS_ACTIVE_GATE",
    "_require_reference_item_active("
    in video_src,
)

check(
    "VIDEO_HAS_EXACTLY_ONE_PRIORITY_GUARD",
    len(guard_lines) == 1,
    guard_lines,
)

check(
    "VIDEO_HAS_EXACTLY_ONE_VISION_CALL",
    len(vision_lines) == 1,
    vision_lines,
)

check(
    "PRIORITY_GUARD_BEFORE_VISION",
    (
        len(guard_lines) == 1
        and len(vision_lines) == 1
        and guard_lines[0]
            < vision_lines[0]
    ),
)


cache_pos = video_src.find(
    "if path.exists()"
)

guard_pos = video_src.find(
    "_require_reference_priority_semantic_allowed("
)

vision_pos = video_src.find(
    "_reference_video_vision("
)

check(
    "HISTORICAL_CACHE_PRECEDES_NEW_MODEL_GATE",
    (
        cache_pos >= 0
        and guard_pos >= 0
        and cache_pos < guard_pos
    ),
)

check(
    "NEW_MODEL_GATE_PRECEDES_MODEL_CALL",
    (
        guard_pos >= 0
        and vision_pos >= 0
        and guard_pos < vision_pos
    ),
)


# ============================================================
# O. RMA IDENTITY MUST REMAIN MEDIA-CENTRIC
# ============================================================

mechanical_src = node_source(
    functions.get(
        "production_reference_mechanical_analysis"
    )
)

mechanical_compact = compact(
    mechanical_src
)

rma_identity_marker = (
    "analysis_id='RMA_'+_canonical_sha256({"
    "'source_sha256':source_sha,"
    "'analyzer_version':REFERENCE_MECHANICAL_ANALYZER_VERSION,"
    "})[:32]"
)

check(
    "RMA_IDENTITY_STILL_MEDIA_CENTRIC",
    rma_identity_marker
    in mechanical_compact,
)


for forbidden in (
    "preference_signal",
    "_reference_video_vision(",
    "production_reference_feature(",
):

    check(
        "RMA_BOUNDARY_NO_"
        + re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            forbidden,
        ).strip("_").upper(),
        forbidden
        not in mechanical_src,
    )


# ============================================================
# P. 09C5 ARCHITECTURE MUST SURVIVE
# ============================================================

for marker in (
    "SM3_REFERENCE_MEDIA_ARTIFACT_V1",
    "SM3_REFERENCE_MEDIA_CAS_V1",
    "SM3_REFERENCE_MEDIA_ACQUISITION_V2",
    "SM3_REFERENCE_MEDIA_ACQUISITION_V1",
    "_resolve_reference_acquisition_source",
):

    check(
        "PRESERVE_09C5_"
        + re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            marker,
        ).strip("_").upper(),
        marker in text,
    )


# ============================================================
# Q. READERS / HISTORY
# ============================================================

decision_reader_src = node_source(
    functions.get(
        "_reference_priority_decisions_for_item"
    )
)

check(
    "HISTORICAL_DECISION_READER_USES_RAW_ITEM_LOADER",
    "_load_reference_item("
    in decision_reader_src,
)

check(
    "HISTORICAL_DECISION_READER_NOT_ACTIVE_ONLY",
    "_require_reference_item_active("
    not in decision_reader_src,
)


# ============================================================
# R. HEALTH
# ============================================================

for marker in (
    '"reference_priority_gate": True',
    '"reference_priority_decision_contract": '
    'REFERENCE_PRIORITY_DECISION_CONTRACT_VERSION',
    '"reference_priority_engine_version": '
    'REFERENCE_PRIORITY_ENGINE_VERSION',
    '"reference_priority_engine_deterministic": True',
    '"reference_priority_engine_model_call": False',
    '"reference_priority_semantic_fail_closed": True',
    '"reference_priority_novelty_v1": False',
):

    check(
        "HEALTH_"
        + re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            marker,
        ).strip("_").upper()[:80],
        marker in text,
    )


# ============================================================
# SUMMARY
# ============================================================

failed = [
    row
    for row in checks
    if not row["pass"]
]

passed = len(checks) - len(failed)

report = {
    "phase":
        "09C6-B2",

    "worker_version":
        constants.get(
            "WORKER_VERSION"
        ),

    "source_sha256":
        source_sha,

    "expected_source_sha256":
        EXPECTED_SHA,

    "check_count":
        len(checks),

    "pass_count":
        passed,

    "fail_count":
        len(failed),

    "all_passed":
        len(failed) == 0,

    "vision_callers":
        vision_callers,

    "failed_checks": [
        row["check"]
        for row in failed
    ],

    "checks":
        checks,
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


print()
print("=== SM3 09C6-B2 CHECKS ===")

for row in checks:

    state = (
        "PASS"
        if row["pass"]
        else "FAIL"
    )

    print(
        f"{state:4}  {row['check']}"
    )


print()
print("=== SM3 09C6-B2 SUMMARY ===")

print(
    f"SOURCE_SHA256={source_sha}"
)

print(
    f"CHECK_COUNT={len(checks)}"
)

print(
    f"PASS_COUNT={passed}"
)

print(
    f"FAIL_COUNT={len(failed)}"
)

print(
    "FAILED_CHECKS="
    + ",".join(
        row["check"]
        for row in failed
    )
)

print(
    f"VISION_CALLERS={vision_callers}"
)

print(
    f"REPORT={REPORT}"
)


if failed:

    print()
    print(
        "SM3_09C6_B2_PRIORITY_STATIC_GATE_FAIL"
    )

    sys.exit(1)


print()
print(
    "SM3_09C6_B2_PRIORITY_STATIC_GATE_PASS"
)
