from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(sys.argv[1])
WORKER = Path(sys.argv[2])
RUNTIME_COPY = Path(sys.argv[3])
CANDIDATE = Path(sys.argv[4])
REPORT = Path(sys.argv[5])
MANIFEST = Path(sys.argv[6])


EXPECTED_WORKER_SHA = (
    "cf778554e324acdc30ba60897767e97c8"
    "6dfe7fa3cc497ac0545cc71796ef89f"
)

EXPECTED_CANDIDATE_SHA = (
    "848537b62be672c51b2ecd6c4079ad20"
    "57382c01034d2bdd2b0a50191055dc4d"
)


def sha256(path: Path) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write_json(
    path: Path,
    value,
):

    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


worker_sha = sha256(
    WORKER
)

runtime_sha = sha256(
    RUNTIME_COPY
)

candidate_sha = sha256(
    CANDIDATE
)


if worker_sha != EXPECTED_WORKER_SHA:

    raise SystemExit(
        "A4_A3_HOST_WORKER_SHA_MISMATCH:"
        + worker_sha
    )


if runtime_sha != EXPECTED_WORKER_SHA:

    raise SystemExit(
        "A4_A3_RUNTIME_WORKER_SHA_MISMATCH:"
        + runtime_sha
    )


if candidate_sha != EXPECTED_CANDIDATE_SHA:

    raise SystemExit(
        "A4_A3_CANDIDATE_SHA_MISMATCH:"
        + candidate_sha
    )


# ============================================================
# 1. PARSE BOTH SOURCES
# ============================================================

worker_source = WORKER.read_text(
    encoding="utf-8-sig"
)

candidate_source = CANDIDATE.read_text(
    encoding="utf-8-sig"
)


worker_tree = ast.parse(
    worker_source,
    filename=str(
        WORKER
    ),
)


candidate_tree = ast.parse(
    candidate_source,
    filename=str(
        CANDIDATE
    ),
)


# ============================================================
# 2. SYMBOL MAP HELPERS
# ============================================================

def top_level_symbols(
    tree,
):

    result = []

    for node in tree.body:

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):

            result.append({
                "name":
                    node.name,

                "kind":
                    type(
                        node
                    ).__name__,

                "line":
                    getattr(
                        node,
                        "lineno",
                        None,
                    ),
            })

        elif isinstance(
            node,
            ast.Assign,
        ):

            for target in node.targets:

                if isinstance(
                    target,
                    ast.Name,
                ):

                    result.append({
                        "name":
                            target.id,

                        "kind":
                            "Assign",

                        "line":
                            getattr(
                                node,
                                "lineno",
                                None,
                            ),
                    })

    return result


worker_symbols = top_level_symbols(
    worker_tree
)

candidate_symbols = top_level_symbols(
    candidate_tree
)


worker_symbol_names = {
    item[
        "name"
    ]
    for item in worker_symbols
}


candidate_symbol_names = {
    item[
        "name"
    ]
    for item in candidate_symbols
}


required_candidate_symbols = {
    "TEMPORAL_VALIDITY_POLICY_VERSION",
    "TEMPORAL_VALIDITY_ENGINE_VERSION",
    "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION",
    "TemporalValidityError",
    "_parse_timestamp",
    "_iso",
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
}


missing_candidate_symbols = sorted(
    required_candidate_symbols
    - candidate_symbol_names
)


symbol_collisions = sorted(
    required_candidate_symbols
    & worker_symbol_names
)


# ============================================================
# 3. CANDIDATE IMPORT AUDIT
# ============================================================

candidate_imports = []


for node in candidate_tree.body:

    if isinstance(
        node,
        ast.Import,
    ):

        for alias in node.names:

            candidate_imports.append(
                alias.name
            )

    elif isinstance(
        node,
        ast.ImportFrom,
    ):

        if node.module:

            candidate_imports.append(
                node.module
            )


candidate_imports = sorted(
    set(
        candidate_imports
    )
)


allowed_import_roots = {
    "__future__",
    "copy",
    "datetime",
    "typing",
}


unexpected_candidate_imports = sorted(
    item
    for item in candidate_imports
    if item.split(
        "."
    )[0]
    not in allowed_import_roots
)


