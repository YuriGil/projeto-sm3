from __future__ import annotations

import json
import sys
from pathlib import Path


A = Path(sys.argv[1])
B = Path(sys.argv[2])
REPORT = Path(sys.argv[3])


a = json.loads(
    A.read_text(
        encoding="utf-8-sig"
    )
)

b = json.loads(
    B.read_text(
        encoding="utf-8-sig"
    )
)


map_a = {
    item[
        "path"
    ]:
        item
    for item in a.get(
        "files",
        []
    )
}


map_b = {
    item[
        "path"
    ]:
        item
    for item in b.get(
        "files",
        []
    )
}


paths_a = set(
    map_a
)

paths_b = set(
    map_b
)


added_paths = sorted(
    paths_b
    - paths_a
)


removed_paths = sorted(
    paths_a
    - paths_b
)


common_paths = sorted(
    paths_a
    & paths_b
)


changed_paths = []


for path in common_paths:

    before = map_a[
        path
    ]

    after = map_b[
        path
    ]

    if before.get(
        "sha256"
    ) != after.get(
        "sha256"
    ):

        changed_paths.append(
            path
        )


added = [
    map_b[
        path
    ]
    for path in added_paths
]


removed = [
    map_a[
        path
    ]
    for path in removed_paths
]


changed = [
    {
        "path":
            path,

        "before":
            map_a[
                path
            ],

        "after":
            map_b[
                path
            ],
    }
    for path in changed_paths
]


idle_delta_detected = bool(
    added
    or removed
    or changed
)


report = {
    "phase":
        "09C7-B3E-A4-R2-F1-S1",

    "status":
        "PRODUCTION_STATE_CONCURRENT_WRITER_AUDIT_COMPLETE",

    "snapshot_a_captured_at":
        a.get(
            "captured_at"
        ),

    "snapshot_b_captured_at":
        b.get(
            "captured_at"
        ),

    "file_count_a":
        a.get(
            "file_count"
        ),

    "file_count_b":
        b.get(
            "file_count"
        ),

    "added_count":
        len(
            added
        ),

    "removed_count":
        len(
            removed
        ),

    "changed_count":
        len(
            changed
        ),

    "idle_delta_detected":
        idle_delta_detected,

    "added":
        added,

    "removed":
        removed,

    "changed":
        changed,

    "latest_a":
        a.get(
            "latest_20",
            [],
        ),

    "latest_b":
        b.get(
            "latest_20",
            [],
        ),

    "audit_production_write_performed":
        False,

    "audit_route_called":
        False,

    "audit_network_request_performed":
        False,

    "audit_provider_called":
        False,

    "audit_model_called":
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


print(
    "=== PRODUCTION STATE IDLE DELTA ==="
)

print(
    "FILE_COUNT_A="
    + str(
        report[
            "file_count_a"
        ]
    )
)

print(
    "FILE_COUNT_B="
    + str(
        report[
            "file_count_b"
        ]
    )
)

print(
    "ADDED_COUNT="
    + str(
        report[
            "added_count"
        ]
    )
)

print(
    "REMOVED_COUNT="
    + str(
        report[
            "removed_count"
        ]
    )
)

print(
    "CHANGED_COUNT="
    + str(
        report[
            "changed_count"
        ]
    )
)

print(
    "IDLE_DELTA_DETECTED="
    + str(
        report[
            "idle_delta_detected"
        ]
    )
)


if added:

    print(
        "\n=== ADDED ==="
    )

    for item in added:

        print(
            item[
                "mtime_utc"
            ]
            + " | "
            + item[
                "path"
            ]
            + " | "
            + item[
                "sha256"
            ]
        )

        if item.get(
            "json_metadata"
        ):

            print(
                "  META="
                + json.dumps(
                    item[
                        "json_metadata"
                    ],
                    ensure_ascii=False,
                    default=str,
                )
            )


if changed:

    print(
        "\n=== CHANGED ==="
    )

    for item in changed:

        print(
            item[
                "path"
            ]
        )

        print(
            "  BEFORE_SHA="
            + item[
                "before"
            ][
                "sha256"
            ]
        )

        print(
            "  AFTER_SHA="
            + item[
                "after"
            ][
                "sha256"
            ]
        )


if removed:

    print(
        "\n=== REMOVED ==="
    )

    for item in removed:

        print(
            item[
                "path"
            ]
        )


print(
    "\nAUDIT_PRODUCTION_WRITE_PERFORMED=False"
)

print(
    "AUDIT_ROUTE_CALLED=False"
)

print(
    "AUDIT_NETWORK_REQUEST_PERFORMED=False"
)

print(
    "AUDIT_PROVIDER_CALLED=False"
)

print(
    "AUDIT_MODEL_CALLED=False"
)

print(
    "SM3_09C7_B3E_A4_R2_F1_S1_CONCURRENT_WRITER_AUDIT_COMPLETE"
)
