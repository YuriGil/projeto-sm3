from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path


worker_path = Path(sys.argv[1])
temporal_path = Path(sys.argv[2])
requirements_path = Path(sys.argv[3])
output_path = Path(sys.argv[4])


EXPECTED_WORKER_SHA = (
    "550664623791a9f8a021c165b47ea511"
    "3226287cab63f0732767c47c1663a77e"
)

EXPECTED_TEMPORAL_SHA = (
    "848537b62be672c51b2ecd6c4079ad20"
    "57382c01034d2bdd2b0a50191055dc4d"
)

EXPECTED_REQUIREMENTS_SHA = (
    "68758b81820c6128e5f72dc66c76e15"
    "af9d6585e86c4726583509379419f50e1"
)

EXPECTED_IMPORTS = sorted([
    "TEMPORAL_VALIDITY_ENGINE_VERSION",
    "TEMPORAL_VALIDITY_IMPLEMENTATION_REVISION",
    "TEMPORAL_VALIDITY_POLICY_VERSION",
    "TemporalValidityError",
    "validate_evidence_temporal",
    "validate_signal_temporal",
    "validate_snapshot_temporal_inputs",
])


def sha(path: Path) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


checks: dict[str, bool] = {}


worker_sha = sha(
    worker_path
)

temporal_sha = sha(
    temporal_path
)

requirements_sha = sha(
    requirements_path
)


checks["WORKER_SHA_EXACT"] = (
    worker_sha == EXPECTED_WORKER_SHA
)

checks["TEMPORAL_SHA_EXACT"] = (
    temporal_sha == EXPECTED_TEMPORAL_SHA
)

checks["REQUIREMENTS_SHA_EXACT"] = (
    requirements_sha == EXPECTED_REQUIREMENTS_SHA
)


worker_source = worker_path.read_text(
    encoding="utf-8-sig"
)

worker_tree = ast.parse(
    worker_source,
    filename=str(worker_path),
)


worker_versions: list[str] = []
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

                worker_versions.append(
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


imported_symbols: list[str] = []


if len(temporal_import_nodes) == 1:

    imported_symbols = sorted(
        alias.name
        for alias in temporal_import_nodes[0].names
    )


checks["WORKER_VERSION_EXACT"] = (
    worker_versions == ["2.35.1"]
)

checks["TEMPORAL_IMPORT_COUNT_EXACT"] = (
    len(temporal_import_nodes) == 1
)

checks["TEMPORAL_IMPORT_SYMBOLS_EXACT"] = (
    imported_symbols == EXPECTED_IMPORTS
)


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

            constants[target.id] = (
                node.value.value
            )


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
    implementation_revision
    == "R2"
)


failures = [
    name
    for name, value in checks.items()
    if not value
]


result = {
    "contract_version":
        "SM3_A12_EXISTING_IMAGE_CONTENT_VERIFY_V1",

    "check_count":
        len(checks),

    "pass_count":
        len(checks) - len(failures),

    "failure_count":
        len(failures),

    "failures":
        failures,

    "checks":
        checks,

    "worker_sha256":
        worker_sha,

    "temporal_sha256":
        temporal_sha,

    "requirements_sha256":
        requirements_sha,

    "worker_versions":
        worker_versions,

    "temporal_import_symbols":
        imported_symbols,

    "temporal_policy_version":
        policy_version,

    "temporal_engine_version":
        engine_version,

    "temporal_implementation_revision":
        implementation_revision,

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
    "CONTENT_VERIFY_CHECK_COUNT="
    + str(result["check_count"])
)

print(
    "CONTENT_VERIFY_PASS_COUNT="
    + str(result["pass_count"])
)

print(
    "CONTENT_VERIFY_FAILURE_COUNT="
    + str(result["failure_count"])
)

print(
    "WORKER_VERSION="
    + (
        worker_versions[0]
        if len(worker_versions) == 1
        else "INVALID"
    )
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
    "CONTENT_VERIFY_PASS="
    + str(result["verification_pass"])
)


if not result["verification_pass"]:

    raise SystemExit(1)