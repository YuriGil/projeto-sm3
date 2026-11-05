import json
import sys
from pathlib import Path

contract = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8-sig"
    )
)

evidence = json.loads(
    Path(sys.argv[2]).read_text(
        encoding="utf-8-sig"
    )
)

checks = [
    contract["contract_version"]
    == "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_V1",

    contract["requirement_id"]
    == "A5-R04",

    contract["implementation_unit"]
    == "A5-I01",

    contract["consumer_count"]
    == 3,

    set(
        contract[
            "public_validator_set"
        ]
    )
    == {
        "validate_evidence_temporal",
        "validate_signal_temporal",
        "validate_snapshot_temporal_inputs",
    },

    contract[
        "bindings"
    ][
        "EVIDENCE"
    ][
        "as_of_binding"
    ]
    == "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

    contract[
        "bindings"
    ][
        "PREFERENCE_SIGNAL"
    ][
        "as_of_binding"
    ]
    == "SERVER_UTC_NOW_AT_HANDLER_ENTRY",

    contract[
        "bindings"
    ][
        "SNAPSHOT"
    ][
        "as_of_binding"
    ]
    == "request.as_of",

    contract[
        "global_invariants"
    ][
        "validation_before_mutation"
    ]
    is True,

    contract[
        "global_invariants"
    ][
        "temporal_validity_error_fail_closed"
    ]
    is True,

    contract[
        "global_invariants"
    ][
        "private_parse_timestamp_direct_call_allowed"
    ]
    is False,

    contract[
        "authorization"
    ][
        "binding_frozen"
    ]
    is True,

    contract[
        "authorization"
    ][
        "implementation_authorized"
    ]
    is False,

    contract[
        "authorization"
    ][
        "candidate_generation_authorized"
    ]
    is False,

    evidence[
        "binding_contract_freeze_pass"
    ]
    is True,

    evidence[
        "role_discovery_pass"
    ]
    is True,

    evidence[
        "request_coverage_pass"
    ]
    is True,
]

print(
    "CONTRACT_VERIFY_PASS="
    + str(
        all(checks)
    )
)

print(
    "SNAPSHOT_VALIDATOR_PARAMETERS="
    + "|".join(
        evidence[
            "snapshot_validator_parameters"
        ]
    )
)

print(
    "SNAPSHOT_EVIDENCE_PARAMETER="
    + str(
        evidence[
            "snapshot_parameter_roles"
        ][
            "evidence"
        ]
    )
)

print(
    "SNAPSHOT_SIGNAL_PARAMETER="
    + str(
        evidence[
            "snapshot_parameter_roles"
        ][
            "signal"
        ]
    )
)

print(
    "SNAPSHOT_AS_OF_PARAMETER="
    + str(
        evidence[
            "snapshot_parameter_roles"
        ][
            "as_of"
        ]
    )
)

raise SystemExit(
    0 if all(checks) else 1
)