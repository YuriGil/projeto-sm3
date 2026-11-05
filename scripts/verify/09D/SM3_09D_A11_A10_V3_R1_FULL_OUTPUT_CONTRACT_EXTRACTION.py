from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


engine_path = Path(sys.argv[1])
challenge_path = Path(sys.argv[2])
report_path = Path(sys.argv[3])


def sha(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def source_of(
    source: str,
    node: ast.AST,
) -> str:

    value = ast.get_source_segment(
        source,
        node,
    )

    if value:
        return value.strip()

    try:
        return ast.unparse(node)
    except Exception:
        return ""


engine_source = engine_path.read_text(
    encoding="utf-8-sig"
)

challenge = json.loads(
    challenge_path.read_text(
        encoding="utf-8-sig"
    )
)

tree = ast.parse(
    engine_source,
    filename=str(engine_path),
)


functions = {}

module_constants = {}


for node in tree.body:

    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):

        functions[
            node.name
        ] = node


    elif isinstance(
        node,
        ast.Assign,
    ):

        for target in node.targets:

            if not isinstance(
                target,
                ast.Name,
            ):
                continue


            try:
                value = ast.literal_eval(
                    node.value
                )

            except Exception:
                continue


            module_constants[
                target.id
            ] = {
                "line":
                    getattr(
                        node,
                        "lineno",
                        None,
                    ),

                "value":
                    value,
            }


required_functions = [
    "prompt",
    "validate_proposal",
    "proposal_format_schema",
]


missing_functions = [
    name
    for name in required_functions
    if name not in functions
]


print(
    "MISSING_FUNCTION_COUNT="
    + str(
        len(
            missing_functions
        )
    )
)


for name in missing_functions:

    print(
        "MISSING_FUNCTION="
        + name
    )


if missing_functions:
    raise SystemExit(1)


# ============================================================
# 1. FUNCTION SOURCES
# ============================================================

function_sources = {}


for name in required_functions:

    node = functions[
        name
    ]

    text = source_of(
        engine_source,
        node,
    )

    function_sources[
        name
    ] = {
        "line_start":
            getattr(
                node,
                "lineno",
                None,
            ),

        "line_end":
            getattr(
                node,
                "end_lineno",
                None,
            ),

        "source":
            text,
    }


print("")
print("=== PROMPT FUNCTION ===")

print(
    "PROMPT_LINES="
    + str(
        function_sources[
            "prompt"
        ][
            "line_start"
        ]
    )
    + "-"
    + str(
        function_sources[
            "prompt"
        ][
            "line_end"
        ]
    )
)

print(
    "PROMPT_SOURCE_BEGIN"
)

print(
    function_sources[
        "prompt"
    ][
        "source"
    ]
)

print(
    "PROMPT_SOURCE_END"
)


print("")
print("=== VALIDATE_PROPOSAL FUNCTION ===")

print(
    "VALIDATE_PROPOSAL_LINES="
    + str(
        function_sources[
            "validate_proposal"
        ][
            "line_start"
        ]
    )
    + "-"
    + str(
        function_sources[
            "validate_proposal"
        ][
            "line_end"
        ]
    )
)

print(
    "VALIDATE_PROPOSAL_SOURCE_BEGIN"
)

print(
    function_sources[
        "validate_proposal"
    ][
        "source"
    ]
)

print(
    "VALIDATE_PROPOSAL_SOURCE_END"
)


print("")
print("=== CURRENT PARTIAL SCHEMA ===")

print(
    "PROPOSAL_FORMAT_SCHEMA_SOURCE_BEGIN"
)

print(
    function_sources[
        "proposal_format_schema"
    ][
        "source"
    ]
)

print(
    "PROPOSAL_FORMAT_SCHEMA_SOURCE_END"
)


# ============================================================
# 2. VALIDATOR REFERENCED FIELD NAMES
# ============================================================

validator = functions[
    "validate_proposal"
]


string_literals = []


for node in ast.walk(
    validator
):

    if (
        isinstance(
            node,
            ast.Constant,
        )
        and isinstance(
            node.value,
            str,
        )
    ):

        string_literals.append(
            node.value
        )


unique_strings = sorted(
    set(
        string_literals
    )
)


print("")
print("=== VALIDATOR STRING LITERALS ===")

print(
    "VALIDATOR_STRING_LITERAL_COUNT="
    + str(
        len(
            unique_strings
        )
    )
)


for value in unique_strings:

    print(
        "VALIDATOR_STRING_LITERAL="
        + value.replace(
            "\n",
            "\\n",
        )
    )


# ============================================================
# 3. .get("field") USAGE
# ============================================================

get_fields = []


for node in ast.walk(
    validator
):

    if not isinstance(
        node,
        ast.Call,
    ):
        continue


    if not isinstance(
        node.func,
        ast.Attribute,
    ):
        continue


    if node.func.attr != "get":
        continue


    if not node.args:
        continue


    key = node.args[0]


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

        get_fields.append({
            "line":
                getattr(
                    node,
                    "lineno",
                    None,
                ),

            "field":
                key.value,

            "expression":
                source_of(
                    engine_source,
                    node,
                ),
        })


print("")
print("=== VALIDATOR GET FIELDS ===")

print(
    "VALIDATOR_GET_FIELD_COUNT="
    + str(
        len(
            get_fields
        )
    )
)


for item in get_fields:

    print(
        "VALIDATOR_GET_FIELD="
        + str(
            item[
                "line"
            ]
        )
        + "|"
        + item[
            "field"
        ]
        + "|"
        + item[
            "expression"
        ]
    )


