from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, "/app")

import worker_service as ws


PROFILE_ID = "RP_0a468e360f9ae70383b235f10e445233"
TARGET_ITEM_ID = "RI_500f8618a5796dc9b1fbded2f3bfff2e"

STATE = Path("/data/media/production_state")
SOURCE = Path("/app/worker_service.py")

REPORT = Path(
    "/tmp/SM3_09C7_B3D_A8_METRIC_POPULATION_AUDIT.json"
)


def norm(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return value.lower()


def url_tail(value):
    if not value:
        return None

    try:
        path = urlparse(
            str(value)
        ).path.strip("/")

        if not path:
            return None

        return path.split("/")[-1].lower()

    except Exception:
        return None


def scalar_identity_values(rec):

    out = {}

    for key,value in rec.items():

        if not isinstance(
            value,
            (str,int,float,bool)
        ):
            continue

        lower = str(key).lower()

        if any(
            token in lower
            for token in (
                "platform",
                "shortcode",
                "url",
                "item_id",
                "external",
                "post_id",
                "media_id",
            )
        ):
            out[key] = value

    return out


# ============================================================
# 1. PROFILE
# ============================================================

profile = ws._load_reference_profile(
    PROFILE_ID
)

profile_has_human_priority = (
    "human_priority" in profile
)

profile_human_priority_raw = (
    profile.get(
        "human_priority"
    )
)

profile_human_priority_effective = max(
    0,
    min(
        100,
        int(
            profile.get(
                "human_priority",
                50,
            )
        ),
    ),
)


# ============================================================
# 2. ACTIVE ITEMS
# ============================================================

active_items = (
    ws.production_reference_items(
        PROFILE_ID,
        include_tombstoned=False,
    ).get("items")
    or []
)


# ============================================================
# 3. SNAPSHOTS BY ACTIVE ITEM
# ============================================================

item_rows = []

active_snapshot_count = 0

basis_counts = {}


for item in active_items:

    item_id = str(
        item.get(
            "reference_item_id"
        )
        or ""
    )

    result = (
        ws.production_reference_metric_snapshots(
            item_id
        )
    )

    snapshots = list(
        result.get("snapshots")
        or []
    )

    latest = (
        ws._reference_priority_latest_metric_snapshot(
            item_id
        )
    )

    basis = None
    metric_value = None

    if latest is not None:
        basis,metric_value = (
            ws._reference_priority_metric_value(
                latest
            )
        )

    if latest is not None:
        active_snapshot_count += 1

    if basis is not None:

        basis_counts[basis] = (
            basis_counts.get(
                basis,
                0
            )
            + 1
        )

    signal = (
        ws._reference_priority_metric_signal(
            item
        )
    )

    item_rows.append({
        "reference_item_id":
            item_id,

        "item_type":
            item.get(
                "item_type"
            ),

        "identity_fields":
            scalar_identity_values(
                item
            ),

        "snapshot_count":
            len(
                snapshots
            ),

        "latest_snapshot_id":
            (
                latest.get(
                    "snapshot_id"
                )
                if latest
                else None
            ),

        "metric_basis":
            basis,

        "metric_value":
            metric_value,

        "metric_signal":
            signal,
    })


# ============================================================
# 4. ALL METRIC SNAPSHOTS
# ============================================================

all_snapshots = []

snapshot_root = (
    STATE
    / "reference_metric_snapshots"
)

if snapshot_root.exists():

    for path in snapshot_root.rglob(
        "RMS_*.json"
    ):

        try:
            rec = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        basis,value = (
            ws._reference_priority_metric_value(
                rec
            )
        )

        all_snapshots.append({
            "path":
                str(path),

            "reference_item_id":
                rec.get(
                    "reference_item_id"
                ),

            "reference_profile_id":
                rec.get(
                    "reference_profile_id"
                ),

            "snapshot_id":
                rec.get(
                    "snapshot_id"
                ),

            "captured_at":
                rec.get(
                    "captured_at"
                ),

            "basis":
                basis,

            "metric_value":
                value,

            "engagement":
                rec.get(
                    "engagement"
                ),

            "interactions":
                rec.get(
                    "interactions"
                ),

            "likes":
                rec.get(
                    "likes"
                ),

            "comments":
                rec.get(
                    "comments"
                ),

            "raw_metrics":
                rec.get(
                    "raw_metrics"
                ),
        })


# ============================================================
# 5. OBSERVATIONS
# ============================================================

observations = []

observation_root = (
    STATE
    / "reference_observations"
    / PROFILE_ID
)

if observation_root.exists():

    for path in observation_root.glob(
        "RO_*.json"
    ):

        try:
            rec = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        observations.append({
            "path":
                str(path),

            "observation_id":
                rec.get(
                    "observation_id"
                ),

            "platform_item_id":
                rec.get(
                    "platform_item_id"
                ),

            "url":
                rec.get(
                    "url"
                ),

            "url_tail":
                url_tail(
                    rec.get(
                        "url"
                    )
                ),

            "content_type":
                rec.get(
                    "content_type"
                ),

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

            "published_at":
                rec.get(
                    "published_at"
                ),

            "provider":
                rec.get(
                    "provider"
                ),

            "network":
                rec.get(
                    "network"
                ),
        })


# ============================================================
# 6. DETERMINISTIC OBSERVATION ↔ ITEM CANDIDATES
# ============================================================

links = []


for item in active_items:

    item_id = str(
        item.get(
            "reference_item_id"
        )
        or ""
    )

    identities = scalar_identity_values(
        item
    )

    normalized_values = set()

    url_tails = set()

    for value in identities.values():

        nv = norm(value)

        if nv:
            normalized_values.add(
                nv
            )

        tail = url_tail(
            value
        )

        if tail:
            url_tails.add(
                tail
            )

    matches = []

    for obs in observations:

        reasons = []

        platform_id = norm(
            obs.get(
                "platform_item_id"
            )
        )

        obs_url = norm(
            obs.get(
                "url"
            )
        )

        obs_tail = obs.get(
            "url_tail"
        )

        if (
            platform_id
            and platform_id
            in normalized_values
        ):
            reasons.append(
                "PLATFORM_ITEM_ID_EXACT"
            )

        if (
            obs_url
            and obs_url
            in normalized_values
        ):
            reasons.append(
                "URL_EXACT"
            )

        if (
            obs_tail
            and obs_tail
            in url_tails
        ):
            reasons.append(
                "URL_TAIL_EXACT"
            )

        if reasons:

            matches.append({
                "observation_id":
                    obs[
                        "observation_id"
                    ],

                "platform_item_id":
                    obs[
                        "platform_item_id"
                    ],

                "url":
                    obs[
                        "url"
                    ],

                "reasons":
                    reasons,

                "views":
                    obs[
                        "views"
                    ],

                "likes":
                    obs[
                        "likes"
                    ],

                "comments":
                    obs[
                        "comments"
                    ],

                "interactions":
                    obs[
                        "interactions"
                    ],

                "engagement":
                    obs[
                        "engagement"
                    ],
            })

    links.append({
        "reference_item_id":
            item_id,

        "identity_fields":
            identities,

        "observation_matches":
            matches,

        "observation_match_count":
            len(
                matches
            ),
    })


# ============================================================
# 7. METRIC ENDPOINT / REQUEST CONTRACT
# ============================================================

text = SOURCE.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(
    text,
    filename=str(SOURCE),
)

metric_routes = []

metric_models = []


for node in tree.body:

    if isinstance(
        node,
        ast.ClassDef,
    ):

        if "metric" not in node.name.lower():
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

            try:
                annotation = ast.unparse(
                    child.annotation
                )
            except Exception:
                annotation = None

            try:
                default = (
                    ast.unparse(
                        child.value
                    )
                    if child.value is not None
                    else None
                )
            except Exception:
                default = None

            fields.append({
                "name":
                    child.target.id,

                "annotation":
                    annotation,

                "default":
                    default,
            })

        metric_models.append({
            "class":
                node.name,

            "fields":
                fields,
        })


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

        if "metric" not in route_path.lower():
            continue

        try:
            source = inspect.getsource(
                getattr(
                    ws,
                    node.name
                )
            )
        except Exception:
            source = ""

        metric_routes.append({
            "method":
                fn.attr.upper(),

            "path":
                route_path,

            "function":
                node.name,

            "source":
                source,
        })


# ============================================================
# 8. TARGET SUMMARY
# ============================================================

target_item_row = next(
    (
        r
        for r in item_rows
        if r[
            "reference_item_id"
        ]
        == TARGET_ITEM_ID
    ),
    None,
)

target_link_row = next(
    (
        r
        for r in links
        if r[
            "reference_item_id"
        ]
        == TARGET_ITEM_ID
    ),
    None,
)


# ============================================================
# 9. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3D-A8",

    "status":
        "METRIC_POPULATION_AND_OBSERVATION_LINKAGE_AUDIT_COMPLETE",

    "worker_version":
        ws.WORKER_VERSION,

    "reference_profile_id":
        PROFILE_ID,

    "profile_has_human_priority":
        profile_has_human_priority,

    "profile_human_priority_raw":
        profile_human_priority_raw,

    "profile_human_priority_effective":
        profile_human_priority_effective,

    "active_item_count":
        len(
            active_items
        ),

    "active_snapshot_item_count":
        active_snapshot_count,

    "basis_counts":
        basis_counts,

    "items":
        item_rows,

    "all_metric_snapshots":
        all_snapshots,

    "observations":
        observations,

    "observation_links":
        links,

    "target_item":
        target_item_row,

    "target_observation_link":
        target_link_row,

    "metric_routes":
        metric_routes,

    "metric_models":
        metric_models,

    "production_write_performed":
        False,

    "metric_api_called":
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
# 10. CONSOLE
# ============================================================

print(
    "=== PROFILE PRIORITY ==="
)

print(
    "PROFILE_HAS_HUMAN_PRIORITY="
    + str(
        profile_has_human_priority
    )
)

print(
    "PROFILE_HUMAN_PRIORITY_RAW="
    + str(
        profile_human_priority_raw
    )
)

print(
    "PROFILE_HUMAN_PRIORITY_EFFECTIVE="
    + str(
        profile_human_priority_effective
    )
)


print(
    "\n=== ACTIVE METRIC POPULATION ==="
)

print(
    "ACTIVE_ITEM_COUNT="
    + str(
        len(active_items)
    )
)

print(
    "ACTIVE_ITEMS_WITH_SNAPSHOT="
    + str(
        active_snapshot_count
    )
)

print(
    "BASIS_COUNTS="
    + json.dumps(
        basis_counts,
        ensure_ascii=False,
        separators=(",",":"),
    )
)


for row in item_rows:

    print(
        json.dumps(
            {
                "reference_item_id":
                    row[
                        "reference_item_id"
                    ],

                "item_type":
                    row[
                        "item_type"
                    ],

                "identity_fields":
                    row[
                        "identity_fields"
                    ],

                "snapshot_count":
                    row[
                        "snapshot_count"
                    ],

                "latest_snapshot_id":
                    row[
                        "latest_snapshot_id"
                    ],

                "metric_basis":
                    row[
                        "metric_basis"
                    ],

                "metric_value":
                    row[
                        "metric_value"
                    ],

                "metric_signal":
                    row[
                        "metric_signal"
                    ],
            },
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== OBSERVATION LINKAGE ==="
)

for row in links:

    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== TARGET ==="
)

print(
    "TARGET_ITEM="
    + TARGET_ITEM_ID
)

print(
    "TARGET_SNAPSHOT_COUNT="
    + str(
        (
            target_item_row
            or {}
        ).get(
            "snapshot_count"
        )
    )
)

print(
    "TARGET_OBSERVATION_MATCH_COUNT="
    + str(
        (
            target_link_row
            or {}
        ).get(
            "observation_match_count"
        )
    )
)

print(
    "TARGET_OBSERVATION_MATCHES="
    + json.dumps(
        (
            target_link_row
            or {}
        ).get(
            "observation_matches"
        )
        or [],
        ensure_ascii=False,
        separators=(",",":"),
    )
)


print(
    "\n=== METRIC ROUTES ==="
)

for row in metric_routes:

    print(
        json.dumps(
            {
                "method":
                    row[
                        "method"
                    ],

                "path":
                    row[
                        "path"
                    ],

                "function":
                    row[
                        "function"
                    ],
            },
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== METRIC REQUEST MODELS ==="
)

for row in metric_models:

    print(
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",",":"),
        )
    )


print(
    "\n=== METRIC POST ROUTE SOURCES ==="
)

for row in metric_routes:

    if row[
        "method"
    ] != "POST":
        continue

    print(
        "\n--- "
        + row[
            "function"
        ]
        + " ---"
    )

    print(
        row[
            "source"
        ]
    )


print("")
print(
    "PRODUCTION_WRITE_PERFORMED=False"
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
    "MODEL_CALLED=False"
)

print(
    "REPORT="
    + str(
        REPORT
    )
)

print(
    "SM3_09C7_B3D_A8_METRIC_POPULATION_AND_OBSERVATION_LINKAGE_AUDIT_COMPLETE"
)
