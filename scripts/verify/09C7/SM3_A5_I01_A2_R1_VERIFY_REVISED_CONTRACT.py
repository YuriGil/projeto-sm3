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


e = contract["bindings"]["EVIDENCE"]

s = contract["bindings"]["PREFERENCE_SIGNAL"]

sn = contract["bindings"]["SNAPSHOT"]


checks = [
    contract["contract_version"]
    == "SM3_A5_I01_TEMPORAL_BINDING_CONTRACT_V2",

    contract["revision"]
    == 2,

    e["temporal_input_fields"]
    == [
        "source_date",
        "observed_at",
        "valid_until",
    ],

    e["validator_mapping_keys"]
    == [
        "source_date",
        "observed_at",
        "valid_until",
    ],

    e["coverage_non_vacuous"]
    is True,

    s["temporal_input_fields"]
    == [
        "window_started_at",
        "window_ended_at",
    ],

    s["validator_mapping_keys"]
    == [
        "window_started_at",
        "window_ended_at",
    ],

    s["coverage_non_vacuous"]
    is True,

    sn["call_style"]
    == "KEYWORD_ONLY_EXACT",

    sn["required_keyword_only_parameters"]
    == [
        "as_of",
        "evidence",
        "signals",
    ],

    sn["keyword_argument_bindings"]["as_of"]
    == "request.as_of",

    sn[
        "internal_as_of_forwarding_evidence_proven"
    ]
    is True,

    sn[
        "internal_as_of_forwarding_signal_proven"
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
        "remediation_pass"
    ]
    is True,

    evidence[
        "preserved_semantics_pass"
    ]
    is True,

    evidence[
        "authorization_closed"
    ]
    is True,
]


print(
    "REVISED_CONTRACT_VERIFY_PASS="
    + str(
        all(checks)
    )
)

print(
    "EVIDENCE_TEMPORAL_INPUT_FIELDS="
    + "|".join(
        e[
            "temporal_input_fields"
        ]
    )
)

print(
    "SIGNAL_TEMPORAL_INPUT_FIELDS="
    + "|".join(
        s[
            "temporal_input_fields"
        ]
    )
)

print(
    "SNAPSHOT_CALL_STYLE="
    + sn[
        "call_style"
    ]
)

print(
    "SNAPSHOT_REQUIRED_KEYWORD_ONLY_PARAMETERS="
    + "|".join(
        sn[
            "required_keyword_only_parameters"
        ]
    )
)

raise SystemExit(
    0 if all(checks) else 1
)