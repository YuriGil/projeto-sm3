from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


engine_path = Path(sys.argv[1])
runner_path = Path(sys.argv[2])
report_path = Path(sys.argv[3])


engine_source = engine_path.read_text(
    encoding="utf-8-sig"
)

runner_source = runner_path.read_text(
    encoding="utf-8-sig"
)

engine_lines = engine_source.splitlines()
runner_lines = runner_source.splitlines()


def sha(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def source_of(
    source: str,
    node: ast.AST,
) -> str:

    result = ast.get_source_segment(
        source,
        node,
    )

    if result:
        return result.strip()

    try:
        return ast.unparse(node)
    except Exception:
        return ""


def call_name(
    node: ast.Call,
) -> str:

    try:
        return ast.unparse(
            node.func
        )
    except Exception:
        return ""


tree = ast.parse(
    engine_source,
    filename=str(engine_path),
)


keywords = (
    "ollama",
    "11434",
    "/api/chat",
    "/api/generate",
    "llama",
    "local_model",
    "local model",
    "requests",
    "urllib",
    "urlopen",
    "subprocess",
)


# ============================================================
# 1. IMPORTS
# ============================================================

imports = []


for node in tree.body:

    if isinstance(
        node,
        (
            ast.Import,
            ast.ImportFrom,
        ),
    ):

        text = source_of(
            engine_source,
            node,
        )

        lowered = text.lower()

        if any(
            token in lowered
            for token in (
                "request",
                "urllib",
                "http",
                "subprocess",
                "ollama",
            )
        ):

            imports.append({
                "line":
                    getattr(
                        node,
                        "lineno",
                        None,
                    ),

                "source":
                    text,
            })


# ============================================================
# 2. FUNCTION INVENTORY
# ============================================================

functions = []


for node in tree.body:

    if not isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        continue


    text = source_of(
        engine_source,
        node,
    )

    lowered = text.lower()


    string_values = []


    for child in ast.walk(
        node
    ):

        if (
            isinstance(
                child,
                ast.Constant,
            )
            and isinstance(
                child.value,
                str,
            )
        ):

            string_values.append(
                child.value
            )


    haystack = (
        node.name.lower()
        + "\n"
        + lowered
        + "\n"
        + "\n".join(
            value.lower()
            for value
            in string_values
        )
    )


    if any(
        token in haystack
        for token in keywords
    ):

        functions.append({
            "name":
                node.name,

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
        })


# ============================================================
# 3. CALL SITES
# ============================================================

calls = []


for node in ast.walk(
    tree
):

    if not isinstance(
        node,
        ast.Call,
    ):
        continue


    text = source_of(
        engine_source,
        node,
    )

    func = call_name(
        node
    )

    combined = (
        func
        + "\n"
        + text
    ).lower()


    if any(
        token in combined
        for token in keywords
    ):

        calls.append({
            "line":
                getattr(
                    node,
                    "lineno",
                    None,
                ),

            "function":
                func,

            "source":
                text,
        })


# ============================================================
# 4. DICTS THAT LOOK LIKE LOCAL MODEL PAYLOADS
# ============================================================

payloads = []


for node in ast.walk(
    tree
):

    if not isinstance(
        node,
        ast.Dict,
    ):
        continue


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


    interesting = {
        "model",
        "prompt",
        "messages",
        "stream",
        "format",
        "options",
    }


    if not (
        set(keys)
        & interesting
    ):

        continue


    payloads.append({
        "line":
            getattr(
                node,
                "lineno",
                None,
            ),

        "keys":
            keys,

        "source":
            source_of(
                engine_source,
                node,
            ),
    })


# ============================================================
# 5. PLATFORM VALIDATOR FUNCTION
# ============================================================

validator_functions = []


for node in tree.body:

    if not isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        continue


    text = source_of(
        engine_source,
        node,
    )


    if (
        "PLATFORM_SET_INVALID"
        in text
        or "PLATFORM_SET_MISMATCH"
        in text
    ):

        validator_functions.append({
            "name":
                node.name,

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
        })


# ============================================================
# 6. RUNNER PYTHON INVOCATION
# ============================================================

runner_hits = []


for index, line in enumerate(
    runner_lines,
    start=1,
):

    lowered = line.lower()


    if (
        "python" in lowered
        or "minimal_feedback_engine" in lowered
    ):

        start = max(
            1,
            index - 8,
        )

        end = min(
            len(
                runner_lines
            ),
            index + 12,
        )


        context = []


        for line_number in range(
            start,
            end + 1,
        ):

            context.append({
                "line":
                    line_number,

                "text":
                    runner_lines[
                        line_number - 1
                    ],
            })


        runner_hits.append({
            "hit_line":
                index,

            "context":
                context,
        })


# ============================================================
# 7. OUTPUT
# ============================================================

print(
    "ENGINE_SHA256="
    + sha(
        engine_path
    )
)

print(
    "RUNNER_SHA256="
    + sha(
        runner_path
    )
)


print("")
print("=== LOCAL MODEL IMPORTS ===")

print(
    "LOCAL_MODEL_IMPORT_COUNT="
    + str(
        len(
            imports
        )
    )
)


for item in imports:

    print(
        "LOCAL_MODEL_IMPORT="
        + str(
            item[
                "line"
            ]
        )
        + "|"
        + item[
            "source"
        ].replace(
            "\n",
            " ",
        )
    )


print("")
print("=== LOCAL MODEL FUNCTIONS ===")

print(
    "LOCAL_MODEL_FUNCTION_COUNT="
    + str(
        len(
            functions
        )
    )
)


for item in functions:

    print("")

    print(
        "LOCAL_MODEL_FUNCTION="
        + item[
            "name"
        ]
        + "|LINES="
        + str(
            item[
                "line_start"
            ]
        )
        + "-"
        + str(
            item[
                "line_end"
            ]
        )
    )

    print(
        "LOCAL_MODEL_FUNCTION_SOURCE_BEGIN"
    )

    print(
        item[
            "source"
        ]
    )

    print(
        "LOCAL_MODEL_FUNCTION_SOURCE_END"
    )


print("")
print("=== LOCAL MODEL CALL SITES ===")

print(
    "LOCAL_MODEL_CALL_COUNT="
    + str(
        len(
            calls
        )
    )
)


for item in calls:

    print("")

    print(
        "LOCAL_MODEL_CALL="
        + str(
            item[
                "line"
            ]
        )
        + "|"
        + item[
            "function"
        ]
    )

    print(
        "LOCAL_MODEL_CALL_SOURCE="
        + item[
            "source"
        ].replace(
            "\n",
            " ",
        )
    )


print("")
print("=== LOCAL MODEL PAYLOADS ===")

print(
    "LOCAL_MODEL_PAYLOAD_COUNT="
    + str(
        len(
            payloads
        )
    )
)


for item in payloads:

    print("")

    print(
        "LOCAL_MODEL_PAYLOAD="
        + str(
            item[
                "line"
            ]
        )
        + "|KEYS="
        + "|".join(
            item[
                "keys"
            ]
        )
    )

    print(
        "LOCAL_MODEL_PAYLOAD_SOURCE_BEGIN"
    )

    print(
        item[
            "source"
        ]
    )

    print(
        "LOCAL_MODEL_PAYLOAD_SOURCE_END"
    )


print("")
print("=== VALIDATOR FUNCTION ===")


for item in validator_functions:

    print(
        "VALIDATOR_FUNCTION="
        + item[
            "name"
        ]
        + "|LINES="
        + str(
            item[
                "line_start"
            ]
        )
        + "-"
        + str(
            item[
                "line_end"
            ]
        )
    )


print("")
print("=== RUNNER INVOCATION ===")


for hit in runner_hits:

    print(
        "RUNNER_HIT_LINE="
        + str(
            hit[
                "hit_line"
            ]
        )
    )


    for row in hit[
        "context"
    ]:

        print(
            "RUNNER_CONTEXT="
            + str(
                row[
                    "line"
                ]
            )
            + "|"
            + row[
                "text"
            ]
        )


report = {
    "contract_version":
        "SM3_A11_A10_LOCAL_MODEL_INVOCATION_SOURCE_MAP_V1",

    "engine_sha256":
        sha(
            engine_path
        ),

    "runner_sha256":
        sha(
            runner_path
        ),

    "imports":
        imports,

    "local_model_functions":
        functions,

    "local_model_calls":
        calls,

    "local_model_payloads":
        payloads,

    "validator_functions":
        validator_functions,

    "runner_invocation_hits":
        runner_hits,

    "model_called":
        False,

    "source_mutation_performed":
        False,

    "diagnostic_complete":
        True,

    "next_action":
        "SCHEMA_CONSTRAINED_LOCAL_MODEL_REPAIR_AND_CHALLENGE_RERUN",
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
print("=== FINAL H2 ===")

print(
    "DIAGNOSTIC_COMPLETE=True"
)

print(
    "MODEL_CALLED=False"
)

print(
    "SOURCE_MUTATION_PERFORMED=False"
)

print(
    "NEXT_ACTION=SCHEMA_CONSTRAINED_LOCAL_MODEL_REPAIR_AND_CHALLENGE_RERUN"
)