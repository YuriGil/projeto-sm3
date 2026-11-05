from __future__ import annotations

import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


engine_path = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
repair_dir = Path(sys.argv[3])
report_path = Path(sys.argv[4])
expected_engine_sha = sys.argv[5].lower()


def sha(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


repair_dir.mkdir(
    parents=True,
    exist_ok=True,
)


engine_sha_before = sha(
    engine_path
)


if engine_sha_before != expected_engine_sha:

    raise RuntimeError(
        "ENGINE_SOURCE_SHA_NOT_AUTHORIZED:"
        + engine_sha_before
    )


manifest_sha_before = sha(
    manifest_path
)


# ============================================================
# BACKUP EXACT ORIGINALS
# ============================================================

engine_backup = (
    repair_dir
    / (
        engine_path.name
        + ".before_"
        + engine_sha_before[:16]
        + ".bak"
    )
)

manifest_backup = (
    repair_dir
    / (
        manifest_path.name
        + ".before_"
        + manifest_sha_before[:16]
        + ".bak"
    )
)


shutil.copy2(
    engine_path,
    engine_backup,
)

shutil.copy2(
    manifest_path,
    manifest_backup,
)


# ============================================================
# LOAD ENGINE
# ============================================================

source = engine_path.read_text(
    encoding="utf-8-sig"
)


if "def proposal_format_schema(" in source:

    raise RuntimeError(
        "SCHEMA_REPAIR_ALREADY_PRESENT"
    )


call_start = source.find(
    "def call_model("
)


if call_start < 0:

    raise RuntimeError(
        "CALL_MODEL_FUNCTION_NOT_FOUND"
    )


next_function = source.find(
    "\ndef ",
    call_start + 1,
)


if next_function < 0:

    raise RuntimeError(
        "CALL_MODEL_FUNCTION_END_NOT_FOUND"
    )


call_source = source[
    call_start:
    next_function
]


# ============================================================
# JSON SCHEMA
#
# Deliberately constrains the structural blocker only.
# Other proposal fields remain controlled by the existing
# prompt + existing fail-closed validate_proposal().
# ============================================================

schema_function = '''def proposal_format_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "platforms": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "items": {
                    "type": "object",
                    "properties": {
                        "platform": {
                            "type": "string",
                            "enum": [
                                "INSTAGRAM",
                                "TIKTOK",
                            ],
                        },
                        "surface": {
                            "type": "string",
                            "enum": [
                                "REELS",
                                "FOR_YOU",
                            ],
                        },
                    },
                    "required": [
                        "platform",
                        "surface",
                    ],
                },
            },
        },
        "required": [
            "platforms",
        ],
    }
'''


# ============================================================
# PATCH call_model ONLY
# ============================================================

signature_anchor = (
    ") -> dict[str, Any]:\n"
    "    body = {\n"
)


if call_source.count(
    signature_anchor
) != 1:

    raise RuntimeError(
        "CALL_MODEL_BODY_ANCHOR_CARDINALITY_INVALID"
    )


call_source = call_source.replace(
    signature_anchor,
    (
        ") -> dict[str, Any]:\n"
        "    schema = proposal_format_schema()\n"
        "    body = {\n"
    ),
    1,
)


format_anchor = (
    '        "format": "json",'
)


if call_source.count(
    format_anchor
) != 1:

    raise RuntimeError(
        "FORMAT_JSON_ANCHOR_CARDINALITY_INVALID"
    )


call_source = call_source.replace(
    format_anchor,
    '        "format": schema,',
    1,
)


system_anchor = (
    '            {"role": "system", "content": prompt()},'
)


if call_source.count(
    system_anchor
) != 1:

    raise RuntimeError(
        "SYSTEM_PROMPT_ANCHOR_CARDINALITY_INVALID"
    )


system_replacement = (
    '            {"role": "system", "content": '
    'prompt() + '
    '"\\n\\nThe response must satisfy this JSON schema. '
    'Preserve every task-required field in addition to the '
    'constrained platform structure:\\n" + '
    'json.dumps(schema, ensure_ascii=False, separators=(",", ":"))},'
)


call_source = call_source.replace(
    system_anchor,
    system_replacement,
    1,
)


patched_source = (
    source[:call_start]
    + schema_function
    + "\n\n"
    + call_source
    + source[next_function:]
)


# ============================================================
# STATIC VALIDATION BEFORE WRITE
# ============================================================

tree = ast.parse(
    patched_source,
    filename=str(
        engine_path
    ),
)


functions = {
    node.name:
        node
    for node in tree.body
    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    )
}


