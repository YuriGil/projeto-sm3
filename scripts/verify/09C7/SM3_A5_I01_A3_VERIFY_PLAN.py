import json
import sys
from pathlib import Path


plan = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8-sig"
    )
)

evidence = json.loads(
    Path(sys.argv[2]).read_text(
        encoding="utf-8-sig"
    )
)


operations = {
    item["consumer"]:
        item
    for item in plan[
        "operations"
    ]
}


checks = [
    plan[
        "contract_version"
    ]
    == "SM3_A5_I01_CANDIDATE_IMPLEMENTATION_PLAN_V1",

    plan[
        "requirement_id"
    ]
    == "A5-R04",

    plan[
        "implementation_unit"
    ]
    == "A5-I01",

    plan[
        "operation_count"
    ]
    == 3,

    set(
        operations
    )
    == {
        "EVIDENCE",
        "PREFERENCE_SIGNAL",
        "SNAPSHOT",
    },

    operations[
        "EVIDENCE"
    ][
        "validator"
    ]
    == "validate_evidence_temporal",

    operations[
        "PREFERENCE_SIGNAL"
    ][
        "validator"
    ]
    == "validate_signal_temporal",

    operations[
        "SNAPSHOT"
    ][
        "validator"
    ]
    == "validate_snapshot_temporal_inputs",

    operations[
        "EVIDENCE"
    ][
        "as_of_binding"
    ]
    == "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

    operations[
        "PREFERENCE_SIGNAL"
    ][
        "as_of_binding"
    ]
    == "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

    operations[
        "SNAPSHOT"
    ][
        "call_style"
    ]
    == "KEYWORD_ONLY_EXACT",

    operations[
        "SNAPSHOT"
    ][
        "keyword_argument_bindings"
    ][
        "as_of"
    ]
    == "request.as_of",

    plan[
        "implementation_strategy"
    ][
        "validation_failure_state_delta"
    ]
    == 0,

    plan[
        "diff_budget"
    ][
        "canonical_worker_mutation_allowed"
    ]
    is False,

    plan[
        "diff_budget"
    ][
        "temporal_module_mutation_allowed"
    ]
    is False,

    plan[
        "candidate_policy"
    ][
        "candidate_generation_authorized"
    ]
    is False,

    plan[
        "candidate_policy"
    ][
        "candidate_generation_requires_plan_adversarial_review"
    ]
    is True,

    plan[
        "implementation_plan_frozen"
    ]
    is True,

    plan[
        "implementation_authorized"
    ]
    is False,

    plan[
        "candidate_generation_authorized"
    ]
    is False,

    plan[
        "production_mutation_authorized"
    ]
    is False,

    len(
        plan[
            "dynamic_test_matrix"
        ]
    )
    == 8,

    evidence[
        "plan_freeze_pass"
    ]
    is True,

    evidence[
        "persistence_pass"
    ]
    is True,
]


print(
    "PLAN_VERIFY_PASS="
    + str(
        all(
            checks
        )
    )
)

print(
    "OPERATION_COUNT="
    + str(
        plan[
            "operation_count"
        )
    )
)

print(
    "DYNAMIC_TEST_COUNT="
    + str(
        len(
            plan[
                "dynamic_test_matrix"
            ]
        )
    )
)

print(
    "CANDIDATE_GENERATION_AUTHORIZED="
    + str(
        plan[
            "candidate_generation_authorized"
        ]
    )
)


raise SystemExit(
    0
    if all(
        checks
    )
    else 1
)