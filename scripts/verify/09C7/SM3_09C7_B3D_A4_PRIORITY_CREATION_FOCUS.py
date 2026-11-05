from __future__ import annotations

from pathlib import Path
import json
import re


ROOT = Path(r"D:\MOLOTOV_SOCIAL_OS_RC7")

INPUT = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B3D_A3_PRIORITY_ENGINE_MAP.json"
)

OUTPUT = (
    ROOT
    / "reports"
    / "09C7"
    / "SM3_09C7_B3D_A4_PRIORITY_CREATION_FOCUS.json"
)


report = json.loads(
    INPUT.read_text(
        encoding="utf-8-sig"
    )
)


# ============================================================
# 1. ROUTES
# ============================================================

routes = report.get(
    "priority_routes",
    []
)

post_routes = [
    row
    for row in routes
    if row.get("method") == "POST"
]


# ============================================================
# 2. REQUEST MODEL
# ============================================================

models = report.get(
    "priority_models",
    []
)


# ============================================================
# 3. RELEVANT CONSTANTS
# ============================================================

constants = report.get(
    "priority_constants",
    {}
)

interesting_constants = {}

for name,value in constants.items():

    upper = name.upper()

    if any(
        token in upper
        for token in (
            "CONTRACT",
            "ENGINE",
            "VERSION",
            "WEIGHT",
            "THRESHOLD",
            "SEMANTIC",
            "DEFER",
            "SKIP",
            "SCORE",
        )
    ):
        interesting_constants[name] = value


# ============================================================
# 4. HELPER FUNCTIONS THAT CONTROL GENERATION
# ============================================================

functions = report.get(
    "priority_functions",
    []
)

generation_helpers = []

for row in functions:

    name = str(
        row.get("name")
        or ""
    )

    source = str(
        row.get("source")
        or ""
    )

    haystack = (
        name
        + "\n"
        + source
    ).lower()

    if any(
        token in haystack
        for token in (
            "evidence",
            "fingerprint",
            "score",
            "weight",
            "eligibility",
            "decision",
            "semantic_analysis_allowed",
            "priority_engine",
            "human_priority",
            "metric",
            "mechanical",
        )
    ):

        generation_helpers.append({
            "name":
                name,

            "signature":
                row.get(
                    "signature"
                ),

            "source":
                source,
        })


# ============================================================
# 5. HISTORICAL RPD FULL KEY MAP
# ============================================================

historical = []

for row in report.get(
    "existing_rpd_records",
    []
):

    rec = row.get(
        "record",
        {}
    )

    historical.append({
        "path":
            row.get(
                "path"
            ),

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

        "all_fields":
            sorted(
                rec.keys()
            ),

        "record":
            rec,
    })


# ============================================================
# 6. TARGET EVIDENCE COMPACT
# ============================================================

target_evidence = []

for row in report.get(
    "target_evidence",
    []
):

    rec = row.get(
        "record",
        {}
    )

    scalar = {}

    for key,value in rec.items():

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
                type(None),
            )
        ):
            scalar[key] = value

    target_evidence.append({
        "path":
            row.get(
                "path"
            ),

        "contract_version":
            row.get(
                "contract_version"
            ),

        "scalar_fields":
            scalar,

        "all_fields":
            sorted(
                rec.keys()
            ),
    })


# ============================================================
# 7. TARGET ITEM
# ============================================================

target_items = report.get(
    "target_item_records",
    []
)


# ============================================================
# 8. DERIVE REQUEST VS CALCULATED FIELDS FROM ROUTE SOURCE
# ============================================================

route_field_refs = []

for route in post_routes:

    source = str(
        route.get(
            "source"
        )
        or ""
    )

    refs = sorted(
        set(
            re.findall(
                r"req\.([A-Za-z_][A-Za-z0-9_]*)",
                source,
            )
        )
    )

    route_field_refs.append({
        "function":
            route.get(
                "function"
            ),

        "path":
            route.get(
                "path"
            ),

        "request_field_references":
            refs,

        "source":
            source,
    })


