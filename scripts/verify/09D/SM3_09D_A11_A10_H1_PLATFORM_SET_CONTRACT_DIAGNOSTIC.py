from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any


root = Path(sys.argv[1])
report_path = Path(sys.argv[2])


challenge_path = root / "SM3_09D_A11_A10_MINIMAL_FEEDBACK_CHALLENGE.json"
engine_path = root / "SM3_09D_A11_A10_MINIMAL_FEEDBACK_ENGINE.py"
runner_path = root / "SM3_09D_A11_A10_RUN_MINIMAL_FEEDBACK_CHALLENGE.ps1"
readme_path = root / "SM3_09D_A11_A10_MINIMAL_FEEDBACK_README.txt"


evidence_paths = [
    root / "SM3_09D_A11_A9_QUALITY_AWARE_SOURCE_SELECTOR_V1.json",
    root / "SM3_09D_A11_A9_INSTAGRAM_REELS_STORYBOARD_V1.json",
    root / "SM3_09D_A11_A9_TIKTOK_FOR_YOU_STORYBOARD_V1.json",
    root / "SM3_09D_A11_A9_CROP_PREVIEW_ASSESSMENT_V1.json",
]


required = [
    challenge_path,
    engine_path,
    runner_path,
    readme_path,
    *evidence_paths,
]


missing = [
    str(path)
    for path in required
    if not path.exists()
]


print(
    "REQUIRED_FILE_COUNT="
    + str(len(required))
)

print(
    "MISSING_FILE_COUNT="
    + str(len(missing))
)


for item in missing:
    print(
        "MISSING_FILE="
        + item
    )


if missing:
    raise SystemExit(1)


def load_json(path: Path) -> Any:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


platform_tokens = (
    "platform",
    "instagram",
    "tiktok",
    "reel",
    "story",
    "for_you",
    "for you",
)


def relevant_string(value: Any) -> bool:

    if not isinstance(value, str):
        return False

    lowered = value.lower()

    return any(
        token in lowered
        for token in platform_tokens
    )


def collect_platform_entries(
    value: Any,
    path: str = "$",
) -> list[dict[str, Any]]:

    output = []


    if isinstance(value, dict):

        for key, child in value.items():

            child_path = (
                path
                + "."
                + str(key)
            )


            if relevant_string(str(key)):

                output.append({
                    "path": child_path,
                    "value": child,
                    "reason": "KEY_MATCH",
                })


            output.extend(
                collect_platform_entries(
                    child,
                    child_path,
                )
            )


    elif isinstance(value, list):

        for index, child in enumerate(value):

            output.extend(
                collect_platform_entries(
                    child,
                    path + "[" + str(index) + "]",
                )
            )


    elif relevant_string(value):

        output.append({
            "path": path,
            "value": value,
            "reason": "VALUE_MATCH",
        })


    return output


def compact(value: Any, limit: int = 500) -> str:

    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        )
    except Exception:
        text = repr(value)


    text = text.replace(
        "\n",
        " ",
    )


    if len(text) > limit:
        text = (
            text[:limit]
            + "...<TRUNCATED>"
        )


    return text


challenge = load_json(
    challenge_path
)


challenge_entries = collect_platform_entries(
    challenge
)


print("")
print("=== CHALLENGE PLATFORM ENTRIES ===")

print(
    "CHALLENGE_PLATFORM_ENTRY_COUNT="
    + str(len(challenge_entries))
)


for item in challenge_entries:

    print(
        "CHALLENGE_PLATFORM_ENTRY="
        + item["path"]
        + "|"
        + item["reason"]
        + "|"
        + compact(item["value"])
    )


evidence_entries = {}


print("")
print("=== EVIDENCE PLATFORM ENTRIES ===")


for path in evidence_paths:

    data = load_json(
        path
    )

    entries = collect_platform_entries(
        data
    )

    evidence_entries[
        path.name
    ] = entries


    print("")
    print(
        "EVIDENCE_FILE="
        + path.name
    )

    print(
        "EVIDENCE_PLATFORM_ENTRY_COUNT="
        + str(len(entries))
    )


    for item in entries:

        print(
            "EVIDENCE_PLATFORM_ENTRY="
            + item["path"]
            + "|"
            + item["reason"]
            + "|"
            + compact(item["value"])
        )


engine_source = engine_path.read_text(
    encoding="utf-8-sig"
)

engine_lines = engine_source.splitlines()


print("")
print("=== ENGINE REJECTION CODE CONTEXT ===")


rejection_codes = [
    "DIAGNOSIS_EVIDENCE_REQUIRED",
    "PLATFORM_SET_INVALID",
    "PLATFORM_SET_MISMATCH",
]


code_context = {}


for code in rejection_codes:

    hits = []


    for index, line in enumerate(
        engine_lines,
        start=1,
    ):

        if code not in line:
            continue


        start = max(
            1,
            index - 10,
        )

        end = min(
            len(engine_lines),
            index + 12,
        )


        context = []


        for line_number in range(
            start,
            end + 1,
        ):

            context.append({
                "line": line_number,
                "text": engine_lines[
                    line_number - 1
                ],
            })


        hits.append({
            "hit_line": index,
            "context": context,
        })


        print("")
        print(
            "REJECTION_CODE="
            + code
        )

        print(
            "REJECTION_HIT_LINE="
            + str(index)
        )


        for row in context:

            print(
                "ENGINE_CONTEXT="
                + str(row["line"])
                + "|"
                + row["text"]
            )


    code_context[
        code
    ] = hits


print("")
print("=== ENGINE PLATFORM ASSIGNMENTS ===")


tree = ast.parse(
    engine_source,
    filename=str(engine_path),
)


platform_assignments = []


