from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(sys.argv[1])
CANONICAL = Path(sys.argv[2])
STAGED = Path(sys.argv[3])
TEMPORAL = Path(sys.argv[4])
REPORT = Path(sys.argv[5])
PACKAGING_REPORT = Path(sys.argv[6])


EXPECTED_CANONICAL_SHA = (
    "cf778554e324acdc30ba60897767e97c8"
    "6dfe7fa3cc497ac0545cc71796ef89f"
)

EXPECTED_STAGED_SHA = (
    "550664623791a9f8a021c165b47ea511"
    "3226287cab63f0732767c47c1663a77e"
)

EXPECTED_TEMPORAL_SHA = (
    "848537b62be672c51b2ecd6c4079ad20"
    "57382c01034d2bdd2b0a50191055dc4d"
)

TEMPORAL_MODULE = (
    "SM3_platform_temporal_validity_v1_r2"
)

EXPECTED_IMPORTED_NAMES = sorted([
    "TEMPORAL_VALIDITY_POLICY_VERSION",
    "TEMPORAL_VALIDITY_ENGINE_VERSION",
    "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION",
    "TemporalValidityError",
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
])

CALLABLE_TEMPORAL_NAMES = {
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
}


def sha256(path: Path) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write_json(path: Path, value):

    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


canonical_sha = sha256(
    CANONICAL
)

staged_sha = sha256(
    STAGED
)

temporal_sha = sha256(
    TEMPORAL
)


if canonical_sha != EXPECTED_CANONICAL_SHA:

    raise SystemExit(
        "A4_A5_CANONICAL_SHA_MISMATCH:"
        + canonical_sha
    )


if staged_sha != EXPECTED_STAGED_SHA:

    raise SystemExit(
        "A4_A5_STAGED_SHA_MISMATCH:"
        + staged_sha
    )


if temporal_sha != EXPECTED_TEMPORAL_SHA:

    raise SystemExit(
        "A4_A5_TEMPORAL_SHA_MISMATCH:"
        + temporal_sha
    )


canonical_source = CANONICAL.read_text(
    encoding="utf-8-sig"
)

staged_source = STAGED.read_text(
    encoding="utf-8-sig"
)

temporal_source = TEMPORAL.read_text(
    encoding="utf-8-sig"
)


canonical_tree = ast.parse(
    canonical_source,
    filename=str(
        CANONICAL
    ),
)

staged_tree = ast.parse(
    staged_source,
    filename=str(
        STAGED
    ),
)

temporal_tree = ast.parse(
    temporal_source,
    filename=str(
        TEMPORAL
    ),
)


attacks = []


def record(
    attack_id,
    severity,
    title,
    passed,
    detail=None,
):

    attacks.append({
        "attack_id":
            attack_id,

        "severity":
            severity,

        "title":
            title,

        "passed":
            bool(
                passed
            ),

        "finding":
            (
                "PASS"
                if passed
                else "GAP"
            ),

        "detail":
            detail,
    })


# ============================================================
# A — EXACT ARTIFACT IDENTITY
# ============================================================

record(
    "A001",
    "CRITICAL",
    "Canonical Worker SHA exact",
    canonical_sha
    == EXPECTED_CANONICAL_SHA,
    canonical_sha,
)


record(
    "A002",
    "CRITICAL",
    "Staged Worker SHA exact",
    staged_sha
    == EXPECTED_STAGED_SHA,
    staged_sha,
)


record(
    "A003",
    "CRITICAL",
    "Temporal module SHA exact",
    temporal_sha
    == EXPECTED_TEMPORAL_SHA,
    temporal_sha,
)


# ============================================================
# B — VERSION DELTA
# ============================================================

def version_values(tree):

    result = []

    for node in tree.body:

        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        for target in node.targets:

            if (
                isinstance(
                    target,
                    ast.Name,
                )
                and
                target.id
                == "WORKER_VERSION"
            ):

                if (
                    isinstance(
                        node.value,
                        ast.Constant,
                    )
                    and
                    isinstance(
                        node.value.value,
                        str,
                    )
                ):

                    result.append(
                        node.value.value
                    )

    return result


canonical_versions = version_values(
    canonical_tree
)

staged_versions = version_values(
    staged_tree
)


record(
    "B001",
    "CRITICAL",
    "Canonical version remains exactly 2.35.0",
    canonical_versions
    == [
        "2.35.0"
    ],
    canonical_versions,
)