if "proposal_format_schema" not in functions:

    raise RuntimeError(
        "SCHEMA_FUNCTION_NOT_MATERIALIZED"
    )


if "call_model" not in functions:

    raise RuntimeError(
        "CALL_MODEL_LOST_AFTER_PATCH"
    )


schema_fn = functions[
    "proposal_format_schema"
]

call_fn = functions[
    "call_model"
]


# Must contain schema = proposal_format_schema()
schema_binding_count = 0

format_schema_count = 0

system_schema_reference_count = 0


for node in ast.walk(
    call_fn
):

    if isinstance(
        node,
        ast.Assign,
    ):

        if (
            len(
                node.targets
            )
            == 1
            and isinstance(
                node.targets[0],
                ast.Name,
            )
            and node.targets[0].id
            == "schema"
            and isinstance(
                node.value,
                ast.Call,
            )
            and isinstance(
                node.value.func,
                ast.Name,
            )
            and node.value.func.id
            == "proposal_format_schema"
        ):

            schema_binding_count += 1


    if isinstance(
        node,
        ast.Dict,
    ):

        keys = []


        for key in node.keys:

            if (
                isinstance(
                    key,
                    ast.Constant,
                )
                and isinstance(
                    key.value,
                    str,
                )
            ):

                keys.append(
                    key.value
                )

            else:

                keys.append(
                    None
                )


        for index, key in enumerate(
            keys
        ):

            if key == "format":

                value = node.values[
                    index
                ]

                if (
                    isinstance(
                        value,
                        ast.Name,
                    )
                    and value.id
                    == "schema"
                ):

                    format_schema_count += 1


# Simple textual confirmation that schema is also grounded
# in the system instruction.
patched_call_text = ast.get_source_segment(
    patched_source,
    call_fn,
) or ""


if (
    "The response must satisfy this JSON schema"
    in patched_call_text
):

    system_schema_reference_count = 1


static_checks = [
    schema_binding_count == 1,
    format_schema_count == 1,
    system_schema_reference_count == 1,
    '"format": "json"' not in patched_call_text,
]


static_validation_pass = all(
    static_checks
)


if not static_validation_pass:

    raise RuntimeError(
        "SCHEMA_REPAIR_STATIC_VALIDATION_FAILED"
    )


# ============================================================
# WRITE ENGINE
# ============================================================

engine_path.write_text(
    patched_source,
    encoding="utf-8",
)


engine_sha_after = sha(
    engine_path
)


if (
    engine_sha_after
    == engine_sha_before
):

    raise RuntimeError(
        "ENGINE_SHA_DID_NOT_CHANGE"
    )


# ============================================================
# UPDATE MANIFEST ENGINE HASH ONLY
# ============================================================

manifest = load_json(
    manifest_path
)


artifacts = manifest.get(
    "artifacts"
)


if not isinstance(
    artifacts,
    list,
):

    raise RuntimeError(
        "MANIFEST_ARTIFACTS_INVALID"
    )


matches = []


for artifact in artifacts:

    if not isinstance(
        artifact,
        dict,
    ):
        continue


    if str(
        artifact.get(
            "file_name",
            "",
        )
    ) == engine_path.name:

        matches.append(
            artifact
        )


if len(
    matches
) != 1:

    raise RuntimeError(
        "MANIFEST_ENGINE_ENTRY_CARDINALITY_INVALID:"
        + str(
            len(
                matches
            )
        )
    )


engine_entry = matches[0]

manifest_engine_sha_before = str(
    engine_entry.get(
        "sha256",
        "",
    )
)


engine_entry[
    "sha256"
] = engine_sha_after


engine_size = engine_path.stat().st_size