# ============================================================
# 4. EXISTING PLATFORM DYNAMICS CONTRACT MAP
# ============================================================

required_existing_literals = [
    "SM3_BLACK_BOX_DYNAMICS_ENGINE_V1",
    "SM3_PLATFORM_DYNAMICS_SNAPSHOT_V1",
    "SM3_PLATFORM_DYNAMICS_EVIDENCE_V1",
    "SM3_PLATFORM_PREFERENCE_SIGNAL_V1",
]


existing_contract_literals = {
    literal:
        (
            literal
            in worker_source
        )
    for literal in required_existing_literals
}


platform_dynamics_literal_pass = all(
    existing_contract_literals.values()
)


# ============================================================
# 5. TEMPORAL V1 MUST NOT ALREADY BE IN RUNTIME
# ============================================================

temporal_runtime_literals = {
    "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1":
        (
            "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
            in worker_source
        ),

    "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1":
        (
            "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
            in worker_source
        ),

    "SOURCE_AFTER_OBSERVATION_ERROR":
        (
            "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_AFTER_OBSERVATION"
            in worker_source
        ),
}


temporal_already_integrated = any(
    temporal_runtime_literals.values()
)


# ============================================================
# 6. ROUTE INVENTORY
# ============================================================

route_pattern = re.compile(
    r"""["'](
        /production/
        [^"' \t\r\n]+
    )["']""",
    re.VERBOSE,
)


all_route_literals = sorted(
    set(
        route_pattern.findall(
            worker_source
        )
    )
)


platform_routes = [
    route
    for route in all_route_literals
    if (
        "platform-dynamics"
        in route
        or
        "platform-preference"
        in route
    )
]


expected_route_fragments = [
    "/production/culture-intelligence/platform-dynamics/evidence",
    "/production/culture-intelligence/platform-preference-signals",
    "/production/culture-intelligence/platform-dynamics/snapshots",
    "/production/culture-intelligence/platform-dynamics/summary",
]


route_presence = {
    route:
        (
            route
            in all_route_literals
        )
    for route in expected_route_fragments
}


required_routes_present = all(
    route_presence.values()
)


# ============================================================
# 7. PLATFORM-RELATED SYMBOL INVENTORY
# ============================================================

platform_related_symbols = []


for item in worker_symbols:

    low = item[
        "name"
    ].lower()

    if (
        "platform"
        in low
        or
        "dynamics"
        in low
        or
        "preference"
        in low
    ):

        platform_related_symbols.append(
            item
        )


platform_related_symbols = sorted(
    platform_related_symbols,
    key=lambda item: (
        item.get(
            "line"
        )
        or 0,
        item[
            "name"
        ],
    )
)


# ============================================================
# 8. SNAPSHOT-RELATED INTEGRATION SEAMS
# ============================================================

snapshot_related_symbols = []


for item in platform_related_symbols:

    low = item[
        "name"
    ].lower()

    if "snapshot" in low:

        snapshot_related_symbols.append(
            item
        )


snapshot_contract_lines = []


for line_number,line in enumerate(
    worker_source.splitlines(),
    start=1,
):

    if (
        "SM3_PLATFORM_DYNAMICS_SNAPSHOT_V1"
        in line
        or
        "SM3_BLACK_BOX_DYNAMICS_ENGINE_V1"
        in line
    ):

        snapshot_contract_lines.append({
            "line":
                line_number,

            "text":
                line.strip(),
        })


snapshot_contract_lines = snapshot_contract_lines[
    :80
]


# ============================================================
# 9. PACKAGING TOPOLOGY AUDIT
# ============================================================

packaging_files = []


candidate_packaging_roots = [
    ROOT / "deployment",
    ROOT / "worker",
]