record(
    "B002",
    "CRITICAL",
    "Staged version is exactly 2.35.1",
    staged_versions
    == [
        "2.35.1"
    ],
    staged_versions,
)


# ============================================================
# C — TEMPORAL IMPORT EXACTNESS
# ============================================================

temporal_import_nodes = []


for node in staged_tree.body:

    if (
        isinstance(
            node,
            ast.ImportFrom,
        )
        and
        node.module
        == TEMPORAL_MODULE
    ):

        temporal_import_nodes.append(
            node
        )


imported_names = []


for node in temporal_import_nodes:

    for alias in node.names:

        imported_names.append(
            alias.asname
            or
            alias.name
        )


imported_names = sorted(
    imported_names
)


record(
    "C001",
    "CRITICAL",
    "Exactly one temporal ImportFrom exists",
    len(
        temporal_import_nodes
    )
    == 1,
    len(
        temporal_import_nodes
    ),
)


record(
    "C002",
    "CRITICAL",
    "Temporal import symbol set exact",
    imported_names
    == EXPECTED_IMPORTED_NAMES,
    imported_names,
)


aliasing_present = False


for node in temporal_import_nodes:

    for alias in node.names:

        if alias.asname is not None:

            aliasing_present = True


record(
    "C003",
    "HIGH",
    "Temporal import does not rename symbols",
    aliasing_present
    is False,
    aliasing_present,
)


# ============================================================
# D — DORMANCY
# ============================================================

usage_counts = {
    name:
        0
    for name in EXPECTED_IMPORTED_NAMES
}


for node in ast.walk(
    staged_tree
):

    if (
        isinstance(
            node,
            ast.Name,
        )
        and
        isinstance(
            node.ctx,
            ast.Load,
        )
        and
        node.id
        in usage_counts
    ):

        usage_counts[
            node.id
        ] += 1


call_usage_counts = {
    name:
        0
    for name in sorted(
        CALLABLE_TEMPORAL_NAMES
    )
}


for node in ast.walk(
    staged_tree
):

    if not isinstance(
        node,
        ast.Call,
    ):
        continue

    if (
        isinstance(
            node.func,
            ast.Name,
        )
        and
        node.func.id
        in call_usage_counts
    ):

        call_usage_counts[
            node.func.id
        ] += 1


record(
    "D001",
    "CRITICAL",
    "No imported temporal symbol is consumed by Worker",
    all(
        value == 0
        for value in usage_counts.values()
    ),
    usage_counts,
)


record(
    "D002",
    "CRITICAL",
    "No temporal validation function is called by Worker",
    all(
        value == 0
        for value in call_usage_counts.values()
    ),
    call_usage_counts,
)


# ============================================================
# E — STRONG NORMALIZED AST EQUIVALENCE
# ============================================================

normalized_stage = copy.deepcopy(
    staged_tree
)


normalized_body = []


for node in normalized_stage.body:

    if (
        isinstance(
            node,
            ast.ImportFrom,
        )
        and
        node.module
        == TEMPORAL_MODULE
    ):

        continue

    normalized_body.append(
        node
    )


normalized_stage.body = normalized_body


version_rewrites = 0


for node in normalized_stage.body:

    if not isinstance(
        node,
        ast.Assign,
    ):
        continue

    is_worker_version = False

    for target in node.targets:

        if (
            isinstance(
                target,
                ast.Name,
            )
            and
            target.id
            == "WORKER_VERSION"
        ):

            is_worker_version = True


    if not is_worker_version:
        continue


    if (
        isinstance(
            node.value,
            ast.Constant,
        )
        and
        node.value.value
        == "2.35.1"
    ):

        node.value.value = "2.35.0"
        node.value.s = "2.35.0"
        version_rewrites += 1


canonical_dump = ast.dump(
    canonical_tree,
    annotate_fields=True,
    include_attributes=False,
)


normalized_dump = ast.dump(
    normalized_stage,
    annotate_fields=True,
    include_attributes=False,
)


record(
    "E001",
    "CRITICAL",
    "Exactly one staged version assignment normalized",
    version_rewrites == 1,
    version_rewrites,
)


record(
    "E002",
    "CRITICAL",
    "Normalized staged AST equals canonical AST exactly",
    normalized_dump
    == canonical_dump,
    {
        "canonical_ast_sha256":
            hashlib.sha256(
                canonical_dump.encode(
                    "utf-8"
                )
            ).hexdigest(),

        "normalized_stage_ast_sha256":
            hashlib.sha256(
                normalized_dump.encode(
                    "utf-8"
                )
            ).hexdigest(),
    },
)


