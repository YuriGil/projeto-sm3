from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path


worker_path = Path(sys.argv[1])
temporal_path = Path(sys.argv[2])
output_path = Path(sys.argv[3])


EXPECTED_WORKER_SHA = (
    "5996325541ee0ed36f7a1fea3cfc9bafb35bab08"
    "c3a9a565b571b6eff31db9ff"
)

EXPECTED_TEMPORAL_SHA = (
    "848537b62be672c51b2ecd6c4079ad2057382c010"
    "34d2bdd2b0a50191055dc4d"
)


EXPECTED_IMPORTS = {
    "TEMPORAL_VALIDITY_ENGINE_VERSION",
    "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION",
    "TEMPORAL_VALIDITY_POLICY_VERSION",
    "TemporalValidityError",
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
}


def sha(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


checks: dict[str, bool] = {}


worker_sha = sha(worker_path)
temporal_sha = sha(temporal_path)


checks["WORKER_SHA_EXACT"] = (
    worker_sha == EXPECTED_WORKER_SHA
)

checks["TEMPORAL_SHA_EXACT"] = (
    temporal_sha == EXPECTED_TEMPORAL_SHA
)


worker_source = worker_path.read_text(
    encoding="utf-8-sig"
)

worker_tree = ast.parse(
    worker_source,
    filename=str(worker_path),
)


versions: list[str] = []
temporal_import_nodes: list[ast.ImportFrom] = []


for node in worker_tree.body:

    if isinstance(node, ast.Assign):

        for target in node.targets:

            if (
                isinstance(target, ast.Name)
                and target.id == "WORKER_VERSION"
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):

                versions.append(
                    node.value.value
                )


    if (
        isinstance(node, ast.ImportFrom)
        and node.module
        == "SM3_platform_temporal_validity_v1_r2"
    ):

        temporal_import_nodes.append(
            node
        )


imported_symbols: set[str] = set()
wildcard_import = False


for node in temporal_import_nodes:

    for alias in node.names:

        if alias.name == "*":
            wildcard_import = True
        else:
            imported_symbols.add(
                alias.name
            )


missing_expected_symbols = sorted(
    EXPECTED_IMPORTS
    - imported_symbols
)

extra_imported_symbols = sorted(
    imported_symbols
    - EXPECTED_IMPORTS
)


checks["WORKER_VERSION_EXACT"] = (
    versions == ["2.36.1"]
)

checks["TEMPORAL_IMPORT_PRESENT"] = (
    len(temporal_import_nodes) >= 1
)

checks["NO_TEMPORAL_WILDCARD_IMPORT"] = (
    wildcard_import is False
)

checks["EXPECTED_TEMPORAL_IMPORT_SURFACE_PRESENT"] = (
    len(missing_expected_symbols) == 0
)


# Count name references excluding import nodes.
usage_counts = {
    name: 0
    for name in EXPECTED_IMPORTS
}


for node in ast.walk(worker_tree):

    if not isinstance(node, ast.Name):
        continue

    if node.id in usage_counts:
        usage_counts[node.id] += 1


temporal_source = temporal_path.read_text(
    encoding="utf-8-sig"
)

temporal_tree = ast.parse(
    temporal_source,
    filename=str(temporal_path),
)


constants: dict[str, object] = {}


for node in temporal_tree.body:

    if not isinstance(node, ast.Assign):
        continue

    if not isinstance(node.value, ast.Constant):
        continue

    for target in node.targets:

        if isinstance(target, ast.Name):
            constants[target.id] = node.value.value


policy_version = constants.get(
    "TEMPORAL_VALIDITY_POLICY_VERSION"
)

engine_version = constants.get(
    "TEMPORAL_VALIDITY_ENGINE_VERSION"
)

implementation_revision = constants.get(
    "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION"
)


checks["TEMPORAL_POLICY_EXACT"] = (
    policy_version
    == "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
)

checks["TEMPORAL_ENGINE_EXACT"] = (
    engine_version
    == "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
)

checks["TEMPORAL_REVISION_EXACT"] = (
    implementation_revision == "R2"
)


failures = [
    name
    for name, value in checks.items()
    if not value
]


result = {
    "contract_version":
        "SM3_CURRENT_2361_TEMPORAL_STATIC_VERIFY_V1",

    "worker_sha256":
        worker_sha,

    "temporal_sha256":
        temporal_sha,

    "worker_versions":
        versions,

    "temporal_import_node_count":
        len(temporal_import_nodes),

    "imported_temporal_symbols":
        sorted(imported_symbols),

    "missing_expected_temporal_symbols":
        missing_expected_symbols,

    "extra_imported_temporal_symbols":
        extra_imported_symbols,

    "temporal_symbol_usage_counts":
        usage_counts,

    "temporal_policy_version":
        policy_version,

    "temporal_engine_version":
        engine_version,

    "temporal_implementation_revision":
        implementation_revision,

    "checks":
        checks,

    "check_count":
        len(checks),

    "pass_count":
        len(checks) - len(failures),

    "failure_count":
        len(failures),

    "failures":
        failures,

    "verification_pass":
        len(failures) == 0,
}


output_path.write_text(
    json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print(
    "STATIC_VERIFY_CHECK_COUNT="
    + str(result["check_count"])
)

print(
    "STATIC_VERIFY_PASS_COUNT="
    + str(result["pass_count"])
)

print(
    "STATIC_VERIFY_FAILURE_COUNT="
    + str(result["failure_count"])
)

print(
    "WORKER_VERSION="
    + (
        versions[0]
        if len(versions) == 1
        else "INVALID"
    )
)

print(
    "TEMPORAL_IMPORT_NODE_COUNT="
    + str(len(temporal_import_nodes))
)

print(
    "MISSING_EXPECTED_TEMPORAL_SYMBOL_COUNT="
    + str(len(missing_expected_symbols))
)

print(
    "EXTRA_TEMPORAL_SYMBOL_COUNT="
    + str(len(extra_imported_symbols))
)

print(
    "TEMPORAL_POLICY_VERSION="
    + str(policy_version)
)

print(
    "TEMPORAL_ENGINE_VERSION="
    + str(engine_version)
)

print(
    "TEMPORAL_IMPLEMENTATION_REVISION="
    + str(implementation_revision)
)

print(
    "STATIC_VERIFY_PASS="
    + str(result["verification_pass"])
)


if not result["verification_pass"]:
    raise SystemExit(1)