for base in candidate_packaging_roots:

    if not base.exists():
        continue

    for path in base.rglob(
        "*"
    ):

        if not path.is_file():
            continue

        name_low = path.name.lower()

        if (
            name_low.startswith(
                "dockerfile"
            )
            or
            (
                name_low.endswith(
                    ".yml"
                )
                and
                (
                    "compose"
                    in name_low
                    or
                    "docker"
                    in name_low
                )
            )
            or
            (
                name_low.endswith(
                    ".yaml"
                )
                and
                (
                    "compose"
                    in name_low
                    or
                    "docker"
                    in name_low
                )
            )
        ):

            try:

                text = path.read_text(
                    encoding="utf-8-sig"
                )

            except Exception:

                continue

            relevant_lines = []

            for line_number,line in enumerate(
                text.splitlines(),
                start=1,
            ):

                low = line.lower()

                if (
                    "worker"
                    in low
                    or
                    "copy"
                    in low
                    or
                    "/app"
                    in low
                    or
                    "dockerfile"
                    in low
                ):

                    relevant_lines.append({
                        "line":
                            line_number,

                        "text":
                            line.strip(),
                    })

            packaging_files.append({
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

                "relevant_lines":
                    relevant_lines[
                        :80
                    ],
            })


# ============================================================
# 10. SCOPE BOUNDARY
# ============================================================

#
# Temporal validity V1 is deliberately narrower than Snapshot V2.
#
# It MUST NOT silently become responsible for:
#
# - duplicate evidence IDs
# - duplicate signal IDs
# - platform/surface matching
# - snapshot identity
# - confidence decay
# - hypothesis selection
# - drift evaluation
# - metric weighting
#
# Those belong to later V2 components.
#

out_of_scope_responsibilities = [
    "DUPLICATE_EVIDENCE_ID_VALIDATION",
    "DUPLICATE_SIGNAL_ID_VALIDATION",
    "PLATFORM_SURFACE_SCOPE_MATCHING",
    "SNAPSHOT_IDENTITY_CONSTRUCTION",
    "CONFIDENCE_DECAY_NUMERIC_POLICY",
    "ACTIVE_HYPOTHESIS_SELECTION",
    "DRIFT_EVALUATION",
    "METRIC_WEIGHT_LEARNING",
]


# ============================================================
# 11. INTEGRATION SAFETY POLICY
# ============================================================

integration_policy = {
    "integration_mode":
        "DORMANT_RUNTIME_CAPABILITY",

    "public_route_added":
        False,

    "production_state_store_added":
        False,

    "existing_route_behavior_changed":
        False,

    "existing_v1_record_migration":
        False,

    "network_call_added":
        False,

    "provider_call_added":
        False,

    "model_call_added":
        False,

    "confidence_decay_enabled":
        False,

    "candidate_contract_semantics_may_change":
        False,

    "candidate_sha_must_remain_source_evidence":
        True,

    "worker_version_must_increment_on_integration":
        True,

    "integration_requires_post_materialization_static_attack":
        True,

    "integration_requires_container_dynamic_test":
        True,

    "integration_requires_scope_aware_mutation_accounting":
        True,

    "integration_requires_no_route_exposure":
        True,

    "consumer_binding_deferred_until_snapshot_v2":
        True,
}


# ============================================================
# 12. PREFLIGHT CHECKS
# ============================================================

checks = {
    "HOST_WORKER_SHA_CANONICAL":
        worker_sha
        == EXPECTED_WORKER_SHA,

    "RUNTIME_COPY_SHA_CANONICAL":
        runtime_sha
        == EXPECTED_WORKER_SHA,

    "HOST_RUNTIME_SOURCE_MATCH":
        worker_sha
        == runtime_sha,

    "CANDIDATE_SHA_CANONICAL":
        candidate_sha
        == EXPECTED_CANDIDATE_SHA,

    "CANDIDATE_SYMBOL_SET_COMPLETE":
        not missing_candidate_symbols,

    "NO_TARGET_SYMBOL_COLLISIONS":
        not symbol_collisions,

    "CANDIDATE_STDLIB_ONLY":
        not unexpected_candidate_imports,

    "PLATFORM_DYNAMICS_V1_FOUND":
        platform_dynamics_literal_pass,

    "PLATFORM_DYNAMICS_ROUTES_FOUND":
        required_routes_present,

    "TEMPORAL_VALIDITY_NOT_ALREADY_IN_RUNTIME":
        not temporal_already_integrated,

    "SNAPSHOT_INTEGRATION_SEAM_FOUND":
        (
            bool(
                snapshot_related_symbols
            )
            or
            bool(
                snapshot_contract_lines
            )
        ),

    "PACKAGING_TOPOLOGY_INSPECTED":
        bool(
            packaging_files
        ),

    "NO_ROUTE_REQUIRED_FOR_TEMPORAL_ENGINE":
        integration_policy[
            "public_route_added"
        ]
        is False,

    "NO_STORE_REQUIRED_FOR_TEMPORAL_ENGINE":
        integration_policy[
            "production_state_store_added"
        ]
        is False,

    "CONSUMER_BINDING_DEFERRED_TO_SNAPSHOT_V2":
        integration_policy[
            "consumer_binding_deferred_until_snapshot_v2"
        ]
        is True,

    "CONFIDENCE_DECAY_STILL_DEFERRED":
        integration_policy[
            "confidence_decay_enabled"
        ]
        is False,
}