# ============================================================
# F — ROUTE / DECORATOR ATTACK
# ============================================================

def route_literals(tree):

    values = []

    for node in ast.walk(
        tree
    ):

        if (
            isinstance(
                node,
                ast.Constant,
            )
            and
            isinstance(
                node.value,
                str,
            )
            and
            node.value.startswith(
                "/production/"
            )
        ):

            values.append(
                node.value
            )

    return sorted(
        values
    )


canonical_routes = route_literals(
    canonical_tree
)

staged_routes = route_literals(
    staged_tree
)


record(
    "F001",
    "CRITICAL",
    "Production route literals exactly unchanged",
    canonical_routes
    == staged_routes,
    {
        "canonical_count":
            len(
                canonical_routes
            ),

        "staged_count":
            len(
                staged_routes
            ),
    },
)


def decorator_dump(tree):

    result = []

    for node in ast.walk(
        tree
    ):

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):

            for decorator in node.decorator_list:

                result.append(
                    ast.dump(
                        decorator,
                        annotate_fields=True,
                        include_attributes=False,
                    )
                )

    return sorted(
        result
    )


record(
    "F002",
    "CRITICAL",
    "Decorator topology unchanged",
    decorator_dump(
        canonical_tree
    )
    == decorator_dump(
        staged_tree
    ),
)


# ============================================================
# G — STORE / FILESYSTEM DELTA ATTACK
# ============================================================

def relevant_storage_literals(tree):

    result = []

    for node in ast.walk(
        tree
    ):

        if (
            isinstance(
                node,
                ast.Constant,
            )
            and
            isinstance(
                node.value,
                str,
            )
        ):

            low = node.value.lower()

            if (
                "production_state"
                in low
                or
                "platform_dynamics"
                in low
                or
                "platform_hypoth"
                in low
                or
                "platform_prediction"
                in low
                or
                "platform_drift"
                in low
                or
                "platform_experiment"
                in low
                or
                "temporal_signature"
                in low
            ):

                result.append(
                    node.value
                )

    return sorted(
        result
    )


record(
    "G001",
    "CRITICAL",
    "Storage-related literal topology unchanged",
    relevant_storage_literals(
        canonical_tree
    )
    == relevant_storage_literals(
        staged_tree
    ),
)


# ============================================================
# H — TEMPORAL MODULE SIDE-EFFECT AUDIT
# ============================================================

imports = set()
calls = []


def dotted_name(node):

    if isinstance(
        node,
        ast.Name,
    ):

        return node.id

    if isinstance(
        node,
        ast.Attribute,
    ):

        parent = dotted_name(
            node.value
        )

        if parent:

            return (
                parent
                + "."
                + node.attr
            )

        return node.attr

    return None


for node in ast.walk(
    temporal_tree
):

    if isinstance(
        node,
        ast.Import,
    ):

        for alias in node.names:

            imports.add(
                alias.name
            )

    elif isinstance(
        node,
        ast.ImportFrom,
    ):

        if node.module:

            imports.add(
                node.module
            )

    elif isinstance(
        node,
        ast.Call,
    ):

        name = dotted_name(
            node.func
        )

        if name:

            calls.append(
                name
            )


forbidden_import_roots = {
    "requests",
    "httpx",
    "urllib",
    "socket",
    "subprocess",
}


forbidden_imports = sorted(
    item
    for item in imports
    if item.split(
        "."
    )[0]
    in forbidden_import_roots
)


dangerous_exact_calls = {
    "open",
    "os.remove",
    "os.unlink",
    "os.rename",
    "os.replace",
    "subprocess.run",
    "subprocess.call",
    "subprocess.Popen",
    "requests.get",
    "requests.post",
    "httpx.get",
    "httpx.post",
}


dangerous_suffixes = {
    ".write_text",
    ".write_bytes",
    ".unlink",
    ".rename",
}


dangerous_calls = sorted(
    set(
        name
        for name in calls
        if (
            name in dangerous_exact_calls
            or
            any(
                name.endswith(
                    suffix
                )
                for suffix in dangerous_suffixes
            )
        )
    )
)


replace_calls = sorted(
    set(
        name
        for name in calls
        if name.endswith(
            ".replace"
        )
    )
)


