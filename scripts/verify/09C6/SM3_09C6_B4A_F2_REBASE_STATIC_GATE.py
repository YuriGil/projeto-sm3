from pathlib import Path
from datetime import datetime
import hashlib
import shutil


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

GATE = (
    ROOT
    / "scripts"
    / "verify"
    / "09C6"
    / "SM3_09C6_B2_PRIORITY_STATIC_GATE.py"
)

EXPECTED_GATE_SHA = (
    "21e0ec51ba9bc309cb0c46ee3cfac7c3"
    "6cdd8b817b18522cb594905f4fd3e835"
)


# ============================================================
# A. EXACT VERIFIER BASELINE
# ============================================================

if not GATE.exists():

    raise SystemExit(
        "SM3_09C6_B4A_F2_GATE_NOT_FOUND"
    )


raw = GATE.read_bytes()

before_sha = hashlib.sha256(
    raw
).hexdigest()


print(
    f"GATE_BEFORE_SHA256={before_sha}"
)


if before_sha != EXPECTED_GATE_SHA:

    raise SystemExit(
        "SM3_09C6_B4A_F2_GATE_BASELINE_SHA_MISMATCH:"
        f"{before_sha}"
    )


text = GATE.read_text(
    encoding="utf-8-sig"
)


# ============================================================
# B. REBASE EXPECTED WORKER SHA
# ============================================================

old_sha = '''EXPECTED_SHA = (
    "227ecf9eefcdb020f1da6917a30d3271"
    "7d8f10d7addc2d615d044b4ef7ce39d7"
)'''


new_sha = '''EXPECTED_SHA = (
    "3af5412234de7a7faa0e8b23116027b7"
    "cad25fe308698ca9188649ca3b1df8ba"
)'''


sha_count = text.count(
    old_sha
)


print(
    f"OLD_EXPECTED_SHA_COUNT={sha_count}"
)


if sha_count != 1:

    raise SystemExit(
        "SM3_09C6_B4A_F2_SHA_ANCHOR_INVALID:"
        f"{sha_count}"
    )


text = text.replace(
    old_sha,
    new_sha,
    1,
)


# ============================================================
# C. REBASE VERSION CHECK 2.23.0 -> 2.23.1
# ============================================================

old_version = '''check(
    "WORKER_VERSION_2_23",
    constants.get(
        "WORKER_VERSION"
    ) == "2.23.0",
    constants.get(
        "WORKER_VERSION"
    ),
)'''


new_version = '''check(
    "WORKER_VERSION_2_23_1",
    constants.get(
        "WORKER_VERSION"
    ) == "2.23.1",
    constants.get(
        "WORKER_VERSION"
    ),
)'''


version_count = text.count(
    old_version
)


print(
    f"OLD_VERSION_CHECK_COUNT={version_count}"
)


if version_count != 1:

    raise SystemExit(
        "SM3_09C6_B4A_F2_VERSION_CHECK_ANCHOR_INVALID:"
        f"{version_count}"
    )


text = text.replace(
    old_version,
    new_version,
    1,
)


# ============================================================
# D. ADD RESOLVER CONTRACT / ARITY INVARIANTS
# ============================================================

anchor = '''# ============================================================
# H. EVIDENCE SOURCES
# ============================================================'''


if text.count(anchor) != 1:

    raise SystemExit(
        "SM3_09C6_B4A_F2_EVIDENCE_SECTION_ANCHOR_INVALID"
    )


