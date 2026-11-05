from __future__ import annotations

import ast
import inspect
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import worker_service as ws


PROFILE_ID = "RP_0a468e360f9ae70383b235f10e445233"

ACTIVE_PLATFORM_IDS = {
    "DcRT-TIBggl",
    "Db3sIJZBogV",
    "DdW4KBZhpEd",
    "Dc38ogahxyF",
    "DcMKLA_huEW",
    "Db_btQHhhKE",
}

STATE = Path("/data/media/production_state")
SOURCE = Path("/app/worker_service.py")

OBS_DIR = (
    STATE
    / "reference_observations"
    / PROFILE_ID
)

REPORT = Path(
    "/tmp/SM3_09C7_B3D_A9_OBSERVATION_RAW_METRIC_AUDIT.json"
)


# ============================================================
# 1. METRIC-LIKE KEY DETECTION
# ============================================================

metric_patterns = (
    "view",
    "play",
    "like",
    "comment",
    "share",
    "save",
    "interaction",
    "engagement",
    "reach",
    "impression",
    "reaction",
)


def is_metric_key(key):

    lower = str(key).lower()

    return any(
        token in lower
        for token in metric_patterns
    )


def scalar(value):

    return isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
            type(None),
        ),
    )


def walk_metrics(
    value,
    path="$",
    depth=0,
    out=None,
):

    if out is None:
        out = []

    if depth > 12:
        return out

    if isinstance(value, dict):

        for key,val in value.items():

            child = (
                path
                + "."
                + str(key)
            )

            if is_metric_key(key):

                out.append({
                    "path":
                        child,

                    "value":
                        (
                            val
                            if scalar(val)
                            else
                            "<"
                            + type(val).__name__
                            + ">"
                        ),

                    "value_type":
                        type(val).__name__,
                })

            walk_metrics(
                val,
                child,
                depth + 1,
                out,
            )

    elif isinstance(value, list):

        for index,val in enumerate(value):

            walk_metrics(
                val,
                path + f"[{index}]",
                depth + 1,
                out,
            )

    return out


# ============================================================
# 2. ACTIVE OBSERVATIONS
# ============================================================

observations = []


for path in sorted(
    OBS_DIR.glob("RO_*.json")
):

    try:
        rec = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        continue

    platform_id = str(
        rec.get(
            "platform_item_id"
        )
        or ""
    )

    if platform_id not in ACTIVE_PLATFORM_IDS:
        continue

    raw = rec.get(
        "raw"
    )

    raw_metric_fields = (
        walk_metrics(raw)
        if raw is not None
        else []
    )

    non_null_raw_metrics = [
        row
        for row in raw_metric_fields
        if row.get("value") is not None
        and row.get("value") != ""
        and not (
            isinstance(
                row.get("value"),
                str,
            )
            and row["value"].startswith("<")
        )
    ]

    observations.append({
        "path":
            str(path),

        "observation_id":
            rec.get(
                "observation_id"
            ),

        "platform_item_id":
            platform_id,

        "provider":
            rec.get(
                "provider"
            ),

        "network":
            rec.get(
                "network"
            ),

        "fetched_at":
            rec.get(
                "fetched_at"
            ),

        "top_level_metrics":{
            "views":
                rec.get(
                    "views"
                ),

            "likes":
                rec.get(
                    "likes"
                ),

            "comments":
                rec.get(
                    "comments"
                ),

            "interactions":
                rec.get(
                    "interactions"
                ),

            "engagement":
                rec.get(
                    "engagement"
                ),

            "followers":
                rec.get(
                    "followers"
                ),
        },

        "raw_type":
            type(raw).__name__,

        "raw_top_level_keys":
            (
                sorted(
                    raw.keys()
                )
                if isinstance(
                    raw,
                    dict,
                )
                else []
            ),

        "raw_metric_fields":
            raw_metric_fields,

        "non_null_raw_metric_fields":
            non_null_raw_metrics,
    })


# ============================================================
# 3. SUMMARY OF RAW METRIC AVAILABILITY
# ============================================================

with_raw_metrics = [
    row
    for row in observations
    if row[
        "non_null_raw_metric_fields"
    ]
]

without_raw_metrics = [
    row
    for row in observations
    if not row[
        "non_null_raw_metric_fields"
    ]
]


# ============================================================
# 4. SOURCE CODE DISCOVERY
# ============================================================

text = SOURCE.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(
    text,
    filename=str(SOURCE),
)


candidate_functions = []