record(
    "H001",
    "CRITICAL",
    "Temporal module has no network/process imports",
    forbidden_imports == [],
    forbidden_imports,
)


record(
    "H002",
    "CRITICAL",
    "Temporal module has no write/process/network calls",
    dangerous_calls == [],
    dangerous_calls,
)


record(
    "H003",
    "HIGH",
    "Only known raw.replace call exists",
    replace_calls
    == [
        "raw.replace"
    ],
    replace_calls,
)


# ============================================================
# I — PACKAGING TOPOLOGY AUDIT
# ============================================================

compose_candidates = []


deployment = (
    ROOT
    / "deployment"
)


if deployment.exists():

    for path in sorted(
        deployment.rglob(
            "*"
        )
    ):

        if not path.is_file():
            continue

        low = path.name.lower()

        if (
            low.endswith(
                ".yml"
            )
            or
            low.endswith(
                ".yaml"
            )
        ):

            try:

                text = path.read_text(
                    encoding="utf-8-sig"
                )

            except Exception:

                continue

            if "media-worker" in text:

                compose_candidates.append({
                    "path":
                        str(
                            path.relative_to(
                                ROOT
                            )
                        ),

                    "sha256":
                        sha256(
                            path
                        ),

                    "text":
                        text,
                })


dockerfile_refs = []


dockerfile_pattern = re.compile(
    r"(?im)^\s*dockerfile\s*:\s*['\"]?([^'\"\r\n#]+)"
)


for item in compose_candidates:

    for match in dockerfile_pattern.finditer(
        item[
            "text"
        ]
    ):

        raw = match.group(
            1
        ).strip()

        dockerfile_refs.append({
            "compose":
                item[
                    "path"
                ],

            "dockerfile_ref":
                raw,
        })


possible_dockerfiles = []


for path in ROOT.rglob(
    "*"
):

    if not path.is_file():
        continue

    low = path.name.lower()

    if (
        low == "dockerfile"
        or
        low.startswith(
            "dockerfile."
        )
        or
        "dockerfile" in low
    ):

        try:

            text = path.read_text(
                encoding="utf-8-sig"
            )

        except Exception:

            continue

        possible_dockerfiles.append({
            "path":
                str(
                    path.relative_to(
                        ROOT
                    )
                ),

            "sha256":
                sha256(
                    path
                ),

            "text":
                text,
        })


worker_packaging_evidence = []


patterns = [
    "worker_service.py",
    "worker/",
    "worker\\",
    "/app",
    "COPY ",
    "ADD ",
    "volumes:",
]


for item in compose_candidates:

    lines = item[
        "text"
    ].splitlines()

    relevant = []

    for index,line in enumerate(
        lines,
        start=1,
    ):

        if any(
            pattern.lower()
            in line.lower()
            for pattern in patterns
        ):

            relevant.append({
                "line":
                    index,

                "text":
                    line.strip(),
            })

    worker_packaging_evidence.append({
        "type":
            "COMPOSE",

        "path":
            item[
                "path"
            ],

        "relevant_lines":
            relevant,
    })


for item in possible_dockerfiles:

    lines = item[
        "text"
    ].splitlines()

    relevant = []

    for index,line in enumerate(
        lines,
        start=1,
    ):

        if any(
            pattern.lower()
            in line.lower()
            for pattern in patterns
        ):

            relevant.append({
                "line":
                    index,

                "text":
                    line.strip(),
            })

    worker_packaging_evidence.append({
        "type":
            "DOCKERFILE",

        "path":
            item[
                "path"
            ],

        "relevant_lines":
            relevant,
    })


#
# Static A5 does not yet assert deployability merely from
# substring heuristics. It classifies whether enough packaging
# evidence exists for A6 to build an isolated image candidate.
#

packaging_evidence_present = (
    bool(
        compose_candidates
    )
    and
    bool(
        worker_packaging_evidence
    )
)


record(
    "I001",
    "CRITICAL",
    "Media-worker compose topology discovered",
    bool(
        compose_candidates
    ),
    [
        item[
            "path"
        ]
        for item in compose_candidates
    ],
)


record(
    "I002",
    "HIGH",
    "Worker packaging evidence discovered",
    packaging_evidence_present,
    worker_packaging_evidence,
)


