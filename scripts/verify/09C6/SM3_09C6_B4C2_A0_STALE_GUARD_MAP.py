from pathlib import Path
import ast
import hashlib
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
        "SM3_09C6_B4C2_A0_PY_SOURCE_SHA_INVALID:"
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


def string_constants(node):

    out = []

    for child in ast.walk(node):

        if (
            isinstance(
                child,
                ast.Constant,
            )
            and
            isinstance(
                child.value,
                str,
            )
        ):
            out.append(
                child.value
            )

    return out


request_class = classes.get(
    "ReferenceVideoAnalysisRequest"
)


video_fn = functions.get(
    "production_reference_video_analysis"
)


if request_class is None:
    raise SystemExit(
        "SM3_09C6_B4C2_A0_VIDEO_REQUEST_CLASS_MISSING"
    )


if video_fn is None:
    raise SystemExit(
        "SM3_09C6_B4C2_A0_VIDEO_ENDPOINT_FUNCTION_MISSING"
    )


video_calls = []


for node in ast.walk(
    video_fn
):

    if isinstance(
        node,
        ast.Call,
    ):

        video_calls.append({
            "line":
                int(node.lineno),

            "name":
                call_name(node),
        })


video_calls.sort(
    key=lambda row: (
        row["line"],
        row["name"],
    )
)


vision_calls = [
    row
    for row in video_calls
    if row["name"]
    == "_reference_video_vision"
]


priority_calls = [
    row
    for row in video_calls
    if "priority" in row["name"].lower()
]


guard_candidates = []


for name,node in functions.items():

    text = segment(node)

    markers = (
        "REFERENCE_PRIORITY",
        "SEMANTIC_ANALYSIS",
        "evidence_fingerprint",
        "_reference_priority_current_evidence",
    )

    if (
        "priority" in name.lower()
        and
        any(
            marker in text
            for marker in markers
        )
    ):

        guard_candidates.append(
            (
                node.lineno,
                name,
                node,
            )
        )


guard_candidates.sort()


priority_error_strings = []


for _,name,node in guard_candidates:

    for value in string_constants(
        node
    ):

        if (
            "PRIORITY" in value.upper()
            or
            "SEMANTIC" in value.upper()
            or
            "EVIDENCE" in value.upper()
        ):

            priority_error_strings.append({
                "function":
                    name,

                "value":
                    value,
            })


request_source = segment(
    request_class
)


video_source = segment(
    video_fn
)


request_fields = []


for child in request_class.body:

    if isinstance(
        child,
        ast.AnnAssign,
    ):

        if isinstance(
            child.target,
            ast.Name,
        ):

            request_fields.append(
                child.target.id
            )


vision_lines = [
    row["line"]
    for row in vision_calls
]


priority_lines = [
    row["line"]
    for row in priority_calls
]


priority_before_vision = (
    len(vision_lines) == 1
    and
    any(
        line < vision_lines[0]
        for line in priority_lines
    )
)


print(
    "============================================================"
)

print(
    "SM3 09C6-B4C2-A0 STALE EVIDENCE GUARD MAP"
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


print(
    "============================================================"
)

print(
    "REFERENCE VIDEO REQUEST SCHEMA"
)

print(
    "============================================================"
)

print(
    "FIELDS="
    + ",".join(
        request_fields
    )
)

print()

print(
    request_source
)

print()


print(
    "============================================================"
)

print(
    "VIDEO ANALYSIS CALL ORDER"
)

print(
    "============================================================"
)


for row in video_calls:

    if (
        "priority" in row["name"].lower()
        or
        row["name"]
        == "_reference_video_vision"
        or
        "media" in row["name"].lower()
        or
        "source" in row["name"].lower()
    ):

        print(
            f"CALL line={row['line']} name={row['name']}"
        )


print()

print(
    "VISION_CALL_COUNT="
    + str(
        len(vision_calls)
    )
)

print(
    "PRIORITY_CALL_COUNT_IN_VIDEO_FUNCTION="
    + str(
        len(priority_calls)
    )
)

print(
    "PRIORITY_GUARD_BEFORE_VISION="
    + str(
        priority_before_vision
    )
)

print()


print(
    "============================================================"
)

print(
    "PRIORITY / SEMANTIC GUARD CANDIDATES"
)

print(
    "============================================================"
)


for line,name,node in guard_candidates:

    print()

    print(
        f"--- {name} @ line {line} ---"
    )

    print(
        segment(node)
    )


print()

print(
    "============================================================"
)

print(
    "PRIORITY ERROR STRINGS"
)

print(
    "============================================================"
)


for row in priority_error_strings:

    print(
        f"{row['function']}: {row['value']}"
    )


print()

print(
    "============================================================"
)

print(
    "VIDEO ANALYSIS FUNCTION"
)

print(
    "============================================================"
)

print(
    video_source
)


checks = {

    "SOURCE_SHA_EXPECTED":
        sha == EXPECTED_SHA,

    "WORKER_VERSION_2_23_1":
        'WORKER_VERSION = "2.23.1"'
        in source,

    "REQUEST_CLASS_FOUND":
        request_class is not None,

    "REQUEST_HAS_REFERENCE_ITEM_ID":
        "reference_item_id"
        in request_fields,

    "REQUEST_HAS_LOCAL_MEDIA_REF":
        "local_media_ref"
        in request_fields,

    "VIDEO_FUNCTION_FOUND":
        video_fn is not None,

    "EXACTLY_ONE_VISION_CALL":
        len(
            vision_calls
        ) == 1,

    "PRIORITY_CALL_PRESENT":
        len(
            priority_calls
        ) >= 1,

    "PRIORITY_GUARD_BEFORE_VISION":
        priority_before_vision,

    "GUARD_CANDIDATE_FOUND":
        len(
            guard_candidates
        ) >= 1,

    "PRIORITY_ERROR_STRING_FOUND":
        len(
            priority_error_strings
        ) >= 1,
}


print()

print(
    "============================================================"
)

print(
    "A0 CHECKS"
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
        "SM3_09C6_B4C2_A0_STALE_GUARD_MAP_FAIL"
    )


print()

print(
    "SM3_09C6_B4C2_A0_STALE_GUARD_MAP_PASS"
)