resolver_gate = r'''
# ============================================================
# G2. ACQUISITION SOURCE RESOLVER CONTRACT / ARITY
#
# 09C6-B4A discovered a class of bug that ordinary call-graph
# verification did not catch:
#
# resolver -> (source, media_artifact)
#
# A consumer must therefore unpack exactly two values.
# A single-variable assignment silently stores the tuple and
# later breaks consumers such as sha256_file(Path).
# ============================================================


resolver_node = functions.get(
    "_resolve_reference_acquisition_source"
)


resolver_returns = []


if resolver_node is not None:

    for candidate in ast.walk(
        resolver_node
    ):

        if not isinstance(
            candidate,
            ast.Return,
        ):
            continue

        if isinstance(
            candidate.value,
            ast.Tuple,
        ):

            resolver_returns.append({
                "line":
                    int(candidate.lineno),

                "arity":
                    len(
                        candidate.value.elts
                    ),
            })

        else:

            resolver_returns.append({
                "line":
                    int(candidate.lineno),

                "arity":
                    (
                        0
                        if candidate.value is None
                        else 1
                    ),
            })


resolver_return_arities = [
    row["arity"]
    for row in resolver_returns
]


check(
    "RESOLVER_CONTRACT_RETURNS_TWO_VALUES",
    (
        resolver_node is not None
        and len(
            resolver_return_arities
        ) >= 2
        and all(
            arity == 2
            for arity in resolver_return_arities
        )
    ),
    resolver_returns,
)


def resolver_assignments(
    function_name,
):

    node = functions.get(
        function_name
    )

    results = []

    if node is None:
        return results

    for candidate in ast.walk(
        node
    ):

        if not isinstance(
            candidate,
            ast.Assign,
        ):
            continue

        if not isinstance(
            candidate.value,
            ast.Call,
        ):
            continue

        if (
            call_name(
                candidate.value
            )
            != "_resolve_reference_acquisition_source"
        ):
            continue

        target_description = {
            "line":
                int(candidate.lineno),

            "kind":
                "UNKNOWN",

            "names":
                [],
        }

        if len(
            candidate.targets
        ) == 1:

            target = candidate.targets[0]

            if isinstance(
                target,
                ast.Tuple,
            ):

                target_description[
                    "kind"
                ] = "TUPLE"

                target_description[
                    "names"
                ] = [
                    (
                        element.id
                        if isinstance(
                            element,
                            ast.Name,
                        )
                        else None
                    )
                    for element
                    in target.elts
                ]

            elif isinstance(
                target,
                ast.Name,
            ):

                target_description[
                    "kind"
                ] = "NAME"

                target_description[
                    "names"
                ] = [
                    target.id
                ]

        results.append(
            target_description
        )

    return results


priority_resolver_assignments = (
    resolver_assignments(
        "production_reference_priority_decision"
    )
)


mechanical_resolver_assignments = (
    resolver_assignments(
        "production_reference_mechanical_analysis"
    )
)


priority_unpack_valid = (
    len(
        priority_resolver_assignments
    ) == 1
    and
    priority_resolver_assignments[0][
        "kind"
    ] == "TUPLE"
    and
    priority_resolver_assignments[0][
        "names"
    ] == [
        "source",
        "media_artifact",
    ]
)


mechanical_unpack_valid = (
    len(
        mechanical_resolver_assignments
    ) == 1
    and
    mechanical_resolver_assignments[0][
        "kind"
    ] == "TUPLE"
    and
    mechanical_resolver_assignments[0][
        "names"
    ] == [
        "source",
        "media_artifact",
    ]
)


check(
    "PRIORITY_RESOLVER_UNPACKS_TWO_VALUES",
    priority_unpack_valid,
    priority_resolver_assignments,
)


check(
    "MECHANICAL_RESOLVER_UNPACKS_TWO_VALUES",
    mechanical_unpack_valid,
    mechanical_resolver_assignments,
)


all_resolver_calls = []


for function_name,node in functions.items():

    for candidate in ast.walk(
        node
    ):

        if not isinstance(
            candidate,
            ast.Call,
        ):
            continue

        if (
            call_name(candidate)
            != "_resolve_reference_acquisition_source"
        ):
            continue

        all_resolver_calls.append({
            "function":
                function_name,

            "line":
                int(candidate.lineno),
        })


all_resolver_assignments = []


for function_name in functions:

    for assignment in resolver_assignments(
        function_name
    ):

        all_resolver_assignments.append({
            "function":
                function_name,

            **assignment,
        })


check(
    "ALL_RESOLVER_CALLS_ARE_ASSIGNED",
    (
        len(
            all_resolver_calls
        )
        ==
        len(
            all_resolver_assignments
        )
    ),
    {
        "calls":
            all_resolver_calls,

        "assignments":
            all_resolver_assignments,
    },
)


single_value_consumers = [
    row
    for row in all_resolver_assignments
    if (
        row.get("kind")
        != "TUPLE"
        or
        len(
            row.get(
                "names"
            ) or []
        ) != 2
    )
]


check(
    "NO_SINGLE_VALUE_RESOLVER_CONSUMERS",
    len(
        single_value_consumers
    ) == 0,
    single_value_consumers,
)


'''


text = text.replace(
    anchor,
    resolver_gate + anchor,
    1,
)


# ============================================================
# E. VERIFIER SCRIPT SYNTAX
# ============================================================

compile(
    text,
    str(GATE),
    "exec",
)


required = (
    "WORKER_VERSION_2_23_1",
    "3af5412234de7a7faa0e8b23116027b7",
    "cad25fe308698ca9188649ca3b1df8ba",
    "RESOLVER_CONTRACT_RETURNS_TWO_VALUES",
    "PRIORITY_RESOLVER_UNPACKS_TWO_VALUES",
    "MECHANICAL_RESOLVER_UNPACKS_TWO_VALUES",
    "ALL_RESOLVER_CALLS_ARE_ASSIGNED",
    "NO_SINGLE_VALUE_RESOLVER_CONSUMERS",
)


for marker in required:

    if marker not in text:

        raise SystemExit(
            "SM3_09C6_B4A_F2_REQUIRED_MARKER_MISSING:"
            f"{marker}"
        )


# ============================================================
# F. BACKUP VERIFIER
# ============================================================

stamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)


backup = GATE.with_name(
    "SM3_09C6_B2_PRIORITY_STATIC_GATE_pre_B4A_F2_"
    + stamp
    + ".py"
)


shutil.copy2(
    GATE,
    backup,
)


# ============================================================
# G. PERSIST + READ BACK
# ============================================================

GATE.write_text(
    text,
    encoding="utf-8",
)


persisted = GATE.read_text(
    encoding="utf-8"
)


compile(
    persisted,
    str(GATE),
    "exec",
)


after_sha = hashlib.sha256(
    GATE.read_bytes()
).hexdigest()


print(
    f"GATE_BACKUP={backup}"
)

print(
    f"GATE_AFTER_SHA256={after_sha}"
)

print(
    "EXPECTED_WORKER_VERSION=2.23.1"
)

print(
    "EXPECTED_WORKER_SHA256="
    "3af5412234de7a7faa0e8b23116027b7"
    "cad25fe308698ca9188649ca3b1df8ba"
)

print(
    "NEW_RESOLVER_ARITY_CHECKS=5"
)

print(
    "EXPECTED_TOTAL_STATIC_CHECKS=139"
)

print(
    "WORKER_MODIFIED=False"
)

print()

print(
    "SM3_09C6_B4A_F2_STATIC_GATE_REBASE_PASS"
)