packaging_report = {
    "phase":
        "09C7-B3E-A4-A5",

    "status":
        "PACKAGING_TOPOLOGY_AUDIT_COMPLETE",

    "compose_candidate_count":
        len(
            compose_candidates
        ),

    "compose_candidates": [
        {
            "path":
                item[
                    "path"
                ],

            "sha256":
                item[
                    "sha256"
                ],
        }
        for item in compose_candidates
    ],

    "dockerfile_ref_count":
        len(
            dockerfile_refs
        ),

    "dockerfile_refs":
        dockerfile_refs,

    "possible_dockerfile_count":
        len(
            possible_dockerfiles
        ),

    "possible_dockerfiles": [
        {
            "path":
                item[
                    "path"
                ],

            "sha256":
                item[
                    "sha256"
                ],
        }
        for item in possible_dockerfiles
    ],

    "worker_packaging_evidence":
        worker_packaging_evidence,

    "packaging_evidence_present":
        packaging_evidence_present,

    "deployment_performed":
        False,
}


write_json(
    PACKAGING_REPORT,
    packaging_report,
)


# ============================================================
# J — IMPORT ORDER / PYTHON LEGALITY
# ============================================================

future_import_lines = []


for node in staged_tree.body:

    if (
        isinstance(
            node,
            ast.ImportFrom,
        )
        and
        node.module
        == "__future__"
    ):

        future_import_lines.append(
            node.lineno
        )


temporal_import_line = (
    temporal_import_nodes[
        0
    ].lineno
    if len(
        temporal_import_nodes
    )
    == 1
    else None
)


future_import_order_valid = (
    temporal_import_line
    is not None
    and
    all(
        line
        < temporal_import_line
        for line in future_import_lines
    )
)


record(
    "J001",
    "CRITICAL",
    "Temporal import occurs after all __future__ imports",
    future_import_order_valid,
    {
        "future_import_lines":
            future_import_lines,

        "temporal_import_line":
            temporal_import_line,
    },
)


try:

    compile(
        staged_source,
        str(
            STAGED
        ),
        "exec",
    )

    staged_compile_pass = True
    staged_compile_error = None

except Exception as exc:

    staged_compile_pass = False
    staged_compile_error = repr(
        exc
    )


record(
    "J002",
    "CRITICAL",
    "Staged Worker compiles statically",
    staged_compile_pass,
    staged_compile_error,
)


try:

    compile(
        temporal_source,
        str(
            TEMPORAL
        ),
        "exec",
    )

    temporal_compile_pass = True
    temporal_compile_error = None

except Exception as exc:

    temporal_compile_pass = False
    temporal_compile_error = repr(
        exc
    )


record(
    "J003",
    "CRITICAL",
    "Temporal module compiles statically",
    temporal_compile_pass,
    temporal_compile_error,
)


# ============================================================
# K — NO DUPLICATE TOP-LEVEL DEFINITIONS
# ============================================================

def duplicate_top_level_defs(tree):

    names = []

    for node in tree.body:

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):

            names.append(
                node.name
            )

    counter = Counter(
        names
    )

    return sorted(
        name
        for name,count
        in counter.items()
        if count > 1
    )


canonical_duplicates = duplicate_top_level_defs(
    canonical_tree
)

staged_duplicates = duplicate_top_level_defs(
    staged_tree
)


record(
    "K001",
    "CRITICAL",
    "No new duplicate top-level definitions introduced",
    staged_duplicates
    == canonical_duplicates,
    {
        "canonical":
            canonical_duplicates,

        "staged":
            staged_duplicates,
    },
)


# ============================================================
# FINAL CLASSIFICATION
# ============================================================

failures = [
    row
    for row in attacks
    if not row[
        "passed"
    ]
]


critical_gaps = [
    row
    for row in failures
    if row[
        "severity"
    ]
    == "CRITICAL"
]


high_gaps = [
    row
    for row in failures
    if row[
        "severity"
    ]
    == "HIGH"
]


static_attack_pass = (
    len(
        failures
    )
    == 0
)


