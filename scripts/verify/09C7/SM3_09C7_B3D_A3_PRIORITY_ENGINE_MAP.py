from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import worker_service as ws


SOURCE = Path("/app/worker_service.py")
STATE = Path("/data/media/production_state")

REPORT = Path(
    "/tmp/SM3_09C7_B3D_A3_PRIORITY_ENGINE_MAP.json"
)

TARGET_ITEM = "RI_500f8618a5796dc9b1fbded2f3bfff2e"

TARGET_SOURCE_SHA = (
    "2ddfb7989ec80ca8d301e40c7f74ca0138a200632c247b8681e007ed6d2bd2e7"
)

TARGET_MECHANICAL = (
    "RMA_0072a9689863b956298a9ec34f01bd0e"
)


text = SOURCE.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(
    text,
    filename=str(SOURCE),
)


def safe_signature(name):

    obj = getattr(
        ws,
        name,
        None,
    )

    if obj is None:
        return None

    try:
        return str(
            inspect.signature(obj)
        )
    except Exception:
        return None


def source_segment(node):

    return (
        ast.get_source_segment(
            text,
            node,
        )
        or ""
    )


def load_json_records():

    rows = []

    if not STATE.exists():
        return rows

    for path in STATE.rglob("*.json"):

        try:
            rec = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        if isinstance(rec, dict):
            rows.append(
                (
                    path,
                    rec,
                )
            )

    return rows


records = load_json_records()


# ============================================================
# 1. PRIORITY ROUTES
# ============================================================

priority_routes = []


for node in tree.body:

    if not isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        continue

    for decorator in node.decorator_list:

        if not isinstance(
            decorator,
            ast.Call,
        ):
            continue

        fn = decorator.func

        if not (
            isinstance(fn, ast.Attribute)
            and
            isinstance(fn.value, ast.Name)
            and
            fn.value.id == "app"
            and
            fn.attr in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }
        ):
            continue

        if not decorator.args:
            continue

        arg = decorator.args[0]

        if not (
            isinstance(arg, ast.Constant)
            and
            isinstance(arg.value, str)
        ):
            continue

        route_path = arg.value

        if "priority" not in route_path.lower():
            continue

        params = []

        for param in node.args.args:

            annotation = None

            if param.annotation is not None:

                try:
                    annotation = ast.unparse(
                        param.annotation
                    )
                except Exception:
                    annotation = None

            params.append({
                "name":
                    param.arg,

                "annotation":
                    annotation,
            })

        priority_routes.append({
            "method":
                fn.attr.upper(),

            "path":
                route_path,

            "function":
                node.name,

            "signature":
                safe_signature(
                    node.name
                ),

            "parameters":
                params,

            "source":
                source_segment(
                    node
                ),
        })


# ============================================================
# 2. PRIORITY REQUEST / DATA MODELS
# ============================================================

priority_models = []


for node in tree.body:

    if not isinstance(
        node,
        ast.ClassDef,
    ):
        continue

    if "priority" not in node.name.lower():
        continue

    fields = []

    for child in node.body:

        if not isinstance(
            child,
            ast.AnnAssign,
        ):
            continue

        if not isinstance(
            child.target,
            ast.Name,
        ):
            continue

        annotation = None
        default = None

        try:
            annotation = ast.unparse(
                child.annotation
            )
        except Exception:
            pass

        if child.value is not None:

            try:
                default = ast.unparse(
                    child.value
                )
            except Exception:
                pass

        fields.append({
            "name":
                child.target.id,

            "annotation":
                annotation,

            "default":
                default,
        })

    priority_models.append({
        "class":
            node.name,

        "fields":
            fields,

        "source":
            source_segment(
                node
            ),
    })


# ============================================================
# 3. PRIORITY FUNCTIONS
# ============================================================

priority_functions = []


for node in tree.body:

    if not isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        continue

    if "priority" not in node.name.lower():
        continue

    priority_functions.append({
        "name":
            node.name,

        "signature":
            safe_signature(
                node.name
            ),

        "source":
            source_segment(
                node
            ),
    })


# ============================================================
# 4. PRIORITY CONSTANTS
# ============================================================

priority_constants = {}


for name in dir(ws):

    upper = name.upper()

    if (
        "REFERENCE_PRIORITY" not in upper
        and
        "PRIORITY_" not in upper
    ):
        continue

    try:
        value = getattr(
            ws,
            name
        )
    except Exception:
        continue

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
            type(None),
        ),
    ):
        priority_constants[
            name
        ] = value

    elif isinstance(
        value,
        (
            list,
            tuple,
            dict,
            set,
        ),
    ):

        try:
            json.dumps(
                value,
                default=str,
            )

            priority_constants[
                name
            ] = value

        except Exception:
            priority_constants[
                name
            ] = str(value)