def assignment_names(
    target: ast.AST,
) -> list[str]:

    if isinstance(
        target,
        ast.Name,
    ):
        return [
            target.id
        ]

    if isinstance(
        target,
        (
            ast.Tuple,
            ast.List,
        ),
    ):

        result = []

        for child in target.elts:

            result.extend(
                assignment_names(
                    child
                )
            )

        return result

    return []


for node in ast.walk(
    tree
):

    targets = []
    value_node = None


    if isinstance(
        node,
        ast.Assign,
    ):

        for target in node.targets:
            targets.extend(
                assignment_names(
                    target
                )
            )

        value_node = node.value


    elif isinstance(
        node,
        ast.AnnAssign,
    ):

        targets.extend(
            assignment_names(
                node.target
            )
        )

        value_node = node.value


    if not targets:
        continue


    platform_targets = [
        name
        for name in targets
        if "platform" in name.lower()
    ]


    if not platform_targets:
        continue


    literal_value = None
    literal_ok = False


    if value_node is not None:

        try:
            literal_value = ast.literal_eval(
                value_node
            )

            literal_ok = True

        except Exception:
            literal_value = None


    try:
        expression = (
            ast.unparse(
                value_node
            )
            if value_node is not None
            else ""
        )

    except Exception:
        expression = ""


    record = {
        "line":
            getattr(
                node,
                "lineno",
                None,
            ),

        "targets":
            platform_targets,

        "literal_ok":
            literal_ok,

        "literal_value":
            literal_value,

        "expression":
            expression,
    }


    platform_assignments.append(
        record
    )


print(
    "PLATFORM_ASSIGNMENT_COUNT="
    + str(len(platform_assignments))
)


for item in platform_assignments:

    print(
        "PLATFORM_ASSIGNMENT="
        + str(item["line"])
        + "|"
        + ",".join(item["targets"])
        + "|LITERAL="
        + str(item["literal_ok"])
        + "|VALUE="
        + compact(item["literal_value"])
        + "|EXPR="
        + item["expression"].replace(
            "\n",
            " ",
        )
    )


print("")
print("=== ENGINE PLATFORM COMPARISONS ===")


platform_comparisons = []


for node in ast.walk(
    tree
):

    if not isinstance(
        node,
        ast.Compare,
    ):
        continue


    try:
        expression = ast.unparse(
            node
        )

    except Exception:
        continue


    lowered = expression.lower()


    if (
        "platform" not in lowered
        and "instagram" not in lowered
        and "tiktok" not in lowered
    ):
        continue


    record = {
        "line":
            getattr(
                node,
                "lineno",
                None,
            ),

        "expression":
            expression,
    }


    platform_comparisons.append(
        record
    )


print(
    "PLATFORM_COMPARISON_COUNT="
    + str(len(platform_comparisons))
)


for item in platform_comparisons:

    print(
        "PLATFORM_COMPARISON="
        + str(item["line"])
        + "|"
        + item["expression"].replace(
            "\n",
            " ",
        )
    )


print("")
print("=== ENGINE PLATFORM STRING CONSTANTS ===")


platform_strings = []


for node in ast.walk(
    tree
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
        and relevant_string(
            node.value
        )
    ):

        platform_strings.append({
            "line":
                getattr(
                    node,
                    "lineno",
                    None,
                ),

            "value":
                node.value,
        })


unique_platform_strings = []
seen_strings = set()


for item in platform_strings:

    key = (
        item["line"],
        item["value"],
    )

    if key in seen_strings:
        continue

    seen_strings.add(
        key
    )

    unique_platform_strings.append(
        item
    )


print(
    "PLATFORM_STRING_COUNT="
    + str(len(unique_platform_strings))
)


for item in unique_platform_strings:

    print(
        "PLATFORM_STRING="
        + str(item["line"])
        + "|"
        + item["value"].replace(
            "\n",
            "\\n",
        )
    )


print("")
print("=== README PLATFORM LINES ===")


readme_lines = readme_path.read_text(
    encoding="utf-8-sig"
).splitlines()


readme_hits = []


for index, line in enumerate(
    readme_lines,
    start=1,
):

    if relevant_string(
        line
    ):

        readme_hits.append({
            "line": index,
            "text": line,
        })


print(
    "README_PLATFORM_LINE_COUNT="
    + str(len(readme_hits))
)


for item in readme_hits:

    print(
        "README_PLATFORM_LINE="
        + str(item["line"])
        + "|"
        + item["text"]
    )


report = {
    "contract_version":
        "SM3_A11_A10_PLATFORM_SET_CONTRACT_DIAGNOSTIC_V1",

    "challenge_platform_entries":
        challenge_entries,

    "evidence_platform_entries":
        evidence_entries,

    "rejection_code_context":
        code_context,

    "platform_assignments":
        platform_assignments,

    "platform_comparisons":
        platform_comparisons,

    "platform_strings":
        unique_platform_strings,

    "readme_platform_lines":
        readme_hits,

    "engine_mutation_performed":
        False,

    "challenge_mutation_performed":
        False,

    "evidence_mutation_performed":
        False,

    "model_called":
        False,

    "local_model_rerun_performed":
        False,

    "diagnostic_complete":
        True,
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
print("=== FINAL DIAGNOSTIC ===")

print(
    "DIAGNOSTIC_COMPLETE=True"
)

print(
    "MODEL_CALLED=False"
)

print(
    "LOCAL_MODEL_RERUN_PERFORMED=False"
)

print(
    "SOURCE_MUTATION_PERFORMED=False"
)

print(
    "REPORT="
    + str(report_path)
)

print(
    "NEXT_ACTION=CLASSIFY_PLATFORM_SET_CONTRACT_MISMATCH"
)