report = {
    "phase":
        "09C7-B3E-A4-A5",

    "status":
        "DORMANT_RUNTIME_STATIC_ATTACK_COMPLETE",

    "canonical_worker_sha256":
        canonical_sha,

    "staged_worker_sha256":
        staged_sha,

    "temporal_module_sha256":
        temporal_sha,

    "attack_count":
        len(
            attacks
        ),

    "pass_count":
        len(
            attacks
        )
        - len(
            failures
        ),

    "failure_count":
        len(
            failures
        ),

    "critical_gap_count":
        len(
            critical_gaps
        ),

    "high_gap_count":
        len(
            high_gaps
        ),

    "static_attack_pass":
        static_attack_pass,

    "usage_counts":
        usage_counts,

    "call_usage_counts":
        call_usage_counts,

    "normalized_ast_exact_match":
        normalized_dump
        == canonical_dump,

    "canonical_route_count":
        len(
            canonical_routes
        ),

    "staged_route_count":
        len(
            staged_routes
        ),

    "packaging_evidence_present":
        packaging_evidence_present,

    "runtime_deployment_performed":
        False,

    "canonical_worker_modified":
        False,

    "production_restart_executed":
        False,

    "route_called":
        False,

    "network_request_performed":
        False,

    "provider_called":
        False,

    "model_called":
        False,

    "attacks":
        attacks,

    "next_gate":
        (
            "09C7-B3E-A4-A6_ISOLATED_RUNTIME_BUILD_PREFLIGHT"
            if static_attack_pass
            else
            "09C7-B3E-A4-A5_REMEDIATION_REQUIRED"
        ),
}


write_json(
    REPORT,
    report,
)


print(
    "=== DORMANT RUNTIME STATIC ATTACK ==="
)

print(
    "ATTACK_COUNT="
    + str(
        report[
            "attack_count"
        ]
    )
)

print(
    "PASS_COUNT="
    + str(
        report[
            "pass_count"
        ]
    )
)

print(
    "FAILURE_COUNT="
    + str(
        report[
            "failure_count"
        ]
    )
)

print(
    "CRITICAL_GAP_COUNT="
    + str(
        report[
            "critical_gap_count"
        ]
    )
)

print(
    "HIGH_GAP_COUNT="
    + str(
        report[
            "high_gap_count"
        ]
    )
)

print(
    "STATIC_ATTACK_PASS="
    + str(
        report[
            "static_attack_pass"
        ]
    )
)


print(
    "\n=== FINDINGS ==="
)

for row in attacks:

    print(
        row[
            "attack_id"
        ]
        + " "
        + row[
            "severity"
        ]
        + " "
        + row[
            "finding"
        ]
        + " :: "
        + row[
            "title"
        ]
    )

    if not row[
        "passed"
    ]:

        print(
            "  DETAIL="
            + json.dumps(
                row.get(
                    "detail"
                ),
                ensure_ascii=False,
                default=str,
            )
        )


print(
    "\n=== STRONG EQUIVALENCE ==="
)

print(
    "NORMALIZED_AST_EXACT_MATCH="
    + str(
        report[
            "normalized_ast_exact_match"
        ]
    )
)

print(
    "CANONICAL_ROUTE_COUNT="
    + str(
        report[
            "canonical_route_count"
        ]
    )
)

print(
    "STAGED_ROUTE_COUNT="
    + str(
        report[
            "staged_route_count"
        ]
    )
)

print(
    "TEMPORAL_USAGE_COUNTS="
    + json.dumps(
        usage_counts,
        sort_keys=True,
    )
)

print(
    "TEMPORAL_CALL_USAGE_COUNTS="
    + json.dumps(
        call_usage_counts,
        sort_keys=True,
    )
)


print(
    "\n=== PACKAGING ==="
)

print(
    "PACKAGING_EVIDENCE_PRESENT="
    + str(
        packaging_evidence_present
    )
)

print(
    "COMPOSE_CANDIDATE_COUNT="
    + str(
        packaging_report[
            "compose_candidate_count"
        ]
    )
)

print(
    "DOCKERFILE_REF_COUNT="
    + str(
        packaging_report[
            "dockerfile_ref_count"
        ]
    )
)

print(
    "POSSIBLE_DOCKERFILE_COUNT="
    + str(
        packaging_report[
            "possible_dockerfile_count"
        ]
    )
)


print(
    "\nRUNTIME_DEPLOYMENT_PERFORMED=False"
)

print(
    "CANONICAL_WORKER_MODIFIED=False"
)

print(
    "PRODUCTION_RESTART_EXECUTED=False"
)

print(
    "ROUTE_CALLED=False"
)

print(
    "NETWORK_REQUEST_PERFORMED=False"
)

print(
    "PROVIDER_CALLED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "NEXT_GATE="
    + report[
        "next_gate"
    ]
)


if not static_attack_pass:

    raise SystemExit(
        1
    )