# ============================================================
# 9. OUTPUT
# ============================================================

focused = {
    "phase":
        "09C7-B3D-A4",

    "status":
        "PRIORITY_CREATION_CONTRACT_FOCUS_COMPLETE",

    "post_routes":
        post_routes,

    "request_models":
        models,

    "interesting_constants":
        interesting_constants,

    "generation_helpers":
        generation_helpers,

    "historical_rpd":
        historical,

    "target_item":
        target_items,

    "target_evidence":
        target_evidence,

    "route_request_field_references":
        route_field_refs,

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


OUTPUT.write_text(
    json.dumps(
        focused,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


# ============================================================
# CONSOLE
# ============================================================

print(
    "=== PRIORITY POST ROUTES ==="
)

for row in post_routes:

    print(
        json.dumps(
            {
                "method":
                    row.get("method"),

                "path":
                    row.get("path"),

                "function":
                    row.get("function"),

                "signature":
                    row.get("signature"),

                "parameters":
                    row.get("parameters"),
            },
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== PRIORITY REQUEST MODELS ==="
)

for row in models:

    print(
        json.dumps(
            {
                "class":
                    row.get("class"),

                "fields":
                    row.get("fields"),
            },
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== ROUTE REQUEST FIELD REFERENCES ==="
)

for row in route_field_refs:

    print(
        json.dumps(
            {
                "function":
                    row["function"],

                "path":
                    row["path"],

                "request_field_references":
                    row[
                        "request_field_references"
                    ],
            },
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== PRIORITY CONSTANTS ==="
)

for name in sorted(
    interesting_constants
):

    print(
        name
        + "="
        + json.dumps(
            interesting_constants[
                name
            ],
            ensure_ascii=False,
            separators=(",",":"),
            default=str,
        )
    )


print(
    "\n=== HISTORICAL RPD ==="
)

for row in historical:

    print(
        json.dumps(
            {
                "priority_decision_id":
                    row[
                        "priority_decision_id"
                    ],

                "reference_item_id":
                    row[
                        "reference_item_id"
                    ],

                "source_sha256":
                    row[
                        "source_sha256"
                    ],

                "mechanical_analysis_id":
                    row[
                        "mechanical_analysis_id"
                    ],

                "eligibility":
                    row[
                        "eligibility"
                    ],

                "decision":
                    row[
                        "decision"
                    ],

                "priority_score":
                    row[
                        "priority_score"
                    ],

                "semantic_analysis_allowed":
                    row[
                        "semantic_analysis_allowed"
                    ],

                "evidence_fingerprint":
                    row[
                        "evidence_fingerprint"
                    ],

                "all_fields":
                    row[
                        "all_fields"
                    ],
            },
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== TARGET EVIDENCE ==="
)

for row in target_evidence:

    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== GENERATION HELPER SIGNATURES ==="
)

for row in generation_helpers:

    print(
        str(
            row.get(
                "name"
            )
        )
        + str(
            row.get(
                "signature"
            )
        )
    )


print(
    "\n=== PRIORITY POST ROUTE SOURCE ==="
)

for row in route_field_refs:

    print(
        "\n--- "
        + str(
            row["function"]
        )
        + " ---"
    )

    print(
        row["source"]
    )


print(
    "\n=== PRIORITY GENERATION HELPER SOURCES ==="
)

for row in generation_helpers:

    print(
        "\n--- "
        + str(
            row.get(
                "name"
            )
        )
        + " ---"
    )

    print(
        row.get(
            "source"
        )
        or ""
    )


print("")
print("PRODUCTION_WRITE_PERFORMED=False")
print("PRIORITY_API_CALLED=False")
print("SEMANTIC_API_CALLED=False")
print("PROVIDER_CALLED=False")
print("MODEL_CALLED=False")

print(
    "REPORT="
    + str(
        OUTPUT
    )
)

print(
    "SM3_09C7_B3D_A4_PRIORITY_CREATION_CONTRACT_FOCUS_COMPLETE"
)