preflight_pass = all(
    checks.values()
)


# ============================================================
# 13. MATERIALIZATION DECISION
# ============================================================

#
# We deliberately do NOT select "import separate module" vs
# "embed definitions" merely by guessing from the repository.
#
# A4-A4 must use this packaging evidence to materialize a
# candidate Worker and then prove its exact runtime packaging.
#

integration_strategy_status = (
    "READY_FOR_MATERIALIZATION"
    if preflight_pass
    else
    "BLOCKED"
)


next_gate = (
    "09C7-B3E-A4-A4_DORMANT_RUNTIME_INTEGRATION_MATERIALIZATION"
    if preflight_pass
    else
    "09C7-B3E-A4-A3_REMEDIATION_REQUIRED"
)


manifest = {
    "contract_version":
        "SM3_TEMPORAL_VALIDITY_INTEGRATION_MANIFEST_V1",

    "phase":
        "09C7-B3E-A4-A3",

    "target_worker_version":
        "2.35.0",

    "target_worker_sha256":
        worker_sha,

    "temporal_candidate_sha256":
        candidate_sha,

    "temporal_policy_version":
        "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1",

    "temporal_engine_version":
        "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1",

    "temporal_implementation_revision":
        "R2",

    "required_candidate_symbols":
        sorted(
            required_candidate_symbols
        ),

    "symbol_collisions":
        symbol_collisions,

    "platform_routes":
        platform_routes,

    "snapshot_related_symbols":
        snapshot_related_symbols,

    "snapshot_contract_lines":
        snapshot_contract_lines,

    "packaging_files":
        packaging_files,

    "integration_policy":
        integration_policy,

    "out_of_scope_responsibilities":
        out_of_scope_responsibilities,

    "materialization_status":
        integration_strategy_status,

    "next_gate":
        next_gate,
}


write_json(
    MANIFEST,
    manifest,
)


manifest_sha = sha256(
    MANIFEST
)


report = {
    "phase":
        "09C7-B3E-A4-A3",

    "status":
        "TEMPORAL_VALIDITY_INTEGRATION_PREFLIGHT_COMPLETE",

    "worker_sha256":
        worker_sha,

    "runtime_copy_sha256":
        runtime_sha,

    "candidate_sha256":
        candidate_sha,

    "checks":
        checks,

    "check_count":
        len(
            checks
        ),

    "pass_count":
        sum(
            1
            for value in checks.values()
            if value
        ),

    "failure_count":
        sum(
            1
            for value in checks.values()
            if not value
        ),

    "preflight_pass":
        preflight_pass,

    "missing_candidate_symbols":
        missing_candidate_symbols,

    "symbol_collisions":
        symbol_collisions,

    "candidate_imports":
        candidate_imports,

    "unexpected_candidate_imports":
        unexpected_candidate_imports,

    "existing_contract_literals":
        existing_contract_literals,

    "temporal_runtime_literals":
        temporal_runtime_literals,

    "temporal_already_integrated":
        temporal_already_integrated,

    "route_presence":
        route_presence,

    "platform_routes":
        platform_routes,

    "platform_related_symbol_count":
        len(
            platform_related_symbols
        ),

    "platform_related_symbols":
        platform_related_symbols[
            :160
        ],

    "snapshot_related_symbol_count":
        len(
            snapshot_related_symbols
        ),

    "snapshot_related_symbols":
        snapshot_related_symbols,

    "snapshot_contract_lines":
        snapshot_contract_lines,

    "packaging_file_count":
        len(
            packaging_files
        ),

    "packaging_files":
        packaging_files,

    "integration_policy":
        integration_policy,

    "out_of_scope_responsibilities":
        out_of_scope_responsibilities,

    "integration_manifest_sha256":
        manifest_sha,

    "integration_strategy_status":
        integration_strategy_status,

    "runtime_integration_performed":
        False,

    "worker_source_modified":
        False,

    "route_added":
        False,

    "production_state_write_performed":
        False,

    "network_request_performed":
        False,

    "provider_called":
        False,

    "model_called":
        False,

    "next_gate":
        next_gate,
}