# ============================================================
# 5. EXISTING RPD RECORDS
# ============================================================

rpd_records = []


for path,rec in records:

    if (
        rec.get(
            "contract_version"
        )
        !=
        "SM3_REFERENCE_PRIORITY_DECISION_V1"
    ):
        continue

    rpd_records.append({
        "path":
            str(path),

        "record":
            rec,
    })


# ============================================================
# 6. TARGET ITEM RECORD
# ============================================================

target_item_records = []


for path,rec in records:

    if (
        rec.get(
            "reference_item_id"
        )
        != TARGET_ITEM
    ):
        continue

    if (
        rec.get(
            "contract_version"
        )
        ==
        "SM3_REFERENCE_ITEM_V1"
    ):

        target_item_records.append({
            "path":
                str(path),

            "record":
                rec,
        })


# ============================================================
# 7. TARGET METRIC / FEATURE / OBSERVATION EVIDENCE
# ============================================================

target_evidence = []


for path,rec in records:

    contract = str(
        rec.get(
            "contract_version"
        )
        or ""
    )

    item_match = (
        str(
            rec.get(
                "reference_item_id"
            )
            or ""
        )
        == TARGET_ITEM
    )

    source_match = (
        str(
            rec.get(
                "source_sha256"
            )
            or ""
        ).lower()
        ==
        TARGET_SOURCE_SHA
    )

    if not (
        item_match
        or source_match
    ):
        continue

    if contract in {
        "SM3_REFERENCE_METRIC_SNAPSHOT_V1",
        "SM3_REFERENCE_FEATURES_V1",
        "SM3_REFERENCE_OBSERVATION_V1",
        "SM3_REFERENCE_MECHANICAL_ANALYSIS_V1",
        "SM3_REFERENCE_MEDIA_ACQUISITION_V1",
        "SM3_REFERENCE_MEDIA_ACQUISITION_V2",
    }:

        target_evidence.append({
            "path":
                str(path),

            "contract_version":
                contract,

            "record":
                rec,
        })


# ============================================================
# 8. TARGET MECHANICAL RECORD
# ============================================================

target_mechanical = None


for path,rec in records:

    if (
        rec.get(
            "mechanical_analysis_id"
        )
        == TARGET_MECHANICAL
    ):
        target_mechanical = {
            "path":
                str(path),

            "record":
                rec,
        }

        break


# ============================================================
# 9. SOURCE REFERENCES TO EVIDENCE / WEIGHTS / THRESHOLDS
# ============================================================

interesting_lines = []


keywords = (
    "human_priority",
    "metric",
    "mechanical",
    "semantic_analysis_allowed",
    "evidence_fingerprint",
    "priority_score",
    "SEMANTIC_ANALYSIS",
    "DEFER",
    "SKIP",
    "0.30",
    "0.50",
    "0.20",
    "70",
    "40",
)


for lineno,line in enumerate(
    text.splitlines(),
    start=1,
):

    lower = line.lower()

    if not any(
        keyword.lower() in lower
        for keyword in keywords
    ):
        continue

    # Keep only lines reasonably close to Priority code.
    if (
        "priority" in lower
        or
        "semantic_analysis_allowed" in lower
        or
        "evidence_fingerprint" in lower
        or
        "human_priority" in lower
    ):

        interesting_lines.append({
            "line":
                lineno,

            "text":
                line,
        })


# ============================================================
# 10. SUMMARY
# ============================================================

summary = {
    "worker_version":
        ws.WORKER_VERSION,

    "priority_route_count":
        len(
            priority_routes
        ),

    "priority_model_count":
        len(
            priority_models
        ),

    "priority_function_count":
        len(
            priority_functions
        ),

    "priority_constant_count":
        len(
            priority_constants
        ),

    "existing_rpd_count":
        len(
            rpd_records
        ),

    "target_item_record_count":
        len(
            target_item_records
        ),

    "target_evidence_record_count":
        len(
            target_evidence
        ),

    "target_mechanical_found":
        target_mechanical
        is not None,
}


report = {
    "phase":
        "09C7-B3D-A3",

    "status":
        "PRIORITY_ENGINE_RUNTIME_CONTRACT_MAP_COMPLETE",

    "summary":
        summary,

    "priority_routes":
        priority_routes,

    "priority_models":
        priority_models,

    "priority_functions":
        priority_functions,

    "priority_constants":
        priority_constants,

    "existing_rpd_records":
        rpd_records,

    "target_item_records":
        target_item_records,

    "target_evidence":
        target_evidence,

    "target_mechanical":
        target_mechanical,

    "interesting_source_lines":
        interesting_lines,

    "production_write_performed":
        False,

    "priority_api_called":
        False,

    "semantic_api_called":
        False,

    "provider_called":
        False,

    "model_called":
        False,
}


REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
        default=str,
    ),
    encoding="utf-8",
)


# ============================================================
# CONSOLE SUMMARY
# ============================================================

print(
    "=== SM3 09C7-B3D-A3 PRIORITY ENGINE MAP ==="
)

print(
    "WORKER_VERSION="
    + str(
        ws.WORKER_VERSION
    )
)

print(
    "PRIORITY_ROUTE_COUNT="
    + str(
        len(priority_routes)
    )
)

print(
    "PRIORITY_MODEL_COUNT="
    + str(
        len(priority_models)
    )
)

print(
    "PRIORITY_FUNCTION_COUNT="
    + str(
        len(priority_functions)
    )
)

print(
    "EXISTING_RPD_COUNT="
    + str(
        len(rpd_records)
    )
)

print(
    "TARGET_ITEM_RECORD_COUNT="
    + str(
        len(target_item_records)
    )
)

print(
    "TARGET_EVIDENCE_RECORD_COUNT="
    + str(
        len(target_evidence)
    )
)

print(
    "TARGET_MECHANICAL_FOUND="
    + str(
        target_mechanical
        is not None
    )
)


print(
    "\n=== PRIORITY ROUTES ==="
)

for row in priority_routes:

    print(
        json.dumps(
            {
                "method":
                    row["method"],

                "path":
                    row["path"],

                "function":
                    row["function"],

                "signature":
                    row["signature"],

                "parameters":
                    row["parameters"],
            },
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== PRIORITY MODELS ==="
)

for row in priority_models:

    print(
        json.dumps(
            {
                "class":
                    row["class"],

                "fields":
                    row["fields"],
            },
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== PRIORITY CONSTANTS ==="
)

for name in sorted(
    priority_constants
):

    print(
        name
        + "="
        + json.dumps(
            priority_constants[
                name
            ],
            ensure_ascii=False,
            default=str,
            separators=(",",":"),
        )
    )


print(
    "\n=== EXISTING RPD RECORDS ==="
)

for row in rpd_records:

    rec = row[
        "record"
    ]

    compact = {
        "path":
            row[
                "path"
            ],

        "priority_decision_id":
            rec.get(
                "priority_decision_id"
            ),

        "reference_item_id":
            rec.get(
                "reference_item_id"
            ),

        "source_sha256":
            rec.get(
                "source_sha256"
            ),

        "mechanical_analysis_id":
            rec.get(
                "mechanical_analysis_id"
            ),

        "eligibility":
            rec.get(
                "eligibility"
            ),

        "decision":
            rec.get(
                "decision"
            ),

        "priority_score":
            rec.get(
                "priority_score"
            ),

        "semantic_analysis_allowed":
            rec.get(
                "semantic_analysis_allowed"
            ),

        "evidence_fingerprint":
            rec.get(
                "evidence_fingerprint"
            ),

        "record_fields":
            sorted(
                rec.keys()
            ),
    }

    print(
        json.dumps(
            compact,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== TARGET ITEM ==="
)

for row in target_item_records:

    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== TARGET EVIDENCE ==="
)

for row in target_evidence:

    compact = {
        "path":
            row[
                "path"
            ],

        "contract_version":
            row[
                "contract_version"
            ],

        "record":
            row[
                "record"
            ],
    }

    print(
        json.dumps(
            compact,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== PRIORITY FUNCTION SIGNATURES ==="
)

for row in priority_functions:

    print(
        row["name"]
        + str(
            row["signature"]
        )
    )


print(
    "\n=== PRIORITY ROUTE SOURCES ==="
)

for row in priority_routes:

    print(
        "\n--- "
        + row["function"]
        + " ---"
    )

    print(
        row["source"]
    )


print(
    "\n=== PRIORITY HELPER SOURCES ==="
)

for row in priority_functions:

    if row["name"].startswith(
        "_"
    ):

        print(
            "\n--- "
            + row["name"]
            + " ---"
        )

        print(
            row["source"]
        )


print(
    "\nPRODUCTION_WRITE_PERFORMED=False"
)

print(
    "PRIORITY_API_CALLED=False"
)

print(
    "SEMANTIC_API_CALLED=False"
)

print(
    "PROVIDER_CALLED=False"
)

print(
    "MODEL_CALLED=False"
)

print(
    "REPORT="
    + str(
        REPORT
    )
)

print(
    "SM3_09C7_B3D_A3_PRIORITY_ENGINE_RUNTIME_CONTRACT_MAP_COMPLETE"
)
