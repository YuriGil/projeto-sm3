from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


engine_path = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
repair_dir = Path(sys.argv[3])
report_path = Path(sys.argv[4])

expected_engine_sha = sys.argv[5].lower()
expected_manifest_sha = sys.argv[6].lower()
expected_contract = sys.argv[7]
expected_challenge_id = sys.argv[8]


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


def node_offsets(
    source: str,
    node: ast.AST,
) -> tuple[int, int]:

    lines = source.splitlines(
        keepends=True
    )

    starts = []
    total = 0

    for line in lines:

        starts.append(
            total
        )

        total += len(
            line
        )


    start = (
        starts[
            node.lineno - 1
        ]
        + node.col_offset
    )

    end = (
        starts[
            node.end_lineno - 1
        ]
        + node.end_col_offset
    )

    return start, end


repair_dir.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# 1. SOURCE HASH AUTHORIZATION
# ============================================================

engine_sha_before = sha(
    engine_path
)

manifest_sha_before = sha(
    manifest_path
)


if engine_sha_before != expected_engine_sha:

    raise RuntimeError(
        "ENGINE_SHA_NOT_AUTHORIZED:"
        + engine_sha_before
    )


if manifest_sha_before != expected_manifest_sha:

    raise RuntimeError(
        "MANIFEST_SHA_NOT_AUTHORIZED:"
        + manifest_sha_before
    )


# ============================================================
# 2. BACKUPS
# ============================================================

engine_backup = (
    repair_dir
    / (
        engine_path.name
        + ".before_v4_"
        + engine_sha_before[:16]
        + ".bak"
    )
)

