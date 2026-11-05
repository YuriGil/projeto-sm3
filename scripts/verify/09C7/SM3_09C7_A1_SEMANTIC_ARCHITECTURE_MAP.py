from pathlib import Path
import ast
import hashlib
import json
import re


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

WORKER = ROOT / "worker" / "worker_service.py"

EXPECTED_SHA = (
    "3af5412234de7a7faa0e8b23116027b7"
    "cad25fe308698ca9188649ca3b1df8ba"
)


raw = WORKER.read_bytes()

sha = hashlib.sha256(raw).hexdigest()


if sha != EXPECTED_SHA:
    raise SystemExit(
        "SM3_09C7_A1_SOURCE_SHA_INVALID:"
        + sha
    )


source = WORKER.read_text(
    encoding="utf-8-sig"
)

lines = source.splitlines()

tree = ast.parse(
    source,
    filename=str(WORKER),
)


functions = {}

classes = {}


for node in tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        functions[node.name] = node

    if isinstance(
        node,
        ast.ClassDef,
    ):
        classes[node.name] = node


def segment(node):

    return "\n".join(
        lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


def call_name(call):

    fn = call.func

    if isinstance(fn, ast.Name):
        return fn.id

    if isinstance(fn, ast.Attribute):

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

    return "<unknown>"


def request_fields(class_name):

    node = classes.get(
        class_name
    )

    if node is None:
        return []

    result = []

    for child in node.body:

        if isinstance(
            child,
            ast.AnnAssign,
        ):

            if isinstance(
                child.target,
                ast.Name,
            ):

                result.append(
                    child.target.id
                )

    return result


def function_calls(function_name):

    node = functions.get(
        function_name
    )

    if node is None:
        return []

    result = []

    for child in ast.walk(
        node
    ):

        if isinstance(
            child,
            ast.Call,
        ):

            result.append({
                "line":
                    int(child.lineno),

                "name":
                    call_name(child),
            })

    return sorted(
        result,
        key=lambda row: (
            row["line"],
            row["name"],
        )
    )


def assigned_value(name):

    for node in tree.body:

        if isinstance(
            node,
            ast.Assign,
        ):

            for target in node.targets:

                if (
                    isinstance(
                        target,
                        ast.Name,
                    )
                    and
                    target.id == name
                ):

                    try:
                        return ast.literal_eval(
                            node.value
                        )
                    except Exception:
                        return ast.unparse(
                            node.value
                        )

    return None


targets = [
    "ReferenceVideoAnalysisRequest",
    "ReferenceFeatureObservationRequest",
    "ReferencePriorityDecisionRequest",
    "ReferenceMechanicalAnalysisRequest",
]


function_targets = [
    "_reference_video_vision",
    "_verify_reference_video_analysis",
    "production_reference_video_analysis",
    "production_reference_video_analysis_latest",
    "production_reference_feature",
    "production_reference_features",
    "_require_reference_priority_semantic_allowed",
    "_reference_priority_current_evidence",
]


constant_targets = [
    "REFERENCE_VIDEO_ANALYSIS_CONTRACT_VERSION",
    "REFERENCE_VIDEO_ANALYZER_VERSION",
    "REFERENCE_VIDEO_VISION_SCHEMA_VERSION",
    "REFERENCE_FEATURE_CONTRACT_VERSION",
    "REFERENCE_PRIORITY_DECISION_CONTRACT_VERSION",
    "REFERENCE_PRIORITY_ENGINE_VERSION",
    "REFERENCE_MECHANICAL_ANALYSIS_CONTRACT_VERSION",
    "REFERENCE_MECHANICAL_ANALYZER_VERSION",
    "VISION_MODEL",
]


print(
    "============================================================"
)

print(
    "SM3 09C7-A1 SEMANTIC ARCHITECTURE MAP"
)

print(
    "============================================================"
)

print(
    f"WORKER_SHA256={sha}"
)

print(
    "WORKER_VERSION_2_23_1="
    + str(
        'WORKER_VERSION = "2.23.1"'
        in source
    )
)

print()


# ============================================================
# CONSTANTS
# ============================================================

print(
    "============================================================"
)

print(
    "SEMANTIC / LEGACY CONSTANTS"
)

print(
    "============================================================"
)


for name in constant_targets:

    print(
        f"{name}={assigned_value(name)}"
    )


# ============================================================
# REQUEST MODELS
# ============================================================

print()

print(
    "============================================================"
)

print(
    "REQUEST MODELS"
)

print(
    "============================================================"
)


for class_name in targets:

    node = classes.get(
        class_name
    )

    print()

    print(
        f"--- {class_name} ---"
    )

    print(
        "FIELDS="
        + ",".join(
            request_fields(
                class_name
            )
        )
    )

    if node is not None:

        print(
            segment(node)
        )


# ============================================================
# FUNCTIONS
# ============================================================

print()

print(
    "============================================================"
)

print(
    "SEMANTIC FUNCTIONS"
)

print(
    "============================================================"
)


for function_name in function_targets:

    node = functions.get(
        function_name
    )

    print()

    print(
        f"--- {function_name} ---"
    )

    if node is None:

        print(
            "MISSING"
        )

        continue

    print(
        f"LINE={node.lineno}"
    )

    print(
        segment(node)
    )


# ============================================================
# VIDEO CALL GRAPH
# ============================================================

print()

print(
    "============================================================"
)

print(
    "LEGACY VIDEO ANALYSIS CALL GRAPH"
)

print(
    "============================================================"
)


video_calls = function_calls(
    "production_reference_video_analysis"
)


for row in video_calls:

    print(
        f"line={row['line']} call={row['name']}"
    )


# ============================================================
# VISION CALL GRAPH
# ============================================================

print()

print(
    "============================================================"
)

print(
    "VISION HELPER CALL GRAPH"
)

print(
    "============================================================"
)


vision_calls = function_calls(
    "_reference_video_vision"
)


for row in vision_calls:

    print(
        f"line={row['line']} call={row['name']}"
    )


# ============================================================
# CROSS-CALLER SEARCH
# ============================================================

vision_callers = []

priority_guard_callers = []


for name,node in functions.items():

    calls = function_calls(
        name
    )

    for row in calls:

        if row["name"] == "_reference_video_vision":

            vision_callers.append({
                "function":
                    name,

                "line":
                    row["line"],
            })

        if row["name"] == "_require_reference_priority_semantic_allowed":

            priority_guard_callers.append({
                "function":
                    name,

                "line":
                    row["line"],
            })


print()

print(
    "============================================================"
)

print(
    "VISION CALLERS"
)

print(
    "============================================================"
)

print(
    json.dumps(
        vision_callers,
        indent=2,
        sort_keys=True,
    )
)


print()

print(
    "============================================================"
)

print(
    "PRIORITY GUARD CALLERS"
)

print(
    "============================================================"
)

print(
    json.dumps(
        priority_guard_callers,
        indent=2,
        sort_keys=True,
    )
)


# ============================================================
# LEGACY COUPLING MARKERS
# ============================================================

video_node = functions.get(
    "production_reference_video_analysis"
)

video_src = (
    segment(video_node)
    if video_node is not None
    else ""
)


coupling = {

    "USES_LOCAL_MEDIA_REF":
        "local_media_ref"
        in video_src,

    "USES_REQUEST_PREFERENCE_SIGNAL":
        "preference_signal"
        in video_src,

    "USES_REQUEST_NOTES":
        "req.notes"
        in video_src,

    "REBUILDS_CONTACT_SHEET":
        "make_contact_sheet"
        in video_src,

    "RECALCULATES_CUT_METRICS":
        "_reference_cut_metrics"
        in video_src,

    "RECALCULATES_AUDIO_ONSETS":
        "_reference_audio_onsets"
        in video_src,

    "RECALCULATES_COLOR_STATS":
        "_reference_color_stats"
        in video_src,

    "CALLS_PRIORITY_GUARD":
        "_require_reference_priority_semantic_allowed"
        in video_src,

    "CALLS_VISION":
        "_reference_video_vision"
        in video_src,

    "WRITES_FEATURE_OBSERVATION":
        (
            "ReferenceFeatureObservationRequest"
            in video_src
            or
            "production_reference_feature"
            in video_src
        ),

    "VIDEO_ID_DEPENDS_ON_ITEM":
        (
            '"reference_item_id"'
            in video_src
            and
            "analysis_id"
            in video_src
        ),

    "REQUEST_FINGERPRINT_USES_LOCAL_PATH":
        (
            "request_fingerprint"
            in video_src
            and
            "local_media_ref"
            in video_src
        ),
}


print()

print(
    "============================================================"
)

print(
    "LEGACY COUPLING"
)

print(
    "============================================================"
)


for name,value in coupling.items():

    print(
        f"{name}={value}"
    )


# ============================================================
# STORAGE ROOT / ROUTE SEARCH
# ============================================================

markers = [
    "PRODUCTION_REFERENCE_VIDEO_ANALYSES",
    "PRODUCTION_REFERENCE_FEATURES",
    "/production/reference-corpus/video-analysis",
    "/production/reference-corpus/feature-observation",
]


print()

print(
    "============================================================"
)

print(
    "STORAGE / ROUTE MARKERS"
)

print(
    "============================================================"
)


for marker in markers:

    occurrences = []

    for i,line in enumerate(
        lines,
        start=1,
    ):

        if marker in line:

            occurrences.append(
                i
            )

    print(
        marker
        + "="
        + ",".join(
            str(x)
            for x in occurrences
        )
    )


# ============================================================
# ASSERTIONS
# ============================================================

checks = {

    "SOURCE_SHA_EXPECTED":
        sha == EXPECTED_SHA,

    "WORKER_VERSION_2_23_1":
        'WORKER_VERSION = "2.23.1"'
        in source,

    "VIDEO_REQUEST_MODEL_FOUND":
        classes.get(
            "ReferenceVideoAnalysisRequest"
        )
        is not None,

    "FEATURE_REQUEST_MODEL_FOUND":
        classes.get(
            "ReferenceFeatureObservationRequest"
        )
        is not None,

    "PRIORITY_REQUEST_MODEL_FOUND":
        classes.get(
            "ReferencePriorityDecisionRequest"
        )
        is not None,

    "MECHANICAL_REQUEST_MODEL_FOUND":
        classes.get(
            "ReferenceMechanicalAnalysisRequest"
        )
        is not None,

    "VISION_HELPER_FOUND":
        functions.get(
            "_reference_video_vision"
        )
        is not None,

    "VIDEO_ENDPOINT_FOUND":
        functions.get(
            "production_reference_video_analysis"
        )
        is not None,

    "PRIORITY_GUARD_FOUND":
        functions.get(
            "_require_reference_priority_semantic_allowed"
        )
        is not None,

    "EXACTLY_ONE_VISION_CALLER":
        len(
            vision_callers
        ) == 1,

    "VISION_CALLER_IS_LEGACY_VIDEO_ENDPOINT":
        (
            len(
                vision_callers
            ) == 1
            and
            vision_callers[0]["function"]
            == "production_reference_video_analysis"
        ),

    "LEGACY_VIDEO_HAS_PRIORITY_GUARD":
        coupling[
            "CALLS_PRIORITY_GUARD"
        ],

    "LEGACY_VIDEO_REBUILDS_MECHANICAL":
        (
            coupling[
                "REBUILDS_CONTACT_SHEET"
            ]
            and
            coupling[
                "RECALCULATES_CUT_METRICS"
            ]
            and
            coupling[
                "RECALCULATES_AUDIO_ONSETS"
            ]
            and
            coupling[
                "RECALCULATES_COLOR_STATS"
            ]
        ),

    "LEGACY_VIDEO_USES_LOCAL_MEDIA_REF":
        coupling[
            "USES_LOCAL_MEDIA_REF"
        ],

    "LEGACY_FINGERPRINT_USES_LOCAL_PATH":
        coupling[
            "REQUEST_FINGERPRINT_USES_LOCAL_PATH"
        ],
}


print()

print(
    "============================================================"
)

print(
    "A1 CHECKS"
)

print(
    "============================================================"
)


for name,value in checks.items():

    print(
        f"{name}={value}"
    )


failed = [
    name
    for name,value
    in checks.items()
    if not value
]


print()

print(
    f"CHECK_COUNT={len(checks)}"
)

print(
    "PASS_COUNT="
    + str(
        len(checks)
        - len(failed)
    )
)

print(
    f"FAIL_COUNT={len(failed)}"
)

print(
    "FAILED_CHECKS="
    + ",".join(
        failed
    )
)


if failed:

    raise SystemExit(
        "SM3_09C7_A1_SEMANTIC_ARCHITECTURE_MAP_FAIL"
    )


print()

print(
    "SM3_09C7_A1_SEMANTIC_ARCHITECTURE_MAP_PASS"
)
