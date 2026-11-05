from __future__ import annotations

import json
import sys
from pathlib import Path


A = Path(sys.argv[1])
B = Path(sys.argv[2])
POLICY = Path(sys.argv[3])
REPORT = Path(sys.argv[4])


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

policy = json.loads(
    POLICY.read_text(
        encoding="utf-8-sig"
    )
)


if (
    policy.get(
        "contract_version"
    )
    != "SM3_TEST_MUTATION_ACCOUNTING_POLICY_V1"
):

    raise SystemExit(
        "A4_A2_MUTATION_POLICY_VERSION_INVALID"
    )


protected_prefixes = [
    "platform_dynamics_evidence/",
    "platform_preference_signals/",
    "platform_dynamics_snapshots/",
    "platform_hypotheses/",
    "platform_predictions/",
    "platform_drift_signals/",
    "platform_experiments/",
    "content_temporal_signatures/",
]


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


changed_paths = sorted(
    path
    for path in (
        paths_a
        & paths_b
    )
    if (
        map_a[
            path
        ].get(
            "sha256"
        )
        !=
        map_b[
            path
        ].get(
            "sha256"
        )
    )
)


def protected(
    path: str,
) -> bool:

    return any(
        path.startswith(
            prefix
        )
        for prefix in protected_prefixes
    )


allowed = []
unknown = []
protected_violations = []


def classify_added(
    path,
    item,
):

    if protected(
        path
    ):

        protected_violations.append({
            "mutation":
                "ADDED",

            "path":
                path,

            "item":
                item,
        })

        return

    if path.startswith(
        "culture_runner_watchdog/snapshots/"
    ):

        metadata = item.get(
            "json_metadata"
        )

        if (
            isinstance(
                metadata,
                dict,
            )
            and
            metadata.get(
                "contract_version"
            )
            == "SM3_RUNNER_WATCHDOG_V1"
            and
            metadata.get(
                "store_version"
            )
            == "SM3_RUNNER_WATCHDOG_STORE_V1"
        ):

            allowed.append({
                "mutation":
                    "ADDED",

                "classification":
                    "RECOGNIZED_WATCHDOG_IMMUTABLE_SNAPSHOT",

                "path":
                    path,
            })

            return

    unknown.append({
        "mutation":
            "ADDED",

        "path":
            path,

        "item":
            item,
    })


def classify_changed(
    path,
    before,
    after,
):

    if protected(
        path
    ):

        protected_violations.append({
            "mutation":
                "CHANGED",

            "path":
                path,

            "before":
                before,

            "after":
                after,
        })

        return

    if path == (
        "culture_runner_watchdog/latest.json"
    ):

        metadata = after.get(
            "json_metadata"
        )

        if (
            isinstance(
                metadata,
                dict,
            )
            and
            metadata.get(
                "contract_version"
            )
            == "SM3_RUNNER_WATCHDOG_V1"
        ):

            allowed.append({
                "mutation":
                    "CHANGED",

                "classification":
                    "RECOGNIZED_WATCHDOG_POINTER_UPDATE",

                "path":
                    path,
            })

            return

    unknown.append({
        "mutation":
            "CHANGED",

        "path":
            path,

        "before":
            before,

        "after":
            after,
    })


for path in added_paths:

    classify_added(
        path,
        map_b[
            path
        ],
    )


for path in changed_paths:

    classify_changed(
        path,
        map_a[
            path
        ],
        map_b[
            path
        ],
    )


for path in removed_paths:

    item = {
        "mutation":
            "REMOVED",

        "path":
            path,

        "item":
            map_a[
                path
            ],
    }

    if protected(
        path
    ):

        protected_violations.append(
            item
        )

    else:

        unknown.append(
            item
        )


mutation_accounting_pass = (
    len(
        protected_violations
    )
    == 0
    and
    len(
        unknown
    )
    == 0
)


report = {
    "phase":
        "09C7-B3E-A4-A2",

    "status":
        "SCOPE_AWARE_MUTATION_ACCOUNTING_COMPLETE",

    "policy_version":
        policy.get(
            "contract_version"
        ),

    "protected_prefixes":
        protected_prefixes,

    "file_count_a":
        a.get(
            "file_count"
        ),

    "file_count_b":
        b.get(
            "file_count"
        ),

    "global_file_count_equal":
        a.get(
            "file_count"
        )
        ==
        b.get(
            "file_count"
        ),

    "added_count":
        len(
            added_paths
        ),

    "changed_count":
        len(
            changed_paths
        ),

    "removed_count":
        len(
            removed_paths
        ),

    "allowed_background_mutation_count":
        len(
            allowed
        ),

    "unknown_mutation_count":
        len(
            unknown
        ),

    "protected_scope_mutation_count":
        len(
            protected_violations
        ),

    "allowed_background_mutations":
        allowed,

    "unknown_mutations":
        unknown,

    "protected_scope_mutations":
        protected_violations,

    "mutation_accounting_pass":
        mutation_accounting_pass,

    "global_file_count_used_as_gate":
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
    "=== SCOPE-AWARE MUTATION ACCOUNTING ==="
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
    "GLOBAL_FILE_COUNT_EQUAL="
    + str(
        report[
            "global_file_count_equal"
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
    "CHANGED_COUNT="
    + str(
        report[
            "changed_count"
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
    "ALLOWED_BACKGROUND_MUTATION_COUNT="
    + str(
        report[
            "allowed_background_mutation_count"
        ]
    )
)

print(
    "UNKNOWN_MUTATION_COUNT="
    + str(
        report[
            "unknown_mutation_count"
        ]
    )
)

print(
    "PROTECTED_SCOPE_MUTATION_COUNT="
    + str(
        report[
            "protected_scope_mutation_count"
        ]
    )
)

print(
    "MUTATION_ACCOUNTING_PASS="
    + str(
        report[
            "mutation_accounting_pass"
        ]
    )
)

print(
    "GLOBAL_FILE_COUNT_USED_AS_GATE=False"
)


if allowed:

    print(
        "\n=== ALLOWED BACKGROUND MUTATIONS ==="
    )

    for item in allowed:

        print(
            json.dumps(
                item,
                ensure_ascii=False,
                default=str,
            )
        )


if unknown:

    print(
        "\n=== UNKNOWN MUTATIONS ==="
    )

    for item in unknown:

        print(
            json.dumps(
                item,
                ensure_ascii=False,
                default=str,
            )
        )


if protected_violations:

    print(
        "\n=== PROTECTED SCOPE VIOLATIONS ==="
    )

    for item in protected_violations:

        print(
            json.dumps(
                item,
                ensure_ascii=False,
                default=str,
            )
        )


if not mutation_accounting_pass:

    raise SystemExit(
        1
    )