manifest_backup = (
    repair_dir
    / (
        manifest_path.name
        + ".before_v4_"
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
# 3. PARSE CURRENT V3 ENGINE
# ============================================================

source = engine_path.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(
    source,
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


required_functions = {
    "prompt",
    "proposal_format_schema",
    "call_model",
    "validate_proposal",
    "main",
}


missing = (
    required_functions
    - set(
        functions
    )
)


if missing:

    raise RuntimeError(
        "V4_REQUIRED_FUNCTION_MISSING:"
        + "|".join(
            sorted(
                missing
            )
        )
    )


# Freeze validator and prompt AST before patch.
validator_ast_before = ast.dump(
    functions[
        "validate_proposal"
    ],
    include_attributes=False,
)

prompt_ast_before = ast.dump(
    functions[
        "prompt"
    ],
    include_attributes=False,
)


# ============================================================
# 4. FULL OUTPUT JSON SCHEMA
# ============================================================

full_schema_function = r'''def proposal_format_schema(
    challenge_id: str,
    catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    candidate_ids = sorted(
        str(candidate_id)
        for candidate_id in catalog
        if str(candidate_id).strip()
    )

    if not candidate_ids:
        raise GateError(
            "A11_A10_FULL_SCHEMA_CATALOG_EMPTY"
        )

    candidate_variants: list[dict[str, Any]] = []

    for candidate_id in candidate_ids:
        candidate = catalog.get(candidate_id)

        if not isinstance(candidate, dict):
            raise GateError(
                "A11_A10_FULL_SCHEMA_CANDIDATE_INVALID:"
                + candidate_id
            )

        role = str(
            candidate.get(
                "role",
                "",
            )
        ).strip()

        if not role:
            raise GateError(
                "A11_A10_FULL_SCHEMA_CANDIDATE_ROLE_MISSING:"
                + candidate_id
            )

        candidate_variants.append({
            "type": "object",
            "properties": {
                "order": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 6,
                },
                "candidate_id": {
                    "type": "string",
                    "enum": [
                        candidate_id,
                    ],
                },
                "role": {
                    "type": "string",
                    "enum": [
                        role,
                    ],
                },
                "label": {
                    "type": "string",
                },
            },
            "required": [
                "order",
                "candidate_id",
                "role",
                "label",
            ],
            "additionalProperties": False,
        })

    timeline_schema = {
        "type": "array",
        "minItems": 3,
        "maxItems": 6,
        "items": {
            "oneOf": candidate_variants,
        },
    }

    def platform_schema(
        platform: str,
        surface: str,
    ) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": [
                        platform,
                    ],
                },
                "surface": {
                    "type": "string",
                    "enum": [
                        surface,
                    ],
                },
                "proposal_status": {
                    "type": "string",
                    "enum": [
                        "HUMAN_REVIEW_REQUIRED",
                    ],
                },
                "changed_from_baseline": {
                    "type": "boolean",
                    "enum": [
                        True,
                    ],
                },
                "social_performance_claimed": {
                    "type": "boolean",
                    "enum": [
                        False,
                    ],
                },
                "rationale_codes": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "string",
                        "minLength": 1,
                    },
                },
                "timeline": timeline_schema,
                "unresolved_limitations": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "string",
                        "minLength": 1,
                    },
                },
            },
            "required": [
                "platform",
                "surface",
                "proposal_status",
                "changed_from_baseline",
                "social_performance_claimed",
                "rationale_codes",
                "timeline",
                "unresolved_limitations",
            ],
            "additionalProperties": False,
        }

    return {
        "type": "object",
        "properties": {
            "contract_version": {
                "type": "string",
                "enum": [
                    PROPOSAL_CONTRACT,
                ],
            },
            "challenge_id": {
                "type": "string",
                "enum": [
                    challenge_id,
                ],
            },
            "model_diagnosis": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "pattern": "^[A-Z0-9_]{3,80}$",
                        },
                        "evidence_refs": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "string",
                                "minLength": 1,
                            },
                        },
                        "confidence_0_100": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 100,
                        },
                    },
                    "required": [
                        "code",
                        "evidence_refs",
                        "confidence_0_100",
                    ],
                    "additionalProperties": False,
                },
            },
            "platforms": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "items": {
                    "oneOf": [
                        platform_schema(
                            "INSTAGRAM",
                            "REELS",
                        ),
                        platform_schema(
                            "TIKTOK",
                            "FOR_YOU",
                        ),
                    ],
                },
            },
            "safety": {
                "type": "object",
                "properties": {
                    "render_performed": {
                        "type": "boolean",
                        "enum": [
                            False,
                        ],
                    },
                    "production_state_writes": {
                        "type": "integer",
                        "enum": [
                            0,
                        ],
                    },
                    "publication_performed": {
                        "type": "boolean",
                        "enum": [
                            False,
                        ],
                    },
                    "paid_provider_used": {
                        "type": "boolean",
                        "enum": [
                            False,
                        ],
                    },
                    "fake_metrics": {
                        "type": "integer",
                        "enum": [
                            0,
                        ],
                    },
                    "automatic_winner": {
                        "type": "boolean",
                        "enum": [
                            False,
                        ],
                    },
                },
                "required": [
                    "render_performed",
                    "production_state_writes",
                    "publication_performed",
                    "paid_provider_used",
                    "fake_metrics",
                    "automatic_winner",
                ],
                "additionalProperties": False,
            },
        },
        "required": [
            "contract_version",
            "challenge_id",
            "model_diagnosis",
            "platforms",
            "safety",
        ],
        "additionalProperties": False,
    }'''


# ============================================================
# 5. REBUILD call_model WITH FULL SCHEMA INPUTS
# ============================================================

new_call_model = r'''def call_model(
    base_url: str,
    model: str,
    evidence: dict[str, Any],
    challenge_id: str,
    catalog: dict[str, dict[str, Any]],
    timeout_seconds: int,
    maximum_output_tokens: int,
) -> dict[str, Any]:
    schema = proposal_format_schema(
        challenge_id,
        catalog,
    )

    body = {
        "model": model,
        "stream": False,
        "format": schema,
        "messages": [
            {
                "role": "system",
                "content": (
                    prompt()
                    + "\n\nThe Ollama format parameter contains the "
                    "authoritative complete JSON output schema. Return "
                    "every required field exactly once, use only catalog "
                    "candidate_id values, preserve candidate roles, and "
                    "satisfy the schema exactly."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    evidence,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        "options": {
            "temperature": 0,
            "seed": 42,
            "num_predict": maximum_output_tokens,
            "num_ctx": 4096,
        },
        "keep_alive": "10m",
    }

    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat",
        data=json.dumps(
            body,
            ensure_ascii=False,
        ).encode(
            "utf-8"
        ),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            envelope = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        return json.loads(
            envelope.get(
                "message",
                {},
            ).get(
                "content",
                "",
            )
        )

    except (
        urllib.error.URLError,
        TimeoutError,
    ) as exc:
        raise GateError(
            f"A11_A10_LOCAL_OLLAMA_UNREACHABLE:{type(exc).__name__}"
        ) from exc

    except (
        json.JSONDecodeError,
        TypeError,
        AttributeError,
    ) as exc:
        raise GateError(
            f"A11_A10_LOCAL_MODEL_JSON_INVALID:{type(exc).__name__}"
        ) from exc'''


# ============================================================
# 6. REPLACE EXACT FUNCTIONS USING AST SPANS
# ============================================================

replacements = []


for name, replacement in (
    (
        "proposal_format_schema",
        full_schema_function,
    ),
    (
        "call_model",
        new_call_model,
    ),
):

    node = functions[
        name
    ]

    start, end = node_offsets(
        source,
        node,
    )

    replacements.append(
        (
            start,
            end,
            replacement,
        )
    )


patched = source


for start, end, replacement in sorted(
    replacements,
    reverse=True,
):

    patched = (
        patched[:start]
        + replacement
        + patched[end:]
    )


# ============================================================
# 7. PASS challenge_id + by_id INTO call_model
# ============================================================

main_call_pattern = re.compile(
    r'(?P<prefix>'
    r'candidate\s*=\s*call_model\(\s*\n'
    r'\s*str\(policy\["base_url"\]\),\s*\n'
    r'\s*model,\s*\n'
    r'\s*attempt_evidence,\s*\n'
    r')'
    r'(?P<timeout>'
    r'\s*int\(policy\["timeout_seconds"\]\),'
    r')',
    re.MULTILINE,
)


matches = list(
    main_call_pattern.finditer(
        patched
    )
)


if len(
    matches
) != 1:

    raise RuntimeError(
        "MAIN_CALL_MODEL_ANCHOR_CARDINALITY_INVALID:"
        + str(
            len(
                matches
            )
        )
    )


patched = main_call_pattern.sub(
    (
        r'\g<prefix>'
        '                str(challenge["challenge_id"]),\n'
        '                by_id,\n'
        r'\g<timeout>'
    ),
    patched,
    count=1,
)


# ============================================================
# 8. PARSE / STATIC REATTACK
# ============================================================

patched_tree = ast.parse(
    patched,
    filename=str(
        engine_path
    ),
)


patched_functions = {
    node.name:
        node
    for node in patched_tree.body
    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    )
}


for name in required_functions:

    if name not in patched_functions:

        raise RuntimeError(
            "FUNCTION_LOST_AFTER_PATCH:"
            + name
        )


validator_ast_after = ast.dump(
    patched_functions[
        "validate_proposal"
    ],
    include_attributes=False,
)

prompt_ast_after = ast.dump(
    patched_functions[
        "prompt"
    ],
    include_attributes=False,
)


validator_unchanged = (
    validator_ast_before
    == validator_ast_after
)

prompt_unchanged = (
    prompt_ast_before
    == prompt_ast_after
)


# ============================================================
# 9. EXECUTE ONLY THE SCHEMA FUNCTION IN ISOLATION
# ============================================================

schema_node = patched_functions[
    "proposal_format_schema"
]


isolated = ast.Module(
    body=[
        schema_node,
    ],
    type_ignores=[],
)


class DummyGateError(
    RuntimeError
):
    pass


namespace = {
    "Any": Any,
    "GateError": DummyGateError,
    "PROPOSAL_CONTRACT": expected_contract,
}


exec(
    compile(
        isolated,
        "<schema-audit>",
        "exec",
    ),
    namespace,
)


schema_fn = namespace[
    "proposal_format_schema"
]


sample_catalog = {
    "CAN_STENCIL": {
        "role":
            "STENCIL_CONTEXT",

        "source_file":
            "source_a.mp4",
    },

    "CAN_FINAL": {
        "role":
            "FINAL_RESULT",

        "source_file":
            "source_b.mp4",
    },

    "CAN_PROCESS": {
        "role":
            "PROCESS_CONTEXT",

        "source_file":
            "source_c.mp4",
    },
}


sample_schema = schema_fn(
    expected_challenge_id,
    sample_catalog,
)


root_required = set(
    sample_schema.get(
        "required",
        [],
    )
)


expected_root_required = {
    "contract_version",
    "challenge_id",
    "model_diagnosis",
    "platforms",
    "safety",
}


root_required_pass = (
    root_required
    == expected_root_required
)


properties = sample_schema.get(
    "properties",
    {}
)


contract_enum_pass = (
    properties.get(
        "contract_version",
        {},
    ).get(
        "enum"
    )
    == [
        expected_contract,
    ]
)


challenge_enum_pass = (
    properties.get(
        "challenge_id",
        {},
    ).get(
        "enum"
    )
    == [
        expected_challenge_id,
    ]
)


diagnosis_schema = properties.get(
    "model_diagnosis",
    {},
)


diagnosis_pass = (
    diagnosis_schema.get(
        "type"
    )
    == "array"
    and diagnosis_schema.get(
        "minItems"
    )
    == 1
)


platform_schema = properties.get(
    "platforms",
    {},
)


platforms_pass = (
    platform_schema.get(
        "type"
    )
    == "array"
    and platform_schema.get(
        "minItems"
    )
    == 2
    and platform_schema.get(
        "maxItems"
    )
    == 2
)


platform_variants = (
    platform_schema
    .get(
        "items",
        {},
    )
    .get(
        "oneOf",
        [],
    )
)


platform_pairs = set()


for variant in platform_variants:

    variant_properties = variant.get(
        "properties",
        {},
    )

    p = (
        variant_properties.get(
            "platform",
            {},
        ).get(
            "enum",
            [],
        )
    )

    s = (
        variant_properties.get(
            "surface",
            {},
        ).get(
            "enum",
            [],
        )
    )

    if (
        len(p) == 1
        and len(s) == 1
    ):

        platform_pairs.add(
            (
                p[0],
                s[0],
            )
        )


platform_pairs_pass = (
    platform_pairs
    == {
        (
            "INSTAGRAM",
            "REELS",
        ),
        (
            "TIKTOK",
            "FOR_YOU",
        ),
    }
)


timeline_candidate_enum_pass = True


for variant in platform_variants:

    timeline = (
        variant
        .get(
            "properties",
            {},
        )
        .get(
            "timeline",
            {},
        )
    )

    if (
        timeline.get(
            "minItems"
        )
        != 3
        or timeline.get(
            "maxItems"
        )
        != 6
    ):

        timeline_candidate_enum_pass = False
        continue


    candidate_variants = (
        timeline
        .get(
            "items",
            {},
        )
        .get(
            "oneOf",
            [],
        )
    )


    observed_ids = set()


    for candidate_variant in candidate_variants:

        ids = (
            candidate_variant
            .get(
                "properties",
                {},
            )
            .get(
                "candidate_id",
                {},
            )
            .get(
                "enum",
                [],
            )
        )

        if len(ids) == 1:

            observed_ids.add(
                ids[0]
            )


    if observed_ids != set(
        sample_catalog
    ):

        timeline_candidate_enum_pass = False


safety_schema = properties.get(
    "safety",
    {},
)


expected_safety_required = {
    "render_performed",
    "production_state_writes",
    "publication_performed",
    "paid_provider_used",
    "fake_metrics",
    "automatic_winner",
}


safety_required_pass = (
    set(
        safety_schema.get(
            "required",
            [],
        )
    )
    == expected_safety_required
)


safety_properties = safety_schema.get(
    "properties",
    {},
)


safety_exact_pass = all([
    safety_properties.get(
        "render_performed",
        {},
    ).get(
        "enum"
    )
    == [
        False,
    ],

    safety_properties.get(
        "production_state_writes",
        {},
    ).get(
        "enum"
    )
    == [
        0,
    ],

    safety_properties.get(
        "publication_performed",
        {},
    ).get(
        "enum"
    )
    == [
        False,
    ],

    safety_properties.get(
        "paid_provider_used",
        {},
    ).get(
        "enum"
    )
    == [
        False,
    ],

    safety_properties.get(
        "fake_metrics",
        {},
    ).get(
        "enum"
    )
    == [
        0,
    ],

    safety_properties.get(
        "automatic_winner",
        {},
    ).get(
        "enum"
    )
    == [
        False,
    ],
])


# ============================================================
# 10. call_model SIGNATURE + main CALL
# ============================================================

call_fn = patched_functions[
    "call_model"
]


call_params = [
    arg.arg
    for arg in call_fn.args.args
]


expected_call_params = [
    "base_url",
    "model",
    "evidence",
    "challenge_id",
    "catalog",
    "timeout_seconds",
    "maximum_output_tokens",
]


call_signature_pass = (
    call_params
    == expected_call_params
)


main_fn = patched_functions[
    "main"
]


main_call_argument_pass = False


for node in ast.walk(
    main_fn
):

    if not isinstance(
        node,
        ast.Call,
    ):
        continue


    if not (
        isinstance(
            node.func,
            ast.Name,
        )
        and node.func.id
        == "call_model"
    ):

        continue


    texts = []


    for arg in node.args:

        try:
            texts.append(
                ast.unparse(
                    arg
                )
            )

        except Exception:
            texts.append(
                ""
            )


    if (
        len(
            texts
        )
        == 7
        and texts[
            3
        ]
        == "str(challenge['challenge_id'])"
        and texts[
            4
        ]
        == "by_id"
    ):

        main_call_argument_pass = True


# ============================================================
# 11. BEHAVIOR PRESERVATION CHECKS
# ============================================================

call_source = ast.get_source_segment(
    patched,
    call_fn,
) or ""


temperature_preserved = (
    '"temperature": 0'
    in call_source
)

seed_preserved = (
    '"seed": 42'
    in call_source
)

api_chat_preserved = (
    '"/api/chat"'
    in call_source
)

format_schema_present = (
    '"format": schema'
    in call_source
)

compact_schema_prompt_pass = (
    "authoritative complete JSON output schema"
    in call_source
)


static_checks = [
    validator_unchanged,
    prompt_unchanged,
    root_required_pass,
    contract_enum_pass,
    challenge_enum_pass,
    diagnosis_pass,
    platforms_pass,
    platform_pairs_pass,
    timeline_candidate_enum_pass,
    safety_required_pass,
    safety_exact_pass,
    call_signature_pass,
    main_call_argument_pass,
    temperature_preserved,
    seed_preserved,
    api_chat_preserved,
    format_schema_present,
    compact_schema_prompt_pass,
]


static_validation_pass = all(
    static_checks
)


if not static_validation_pass:

    details = {
        "validator_unchanged":
            validator_unchanged,

        "prompt_unchanged":
            prompt_unchanged,

        "root_required_pass":
            root_required_pass,

        "contract_enum_pass":
            contract_enum_pass,

        "challenge_enum_pass":
            challenge_enum_pass,

        "diagnosis_pass":
            diagnosis_pass,

        "platforms_pass":
            platforms_pass,

        "platform_pairs_pass":
            platform_pairs_pass,

        "timeline_candidate_enum_pass":
            timeline_candidate_enum_pass,

        "safety_required_pass":
            safety_required_pass,

        "safety_exact_pass":
            safety_exact_pass,

        "call_signature_pass":
            call_signature_pass,

        "main_call_argument_pass":
            main_call_argument_pass,

        "temperature_preserved":
            temperature_preserved,

        "seed_preserved":
            seed_preserved,

        "api_chat_preserved":
            api_chat_preserved,

        "format_schema_present":
            format_schema_present,

        "compact_schema_prompt_pass":
            compact_schema_prompt_pass,
    }

    raise RuntimeError(
        "V4_STATIC_VALIDATION_FAILED:"
        + json.dumps(
            details,
            sort_keys=True,
        )
    )


# ============================================================
# 12. WRITE ENGINE
# ============================================================

engine_path.write_text(
    patched,
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
        "V4_ENGINE_SHA_UNCHANGED"
    )


# ============================================================
# 13. UPDATE MANIFEST ENGINE ENTRY ONLY
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


matches = [
    item
    for item in artifacts
    if isinstance(
        item,
        dict,
    )
    and item.get(
        "file_name"
    )
    == engine_path.name
]


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


engine_entry = matches[
    0
]


manifest_engine_sha_before = str(
    engine_entry.get(
        "sha256",
        "",
    )
)


engine_entry[
    "sha256"
] = engine_sha_after


for size_key in (
    "size_bytes",
    "bytes",
):

    if size_key in engine_entry:

        engine_entry[
            size_key
        ] = engine_path.stat().st_size


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


persisted_manifest = load_json(
    manifest_path
)


persisted_matches = [
    item
    for item
    in persisted_manifest.get(
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
        persisted_matches
    )
    == 1
    and str(
        persisted_matches[
            0
        ].get(
            "sha256",
            "",
        )
    ).lower()
    == engine_sha_after
)


if not manifest_update_pass:

    raise RuntimeError(
        "V4_MANIFEST_UPDATE_FAILED"
    )


# ============================================================
# 14. FINAL PARSE
# ============================================================

ast.parse(
    engine_path.read_text(
        encoding="utf-8-sig"
    ),
    filename=str(
        engine_path
    ),
)


repair_pass = all([
    static_validation_pass,
    manifest_update_pass,
])


# ============================================================
# 15. REPORT
# ============================================================

report = {
    "contract_version":
        "SM3_A11_A10_FULL_OUTPUT_SCHEMA_REPAIR_V1",

    "repair_revision":
        4,

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

    "proposal_contract":
        expected_contract,

    "challenge_id":
        expected_challenge_id,

    "validator_unchanged":
        validator_unchanged,

    "prompt_unchanged":
        prompt_unchanged,

    "root_required_pass":
        root_required_pass,

    "platform_pairs_pass":
        platform_pairs_pass,

    "timeline_candidate_catalog_constrained":
        timeline_candidate_enum_pass,

    "safety_exact_pass":
        safety_exact_pass,

    "call_signature_pass":
        call_signature_pass,

    "main_call_argument_pass":
        main_call_argument_pass,

    "temperature_preserved":
        temperature_preserved,

    "seed_preserved":
        seed_preserved,

    "api_chat_preserved":
        api_chat_preserved,

    "maximum_attempts_policy_mutated":
        False,

    "fail_closed_mutated":
        False,

    "production_state_mutation_performed":
        False,

    "engine_backup":
        str(
            engine_backup
        ),

    "manifest_backup":
        str(
            manifest_backup
        ),

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
    "VALIDATOR_UNCHANGED="
    + str(
        validator_unchanged
    )
)

print(
    "PROMPT_UNCHANGED="
    + str(
        prompt_unchanged
    )
)

print(
    "ROOT_REQUIRED_PASS="
    + str(
        root_required_pass
    )
)

print(
    "CONTRACT_ENUM_PASS="
    + str(
        contract_enum_pass
    )
)

print(
    "CHALLENGE_ENUM_PASS="
    + str(
        challenge_enum_pass
    )
)

print(
    "DIAGNOSIS_SCHEMA_PASS="
    + str(
        diagnosis_pass
    )
)

print(
    "PLATFORMS_SCHEMA_PASS="
    + str(
        platforms_pass
    )
)

print(
    "PLATFORM_PAIRS_PASS="
    + str(
        platform_pairs_pass
    )
)

print(
    "TIMELINE_CATALOG_CONSTRAINT_PASS="
    + str(
        timeline_candidate_enum_pass
    )
)

print(
    "SAFETY_SCHEMA_PASS="
    + str(
        safety_exact_pass
    )
)

print(
    "CALL_SIGNATURE_PASS="
    + str(
        call_signature_pass
    )
)

print(
    "MAIN_CALL_ARGUMENT_PASS="
    + str(
        main_call_argument_pass
    )
)

print(
    "TEMPERATURE_PRESERVED="
    + str(
        temperature_preserved
    )
)

print(
    "SEED_PRESERVED="
    + str(
        seed_preserved
    )
)

print(
    "API_CHAT_PRESERVED="
    + str(
        api_chat_preserved
    )
)

print(
    "MANIFEST_UPDATE_PASS="
    + str(
        manifest_update_pass
    )
)

print(
    "STATIC_VALIDATION_PASS="
    + str(
        static_validation_pass
    )
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