for node in tree.body:

    if not isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        continue

    try:
        source = inspect.getsource(
            getattr(
                ws,
                node.name,
            )
        )
    except Exception:
        continue

    lower = (
        node.name
        + "\n"
        + source
    ).lower()

    observation_related = (
        "reference_observation" in lower
        or
        "observation" in node.name.lower()
    )

    scraper_related = (
        "scraper" in lower
        or
        "provider" in lower
    )

    metric_related = any(
        token in lower
        for token in (
            "views",
            "likes",
            "comments",
            "interactions",
            "engagement",
            "followers",
        )
    )

    if (
        observation_related
        and (
            scraper_related
            or metric_related
        )
    ):
        candidate_functions.append({
            "name":
                node.name,

            "source":
                source,
        })


# ============================================================
# 5. OBSERVATION CONSTRUCTION SITES
# ============================================================

construction_lines = []

lines = text.splitlines()


for lineno,line in enumerate(
    lines,
    start=1,
):

    lower = line.lower()

    if not any(
        token in lower
        for token in (
            '"views"',
            '"likes"',
            '"comments"',
            '"interactions"',
            '"engagement"',
            '"raw"',
        )
    ):
        continue

    start = max(
        1,
        lineno - 6,
    )

    end = min(
        len(lines),
        lineno + 6,
    )

    context = "\n".join(
        f"{n}:{lines[n-1]}"
        for n in range(
            start,
            end + 1,
        )
    )

    if (
        "observation" in context.lower()
        or
        "scraper" in context.lower()
        or
        "provider" in context.lower()
    ):
        construction_lines.append({
            "line":
                lineno,

            "context":
                context,
        })


# ============================================================
# 6. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3D-A9",

    "status":
        "OBSERVATION_RAW_METRIC_PROVENANCE_AUDIT_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "reference_profile_id":
        PROFILE_ID,

    "active_platform_ids":
        sorted(
            ACTIVE_PLATFORM_IDS
        ),

    "active_observation_count":
        len(
            observations
        ),

    "observations_with_non_null_raw_metrics":
        len(
            with_raw_metrics
        ),

    "observations_without_non_null_raw_metrics":
        len(
            without_raw_metrics
        ),

    "observations":
        observations,

    "candidate_functions":
        candidate_functions,

    "construction_lines":
        construction_lines,

    "production_write_performed":
        False,

    "observation_api_called":
        False,

    "metric_api_called":
        False,

    "priority_api_called":
        False,

    "semantic_api_called":
        False,

    "provider_called":
        False,

    "network_request_performed":
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
# 7. CONSOLE
# ============================================================

print(
    "=== ACTIVE OBSERVATION RAW METRICS ==="
)

print(
    "ACTIVE_OBSERVATION_COUNT="
    + str(
        len(observations)
    )
)

print(
    "OBSERVATIONS_WITH_NON_NULL_RAW_METRICS="
    + str(
        len(with_raw_metrics)
    )
)

print(
    "OBSERVATIONS_WITHOUT_NON_NULL_RAW_METRICS="
    + str(
        len(without_raw_metrics)
    )
)


for row in observations:

    print("")
    print(
        "OBSERVATION_ID="
        + str(
            row[
                "observation_id"
            ]
        )
    )

    print(
        "PLATFORM_ITEM_ID="
        + str(
            row[
                "platform_item_id"
            ]
        )
    )

    print(
        "PROVIDER="
        + str(
            row[
                "provider"
            ]
        )
    )

    print(
        "TOP_LEVEL_METRICS="
        + json.dumps(
            row[
                "top_level_metrics"
            ],
            ensure_ascii=False,
            separators=(",",":"),
        )
    )

    print(
        "RAW_TYPE="
        + str(
            row[
                "raw_type"
            ]
        )
    )

    print(
        "RAW_TOP_LEVEL_KEYS="
        + json.dumps(
            row[
                "raw_top_level_keys"
            ],
            ensure_ascii=False,
            separators=(",",":"),
        )
    )

    print(
        "NON_NULL_RAW_METRICS="
        + json.dumps(
            row[
                "non_null_raw_metric_fields"
            ],
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== OBSERVATION / SCRAPER FUNCTIONS ==="
)

for row in candidate_functions:

    print(
        "\n--- "
        + row[
            "name"
        ]
        + " ---"
    )

    print(
        row[
            "source"
        ]
    )


print(
    "\n=== OBSERVATION METRIC CONSTRUCTION CONTEXTS ==="
)

seen = set()

for row in construction_lines:

    context = row[
        "context"
    ]

    if context in seen:
        continue

    seen.add(
        context
    )

    print(
        "\n--- LINE "
        + str(
            row[
                "line"
            ]
        )
        + " ---"
    )

    print(
        context
    )


print("")
print(
    "PRODUCTION_WRITE_PERFORMED=False"
)
print(
    "OBSERVATION_API_CALLED=False"
)
print(
    "METRIC_API_CALLED=False"
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
    "NETWORK_REQUEST_PERFORMED=False"
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
    "SM3_09C7_B3D_A9_OBSERVATION_RAW_METRIC_PROVENANCE_AUDIT_COMPLETE"
)
