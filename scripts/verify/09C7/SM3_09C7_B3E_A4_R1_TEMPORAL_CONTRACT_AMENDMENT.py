from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


FREEZE = Path(sys.argv[1])
ATTACK = Path(sys.argv[2])
ENGINE = Path(sys.argv[3])
REVISED = Path(sys.argv[4])
REPORT = Path(sys.argv[5])


EXPECTED_FREEZE_SHA = (
    "3c6ad11d8d6240158c8c890fe7c7428a"
    "e0d9dd323be17c52fbdce738b0a21399"
)

EXPECTED_ATTACK_SHA = (
    "5a1f6b5e029d12e7a240bb9d4a8bb875"
    "e24503544720d6081ec89c6e892e370c"
)

EXPECTED_ENGINE_SHA = (
    "4a8b8c10c89bb02931aafae4c59d45ca"
    "6dfe16ba20e92e12c830deae78aa3753"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def write_json(path: Path, value):
    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


freeze_sha = sha256(
    FREEZE
)

attack_sha = sha256(
    ATTACK
)

engine_sha = sha256(
    ENGINE
)


if freeze_sha != EXPECTED_FREEZE_SHA:
    raise SystemExit(
        "A4_R1_FREEZE_SHA_MISMATCH:"
        + freeze_sha
    )


if attack_sha != EXPECTED_ATTACK_SHA:
    raise SystemExit(
        "A4_R1_ATTACK_SHA_MISMATCH:"
        + attack_sha
    )


if engine_sha != EXPECTED_ENGINE_SHA:
    raise SystemExit(
        "A4_R1_ENGINE_SHA_MISMATCH:"
        + engine_sha
    )


freeze = load_json(
    FREEZE
)

attack = load_json(
    ATTACK
)


# ============================================================
# 4. VERIFY ATTACK FINDINGS
# ============================================================

findings = {
    row.get("attack_id"):
        row
    for row in attack.get(
        "findings",
        []
    )
}


c001 = findings.get(
    "C001"
)

i001 = findings.get(
    "I001"
)


attack_preconditions = [
    attack.get("status")
    == "TEMPORAL_VALIDITY_ADVERSARIAL_ATTACK_COMPLETE",

    attack.get("attack_count")
    == 21,

    attack.get("pass_count")
    == 19,

    attack.get("contract_probe_gap_count")
    == 1,

    c001 is not None,

    c001.get("finding")
    == "GAP",

    c001.get("classification")
    == "CONTRACT_PROBE",

    c001.get("expected")
    == "source_date <= observed_at",

    i001 is not None,

    i001.get("finding")
    == "GAP",

    i001.get("severity")
    == "CRITICAL",
]


if not all(
    attack_preconditions
):
    raise SystemExit(
        "A4_R1_ATTACK_FINDING_PRECONDITION_FAILED"
    )


# ============================================================
# 5. CORRECT I001 CLASSIFICATION USING AST
# ============================================================

engine_source = ENGINE.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(
    engine_source,
    filename=str(
        ENGINE
    ),
)


imports = set()

calls = []


def dotted_name(node):
    if isinstance(
        node,
        ast.Name,
    ):
        return node.id

    if isinstance(
        node,
        ast.Attribute,
    ):
        parent = dotted_name(
            node.value
        )

        if parent:
            return (
                parent
                + "."
                + node.attr
            )

        return node.attr

    return None


for node in ast.walk(
    tree
):

    if isinstance(
        node,
        ast.Import,
    ):

        for alias in node.names:

            imports.add(
                alias.name
            )

    elif isinstance(
        node,
        ast.ImportFrom,
    ):

        if node.module:

            imports.add(
                node.module
            )

    elif isinstance(
        node,
        ast.Call,
    ):

        name = dotted_name(
            node.func
        )

        if name:
            calls.append(
                name
            )


network_or_process_imports = sorted(
    item
    for item in imports
    if (
        item == "requests"
        or
        item.startswith(
            "requests."
        )
        or
        item == "httpx"
        or
        item.startswith(
            "httpx."
        )
        or
        item == "urllib"
        or
        item.startswith(
            "urllib."
        )
        or
        item == "socket"
        or
        item.startswith(
            "socket."
        )
        or
        item == "subprocess"
        or
        item.startswith(
            "subprocess."
        )
    )
)


dangerous_exact_calls = {
    "open",
    "os.remove",
    "os.unlink",
    "os.rename",
    "os.replace",
    "subprocess.run",
    "subprocess.call",
    "subprocess.Popen",
    "requests.get",
    "requests.post",
    "httpx.get",
    "httpx.post",
}


dangerous_suffixes = {
    ".write_text",
    ".write_bytes",
    ".unlink",
    ".rename",
}


dangerous_calls = sorted(
    set(
        name
        for name in calls
        if (
            name in dangerous_exact_calls
            or
            any(
                name.endswith(
                    suffix
                )
                for suffix
                in dangerous_suffixes
            )
        )
    )
)


replace_calls = sorted(
    set(
        name
        for name in calls
        if name.endswith(
            ".replace"
        )
    )
)


i001_false_positive = (
    not network_or_process_imports
    and
    not dangerous_calls
    and
    "raw.replace"
    in replace_calls
)


if not i001_false_positive:
    raise SystemExit(
        "A4_R1_I001_FALSE_POSITIVE_NOT_CONFIRMED"
    )


# ============================================================
# 6. PROBE CURRENT ENGINE
# It SHOULD still accept the invalid order at this stage.
# ============================================================

spec = importlib.util.spec_from_file_location(
    "sm3_temporal_validity",
    ENGINE,
)

module = importlib.util.module_from_spec(
    spec
)

assert spec.loader is not None

spec.loader.exec_module(
    module
)


probe_record = {
    "evidence_id":
        "PDE_contract_probe",

    "source_date":
        "2026-09-27T19:00:00+00:00",

    "observed_at":
        "2026-09-27T18:00:00+00:00",

    "valid_until":
        "2026-10-27T00:00:00+00:00",
}


current_engine_accepts_invalid_order = False

current_engine_error_code = None


try:
    module.validate_evidence_temporal(
        probe_record,
        "2026-09-27T20:00:00+00:00",
    )

    current_engine_accepts_invalid_order = True

except module.TemporalValidityError as exc:

    current_engine_error_code = exc.code


if not current_engine_accepts_invalid_order:
    raise SystemExit(
        "A4_R1_ENGINE_STATE_UNEXPECTED:"
        + str(
            current_engine_error_code
        )
    )


# ============================================================
# 7. AMEND CONTRACT
# ============================================================

revised = copy.deepcopy(
    freeze
)


previous_revision = copy.deepcopy(
    revised.get(
        "revision_metadata",
        {}
    )
)


revised[
    "revision_metadata"
] = {
    "revision":
        "R2",

    "amendment_phase":
        "09C7-B3E-A4-R1",

    "parent_revised_freeze_sha256":
        freeze_sha,

    "root_parent_freeze_sha256":
        previous_revision.get(
            "parent_freeze_sha256"
        ),

    "previous_revision":
        previous_revision.get(
            "revision"
        ),

    "source_attack_sha256":
        attack_sha,

    "reason":
        (
            "Adversarial attack found missing evidence "
            "causal ordering invariant"
        ),

    "production_source_modified":
        False,

    "production_state_modified":
        False,
}


temporal = revised[
    "temporal_validity"
]


temporal[
    "evidence_source_date_must_not_exceed_observed_at"
] = True


temporal[
    "evidence_temporal_order"
] = (
    "source_date <= observed_at <= as_of"
)


temporal[
    "evidence_temporal_causality_fail_closed"
] = True


temporal[
    "source_after_observation_error_code"
] = (
    "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_AFTER_OBSERVATION"
)


temporal[
    "source_date_equal_observed_at_allowed"
] = True


temporal[
    "ordering_validation_precedes_age_calculation"
] = True


# Preserve the existing expiry semantics:
#
# valid_until absent -> allowed
# valid_until present -> as_of <= valid_until
#
# No additional invented relationship is introduced.

temporal[
    "hard_expiry_semantics_unchanged"
] = True


# ============================================================
# 8. ATTACK-HARNESS CORRECTION RECORD
# ============================================================

revised[
    "verification_corrections"
] = {
    "A4_A1_I001": {
        "original_classification":
            "CRITICAL_ENGINE_GAP",

        "corrected_classification":
            "AUDITOR_FALSE_POSITIVE",

        "cause":
            (
                "Naive substring scanner matched "
                "str.replace used for ISO Z normalization"
            ),

        "matched_call":
            "raw.replace",

        "filesystem_replace_detected":
            False,

        "network_or_process_imports":
            network_or_process_imports,

        "dangerous_calls":
            dangerous_calls,

        "reattack_must_use_ast":
            True,
    }
}


# ============================================================
# 9. ROLLOUT
# ============================================================

revised[
    "rollout"
] = [
    "A4_R2_TEMPORAL_ENGINE_REMEDIATION",
    "A4_A2_TEMPORAL_ADVERSARIAL_REATTACK",
    "A4_A3_INTEGRATION_PREFLIGHT",
    "A5_HYPOTHESIS_STORE",
    "A6_PREDICTION_OUTCOME_AND_ERROR",
    "A7_DRIFT_ENGINE",
    "A8_EXPERIMENT_STORE",
    "A9_TEMPORAL_SIGNATURE",
    "A10_SNAPSHOT_V2",
    "A11_METRIC_ACQUISITION_BINDING",
    "A12_REAL_SIGNAL_POPULATION",
    "A13_TASTE_MODEL_FREEZE",
    "A14_STRATEGY_FUSION",
]


write_json(
    REVISED,
    revised,
)


revised_sha = sha256(
    REVISED
)


# ============================================================
# 10. VERIFY AMENDMENT
# ============================================================

loaded = load_json(
    REVISED
)

tv = loaded[
    "temporal_validity"
]


contract_checks = {
    "SOURCE_DATE_LTE_OBSERVED_AT":
        tv.get(
            "evidence_source_date_must_not_exceed_observed_at"
        )
        is True,

    "TEMPORAL_ORDER_EXACT":
        tv.get(
            "evidence_temporal_order"
        )
        == "source_date <= observed_at <= as_of",

    "CAUSALITY_FAIL_CLOSED":
        tv.get(
            "evidence_temporal_causality_fail_closed"
        )
        is True,

    "ERROR_CODE_FROZEN":
        tv.get(
            "source_after_observation_error_code"
        )
        == (
            "PLATFORM_TEMPORAL_EVIDENCE_"
            "SOURCE_AFTER_OBSERVATION"
        ),

    "EQUALITY_ALLOWED":
        tv.get(
            "source_date_equal_observed_at_allowed"
        )
        is True,

    "ORDER_BEFORE_AGE":
        tv.get(
            "ordering_validation_precedes_age_calculation"
        )
        is True,

    "I001_FALSE_POSITIVE_RECORDED":
        loaded.get(
            "verification_corrections",
            {},
        ).get(
            "A4_A1_I001",
            {},
        ).get(
            "corrected_classification"
        )
        == "AUDITOR_FALSE_POSITIVE",

    "AST_REATTACK_REQUIRED":
        loaded.get(
            "verification_corrections",
            {},
        ).get(
            "A4_A1_I001",
            {},
        ).get(
            "reattack_must_use_ast"
        )
        is True,
}


all_contract_checks_pass = all(
    contract_checks.values()
)


if not all_contract_checks_pass:
    raise SystemExit(
        "A4_R1_CONTRACT_AMENDMENT_VERIFY_FAILED"
    )


# ============================================================
# 11. REPORT
# ============================================================

report = {
    "phase":
        "09C7-B3E-A4-R1",

    "status":
        "TEMPORAL_CONTRACT_AMENDMENT_COMPLETE",

    "parent_freeze_sha256":
        freeze_sha,

    "adversarial_attack_sha256":
        attack_sha,

    "engine_sha256":
        engine_sha,

    "revised_freeze_sha256":
        revised_sha,

    "contract_checks":
        contract_checks,

    "contract_amended":
        True,

    "source_date_lte_observed_at_frozen":
        True,

    "i001_auditor_false_positive_confirmed":
        i001_false_positive,

    "replace_calls":
        replace_calls,

    "dangerous_calls":
        dangerous_calls,

    "network_or_process_imports":
        network_or_process_imports,

    "current_engine_accepts_invalid_order":
        current_engine_accepts_invalid_order,

    "engine_remediation_required":
        True,

    "runtime_integration_allowed":
        False,

    "next_gate":
        "09C7-B3E-A4-R2_TEMPORAL_ENGINE_REMEDIATION",

    "production_source_modified":
        False,

    "production_state_modified":
        False,

    "production_restart_executed":
        False,

    "route_called":
        False,

    "network_request_performed":
        False,

    "provider_called":
        False,

    "model_called":
        False,
}


write_json(
    REPORT,
    report,
)


report_sha = sha256(
    REPORT
)


print(
    "=== TEMPORAL CONTRACT AMENDMENT ==="
)


for name,value in contract_checks.items():

    print(
        name
        + "="
        + str(
            value
        )
    )


print("")
print(
    "CONTRACT_AMENDED=True"
)

print(
    "SOURCE_DATE_LTE_OBSERVED_AT_FROZEN=True"
)

print(
    "I001_AUDITOR_FALSE_POSITIVE_CONFIRMED="
    + str(
        i001_false_positive
    )
)

print(
    "REPLACE_CALLS="
    + json.dumps(
        replace_calls
    )
)

print(
    "DANGEROUS_CALLS="
    + json.dumps(
        dangerous_calls
    )
)

print(
    "CURRENT_ENGINE_ACCEPTS_INVALID_ORDER="
    + str(
        current_engine_accepts_invalid_order
    )
)

print(
    "ENGINE_REMEDIATION_REQUIRED=True"
)

print(
    "RUNTIME_INTEGRATION_ALLOWED=False"
)

print(
    "NEXT_GATE="
    "09C7-B3E-A4-R2_TEMPORAL_ENGINE_REMEDIATION"
)

print(
    "REVISED_FREEZE_SHA256="
    + revised_sha
)

print(
    "REPORT_SHA256="
    + report_sha
)

print(
    "SM3_09C7_B3E_A4_R1_TEMPORAL_CONTRACT_AMENDMENT_COMPLETE"
)