# ============================================================
# 4. SUBSCRIPT STRING FIELD USAGE
# ============================================================

subscript_fields = []


for node in ast.walk(
    validator
):

    if not isinstance(
        node,
        ast.Subscript,
    ):
        continue


    key = node.slice


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

        subscript_fields.append({
            "line":
                getattr(
                    node,
                    "lineno",
                    None,
                ),

            "field":
                key.value,

            "expression":
                source_of(
                    engine_source,
                    node,
                ),
        })


print("")
print("=== VALIDATOR SUBSCRIPT FIELDS ===")

print(
    "VALIDATOR_SUBSCRIPT_FIELD_COUNT="
    + str(
        len(
            subscript_fields
        )
    )
)


for item in subscript_fields:

    print(
        "VALIDATOR_SUBSCRIPT_FIELD="
        + str(
            item[
                "line"
            ]
        )
        + "|"
        + item[
            "field"
        ]
        + "|"
        + item[
            "expression"
        ]
    )


# ============================================================
# 5. ERROR APPENDS
# ============================================================

error_expressions = []


for node in ast.walk(
    validator
):

    if not isinstance(
        node,
        ast.Call,
    ):
        continue


    if not isinstance(
        node.func,
        ast.Attribute,
    ):
        continue


    if node.func.attr != "append":
        continue


    if not node.args:
        continue


    expression = source_of(
        engine_source,
        node.args[0],
    )


    if not expression:
        continue


    error_expressions.append({
        "line":
            getattr(
                node,
                "lineno",
                None,
            ),

        "expression":
            expression,
    })


print("")
print("=== VALIDATOR ERROR EXPRESSIONS ===")

print(
    "VALIDATOR_ERROR_EXPRESSION_COUNT="
    + str(
        len(
            error_expressions
        )
    )
)


for item in error_expressions:

    print(
        "VALIDATOR_ERROR_EXPRESSION="
        + str(
            item[
                "line"
            ]
        )
        + "|"
        + item[
            "expression"
        ]
    )


# ============================================================
# 6. MODULE CONSTANTS RELEVANT TO OUTPUT CONTRACT
# ============================================================

relevant_constants = {}


tokens = (
    "CONTRACT",
    "SCOPE",
    "PLATFORM",
    "SURFACE",
    "TIMELINE",
    "SAFETY",
    "OUTPUT",
    "REVIEW",
    "PERFORMANCE",
)


for name, item in module_constants.items():

    upper_name = name.upper()


    if any(
        token in upper_name
        for token in tokens
    ):

        relevant_constants[
            name
        ] = item


print("")
print("=== RELEVANT MODULE CONSTANTS ===")

print(
    "RELEVANT_CONSTANT_COUNT="
    + str(
        len(
            relevant_constants
        )
    )
)


for name in sorted(
    relevant_constants
):

    item = relevant_constants[
        name
    ]

    print(
        "RELEVANT_CONSTANT="
        + name
        + "|LINE="
        + str(
            item[
                "line"
            ]
        )
        + "|VALUE="
        + json.dumps(
            item[
                "value"
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
    )


# ============================================================
# 7. CHALLENGE CONTRACT FIELDS
# ============================================================

print("")
print("=== CHALLENGE CONTRACT ===")

print(
    "CHALLENGE_ID="
    + str(
        challenge.get(
            "challenge_id"
        )
    )
)


print(
    "CHALLENGE_TOP_LEVEL_KEYS="
    + "|".join(
        sorted(
            str(
                key
            )
            for key
            in challenge.keys()
        )
    )
)


for key, value in challenge.items():

    lowered = str(
        key
    ).lower()


    if any(
        token in lowered
        for token in (
            "contract",
            "output",
            "safety",
            "platform",
            "review",
            "timeline",
            "model",
        )
    ):

        print(
            "CHALLENGE_RELEVANT_FIELD="
            + str(
                key
            )
            + "|"
            + json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )
        )


# ============================================================
# 8. REPORT
# ============================================================

report = {
    "contract_version":
        "SM3_A11_A10_FULL_OUTPUT_CONTRACT_EXTRACTION_V1",

    "engine_sha256":
        sha(
            engine_path
        ),

    "challenge_sha256":
        sha(
            challenge_path
        ),

    "function_sources":
        function_sources,

    "validator_string_literals":
        unique_strings,

    "validator_get_fields":
        get_fields,

    "validator_subscript_fields":
        subscript_fields,

    "validator_error_expressions":
        error_expressions,

    "relevant_module_constants":
        relevant_constants,

    "challenge_id":
        challenge.get(
            "challenge_id"
        ),

    "challenge_top_level_keys":
        sorted(
            str(
                key
            )
            for key
            in challenge.keys()
        ),

    "source_mutation_performed":
        False,

    "model_called":
        False,

    "production_state_mutation_performed":
        False,

    "extraction_complete":
        True,

    "next_action":
        "BUILD_FULL_OUTPUT_JSON_SCHEMA_AND_RERUN_A11_A10",
}


report_path.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print("")
print("=== FINAL V3-R1 ===")

print(
    "EXTRACTION_COMPLETE=True"
)

print(
    "SOURCE_MUTATION_PERFORMED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "PRODUCTION_STATE_MUTATION_PERFORMED=False"
)

print(
    "NEXT_ACTION=BUILD_FULL_OUTPUT_JSON_SCHEMA_AND_RERUN_A11_A10"
)