for size_key in (
    "size_bytes",
    "bytes",
):

    if size_key in engine_entry:

        engine_entry[
            size_key
        ] = engine_size


manifest_path.write_text(
    json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)


manifest_sha_after = sha(
    manifest_path
)


# ============================================================
# READ BACK / FINAL STATIC PROOF
# ============================================================

persisted_source = engine_path.read_text(
    encoding="utf-8-sig"
)

ast.parse(
    persisted_source,
    filename=str(
        engine_path
    ),
)


persisted_manifest = load_json(
    manifest_path
)


persisted_entries = [
    item
    for item in persisted_manifest.get(
        "artifacts",
        [],
    )
    if isinstance(
        item,
        dict,
    )
    and item.get(
        "file_name"
    )
    == engine_path.name
]


manifest_update_pass = (
    len(
        persisted_entries
    )
    == 1
    and str(
        persisted_entries[
            0
        ].get(
            "sha256",
            "",
        )
    ).lower()
    == engine_sha_after.lower()
)


repair_pass = all([
    static_validation_pass,
    manifest_update_pass,
    sha(
        engine_path
    )
    == engine_sha_after,
])


if not repair_pass:

    raise RuntimeError(
        "SCHEMA_REPAIR_FINAL_VERIFY_FAILED"
    )


# ============================================================
# REPORT
# ============================================================

report = {
    "contract_version":
        "SM3_A11_A10_SCHEMA_CONSTRAINED_LOCAL_MODEL_REPAIR_V1",

    "repair_revision":
        3,

    "engine_sha256_before":
        engine_sha_before,

    "engine_sha256_after":
        engine_sha_after,

    "manifest_sha256_before":
        manifest_sha_before,

    "manifest_sha256_after":
        manifest_sha_after,

    "manifest_engine_sha256_before":
        manifest_engine_sha_before,

    "manifest_engine_sha256_after":
        engine_sha_after,

    "engine_backup":
        str(
            engine_backup
        ),

    "manifest_backup":
        str(
            manifest_backup
        ),

    "schema_contract": {
        "root_type":
            "object",

        "platforms_required":
            True,

        "platforms_min_items":
            2,

        "platforms_max_items":
            2,

        "platform_enum": [
            "INSTAGRAM",
            "TIKTOK",
        ],

        "surface_enum": [
            "REELS",
            "FOR_YOU",
        ],

        "platform_and_surface_required_per_item":
            True,
    },

    "ollama_endpoint_unchanged":
        "/api/chat",

    "model_policy_unchanged":
        True,

    "temperature_unchanged":
        True,

    "seed_unchanged":
        True,

    "maximum_attempts_unchanged":
        True,

    "validator_unchanged":
        True,

    "fail_closed_unchanged":
        True,

    "production_state_mutation_performed":
        False,

    "repair_pass":
        repair_pass,
}


report_path.write_text(
    json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)


print(
    "ENGINE_SHA256_BEFORE="
    + engine_sha_before
)

print(
    "ENGINE_SHA256_AFTER="
    + engine_sha_after
)

print(
    "MANIFEST_SHA256_BEFORE="
    + manifest_sha_before
)

print(
    "MANIFEST_SHA256_AFTER="
    + manifest_sha_after
)

print(
    "MANIFEST_ENGINE_ENTRY_UPDATE_PASS="
    + str(
        manifest_update_pass
    )
)

print(
    "SCHEMA_BINDING_COUNT="
    + str(
        schema_binding_count
    )
)

print(
    "FORMAT_SCHEMA_COUNT="
    + str(
        format_schema_count
    )
)

print(
    "SYSTEM_SCHEMA_REFERENCE_COUNT="
    + str(
        system_schema_reference_count
    )
)

print(
    "STATIC_VALIDATION_PASS="
    + str(
        static_validation_pass
    )
)

print(
    "VALIDATOR_MUTATED=False"
)

print(
    "FAIL_CLOSED_MUTATED=False"
)

print(
    "MAXIMUM_ATTEMPTS_MUTATED=False"
)

print(
    "PRODUCTION_STATE_MUTATION_PERFORMED=False"
)

print(
    "REPAIR_PASS="
    + str(
        repair_pass
    )
)