write_json(
    REPORT,
    report,
)


print(
    "=== TEMPORAL VALIDITY INTEGRATION PREFLIGHT ==="
)

print(
    "WORKER_SHA256="
    + worker_sha
)

print(
    "RUNTIME_COPY_SHA256="
    + runtime_sha
)

print(
    "CANDIDATE_SHA256="
    + candidate_sha
)


print(
    "\n=== CHECKS ==="
)

for name,value in checks.items():

    print(
        name
        + "="
        + str(
            value
        )
    )


print(
    "\nCHECK_COUNT="
    + str(
        report[
            "check_count"
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
    "PREFLIGHT_PASS="
    + str(
        preflight_pass
    )
)


print(
    "\n=== SYMBOL MAP ==="
)

print(
    "MISSING_CANDIDATE_SYMBOLS="
    + json.dumps(
        missing_candidate_symbols
    )
)

print(
    "SYMBOL_COLLISIONS="
    + json.dumps(
        symbol_collisions
    )
)

print(
    "CANDIDATE_IMPORTS="
    + json.dumps(
        candidate_imports
    )
)

print(
    "UNEXPECTED_CANDIDATE_IMPORTS="
    + json.dumps(
        unexpected_candidate_imports
    )
)


print(
    "\n=== EXISTING PLATFORM DYNAMICS ==="
)

print(
    "PLATFORM_RELATED_SYMBOL_COUNT="
    + str(
        len(
            platform_related_symbols
        )
    )
)

print(
    "SNAPSHOT_RELATED_SYMBOL_COUNT="
    + str(
        len(
            snapshot_related_symbols
        )
    )
)

print(
    "PLATFORM_ROUTE_COUNT="
    + str(
        len(
            platform_routes
        )
    )
)

for route in platform_routes:

    print(
        "PLATFORM_ROUTE="
        + route
    )


print(
    "\n=== PACKAGING ==="
)

print(
    "PACKAGING_FILE_COUNT="
    + str(
        len(
            packaging_files
        )
    )
)

for item in packaging_files:

    print(
        "PACKAGING_FILE="
        + item[
            "path"
        ]
    )


print(
    "\n=== INTEGRATION BOUNDARY ==="
)

print(
    "INTEGRATION_MODE=DORMANT_RUNTIME_CAPABILITY"
)

print(
    "PUBLIC_ROUTE_ADDED=False"
)

print(
    "PRODUCTION_STATE_STORE_ADDED=False"
)

print(
    "EXISTING_ROUTE_BEHAVIOR_CHANGED=False"
)

print(
    "NETWORK_CALL_ADDED=False"
)

print(
    "PROVIDER_CALL_ADDED=False"
)

print(
    "MODEL_CALL_ADDED=False"
)

print(
    "CONFIDENCE_DECAY_ENABLED=False"
)

print(
    "CONSUMER_BINDING_DEFERRED_UNTIL_SNAPSHOT_V2=True"
)


print(
    "\n=== MATERIALIZATION ==="
)

print(
    "INTEGRATION_STRATEGY_STATUS="
    + integration_strategy_status
)

print(
    "MANIFEST_SHA256="
    + manifest_sha
)

print(
    "NEXT_GATE="
    + next_gate
)


print(
    "\nRUNTIME_INTEGRATION_PERFORMED=False"
)

print(
    "WORKER_SOURCE_MODIFIED=False"
)

print(
    "ROUTE_ADDED=False"
)

print(
    "PRODUCTION_STATE_WRITE_PERFORMED=False"
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


if not preflight_pass:

    raise SystemExit(
        1
    )
