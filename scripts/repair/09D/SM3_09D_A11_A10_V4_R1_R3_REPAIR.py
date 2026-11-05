
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

EXPECTED_ENGINE_SHA = "e7caceffcc0d9e66be16e7d605e3671cb646fcb5ce211bbd11747ac0122dbde6"
EXPECTED_MANIFEST_SHA = "bffbc73363c654c7ef6003bce0273029b25ab02b03a1ee5ea5686aacb4bcf1cd"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def main() -> int:
    root = Path(sys.argv[1]).resolve()
    engine_path = root / "SM3_09D_A11_A10_MINIMAL_FEEDBACK_ENGINE.py"
    manifest_path = root / "SM3_09D_A11_A10_MINIMAL_FEEDBACK_MANIFEST.json"
    repair_dir = root / "reports" / "09D" / "A11_A10_V4_R1_R3_SELECTOR_RETRY"
    report_path = repair_dir / "SM3_09D_A11_A10_V4_R1_R3_SELECTOR_RETRY_REPAIR.json"
    repair_dir.mkdir(parents=True, exist_ok=True)

    if not engine_path.is_file():
        raise RuntimeError(f"ENGINE_MISSING:{engine_path}")
    if not manifest_path.is_file():
        raise RuntimeError(f"MANIFEST_MISSING:{manifest_path}")

    engine_sha_before = sha(engine_path)
    manifest_sha_before = sha(manifest_path)

    print(f"ENGINE_SHA256_BEFORE={engine_sha_before}")
    print(f"MANIFEST_SHA256_BEFORE={manifest_sha_before}")

    if engine_sha_before != EXPECTED_ENGINE_SHA:
        raise RuntimeError(f"ENGINE_SHA_NOT_AUTHORIZED:{engine_sha_before}")
    if manifest_sha_before != EXPECTED_MANIFEST_SHA:
        raise RuntimeError(f"MANIFEST_SHA_NOT_AUTHORIZED:{manifest_sha_before}")

    engine_backup = repair_dir / f"{engine_path.name}.before_v4_r1_r3_{engine_sha_before[:16]}.bak"
    manifest_backup = repair_dir / f"{manifest_path.name}.before_v4_r1_r3_{manifest_sha_before[:16]}.bak"
    shutil.copy2(engine_path, engine_backup)
    shutil.copy2(manifest_path, manifest_backup)

    source = engine_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(engine_path))

    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    required = {
        "proposal_format_schema",
        "build_duplicate_repair_directives",
        "call_model",
        "validate_proposal",
        "main",
    }

    missing = required - set(functions)
    if missing:
        raise RuntimeError("REQUIRED_FUNCTION_MISSING:" + "|".join(sorted(missing)))

    if "call_duplicate_repair_selector" in functions or "apply_duplicate_repair_selections" in functions:
        raise RuntimeError("R3_SELECTOR_REPAIR_ALREADY_PRESENT")

    validator_ast_before = ast.dump(functions["validate_proposal"], include_attributes=False)
    schema_ast_before = ast.dump(functions["proposal_format_schema"], include_attributes=False)

    old_allowed = "            allowed = same_role if same_role else fallback"
    new_allowed = "            allowed = same_role"
    if source.count(old_allowed) != 1:
        raise RuntimeError("SAFE_ALTERNATIVE_POLICY_ANCHOR_INVALID:" + str(source.count(old_allowed)))
    patched = source.replace(old_allowed, new_allowed, 1)

    selector_functions = r'''
def call_duplicate_repair_selector(
    base_url: str,
    model: str,
    directives: list[dict[str, Any]],
    timeout_seconds: int,
    maximum_output_tokens: int,
) -> dict[str, str]:
    if not directives:
        raise GateError("A11_A10_DUPLICATE_REPAIR_DIRECTIVES_REQUIRED")

    properties: dict[str, Any] = {}
    required: list[str] = []
    evidence: dict[str, Any] = {}

    for index, directive in enumerate(directives):
        key = "D" + str(index)
        allowed = directive.get("allowed_replacements")

        if not isinstance(allowed, list):
            raise GateError("A11_A10_DUPLICATE_REPAIR_ALLOWED_INVALID:" + key)

        allowed_ids = sorted({
            str(item.get("candidate_id", ""))
            for item in allowed
            if isinstance(item, dict)
            and str(item.get("candidate_id", "")).strip()
        })

        if not allowed_ids:
            raise GateError("A11_A10_DUPLICATE_REPAIR_NO_SAFE_ALTERNATIVE:" + key)

        properties[key] = {
            "type": "string",
            "enum": allowed_ids,
        }
        required.append(key)
        evidence[key] = {
            "platform": str(directive.get("platform", "")),
            "surface": str(directive.get("surface", "")),
            "timeline_order": int(directive.get("timeline_order", 0)),
            "duplicate_candidate_id": str(directive.get("duplicate_candidate_id", "")),
            "current_role": str(directive.get("current_role", "")),
            "allowed_replacements": allowed,
        }

    schema = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }

    body = {
        "model": model,
        "stream": False,
        "format": schema,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are repairing duplicate candidate selections in an already "
                    "validated editorial proposal. For each key, choose exactly one "
                    "candidate_id from that key's allowed_replacements. Do not invent "
                    "IDs. Return only the schema object. The engine, not you, will apply "
                    "the selected IDs to the rejected proposal."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    evidence,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        "options": {
            "temperature": 0,
            "seed": 42,
            "num_predict": min(maximum_output_tokens, 256),
            "num_ctx": 4096,
        },
        "keep_alive": "10m",
    }

    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            envelope = json.loads(response.read().decode("utf-8"))

        parsed = json.loads(
            envelope.get("message", {}).get("content", "")
        )

    except (urllib.error.URLError, TimeoutError) as exc:
        raise GateError(
            f"A11_A10_DUPLICATE_REPAIR_SELECTOR_UNREACHABLE:{type(exc).__name__}"
        ) from exc

    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        raise GateError(
            f"A11_A10_DUPLICATE_REPAIR_SELECTOR_JSON_INVALID:{type(exc).__name__}"
        ) from exc

    if not isinstance(parsed, dict):
        raise GateError("A11_A10_DUPLICATE_REPAIR_SELECTOR_OUTPUT_INVALID")

    result: dict[str, str] = {}

    for key in required:
        selected = str(parsed.get(key, ""))
        allowed_ids = set(properties[key]["enum"])

        if selected not in allowed_ids:
            raise GateError(
                "A11_A10_DUPLICATE_REPAIR_SELECTOR_CHOICE_INVALID:" + key
            )

        result[key] = selected

    return result


def apply_duplicate_repair_selections(
    proposal: dict[str, Any],
    directives: list[dict[str, Any]],
    selections: dict[str, str],
    catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    repaired = json.loads(
        json.dumps(
            proposal,
            ensure_ascii=False,
        )
    )

    platforms = repaired.get("platforms")
    if not isinstance(platforms, list):
        raise GateError("A11_A10_DUPLICATE_REPAIR_PROPOSAL_PLATFORMS_INVALID")

    selected_by_scope: dict[tuple[str, str], set[str]] = {}

    for index, directive in enumerate(directives):
        key = "D" + str(index)
        selected_id = str(selections.get(key, ""))
        allowed = directive.get("allowed_replacements")

        if not isinstance(allowed, list):
            raise GateError("A11_A10_DUPLICATE_REPAIR_ALLOWED_INVALID:" + key)

        allowed_ids = {
            str(item.get("candidate_id", ""))
            for item in allowed
            if isinstance(item, dict)
        }

        if selected_id not in allowed_ids:
            raise GateError("A11_A10_DUPLICATE_REPAIR_SELECTION_NOT_ALLOWED:" + key)

        candidate = catalog.get(selected_id)
        if not isinstance(candidate, dict):
            raise GateError(
                "A11_A10_DUPLICATE_REPAIR_SELECTED_CANDIDATE_UNKNOWN:" + selected_id
            )

        selected_role = str(candidate.get("role", ""))
        expected_role = str(directive.get("current_role", ""))

        if not selected_role or selected_role != expected_role:
            raise GateError("A11_A10_DUPLICATE_REPAIR_ROLE_MISMATCH:" + selected_id)

        scope = (
            str(directive.get("platform", "")),
            str(directive.get("surface", "")),
        )

        already_selected = selected_by_scope.setdefault(scope, set())

        if selected_id in already_selected:
            raise GateError(
                "A11_A10_DUPLICATE_REPAIR_SELECTION_COLLISION:" + selected_id
            )

        already_selected.add(selected_id)

        order = int(directive.get("timeline_order", 0))
        if order < 1:
            raise GateError("A11_A10_DUPLICATE_REPAIR_ORDER_INVALID:" + key)

        duplicate_id = str(directive.get("duplicate_candidate_id", ""))

        matching_platforms = [
            platform
            for platform in platforms
            if isinstance(platform, dict)
            and str(platform.get("platform", "")) == scope[0]
            and str(platform.get("surface", "")) == scope[1]
        ]

        if len(matching_platforms) != 1:
            raise GateError(
                "A11_A10_DUPLICATE_REPAIR_SCOPE_CARDINALITY_INVALID:" + repr(scope)
            )

        timeline = matching_platforms[0].get("timeline")
        if not isinstance(timeline, list):
            raise GateError(
                "A11_A10_DUPLICATE_REPAIR_TIMELINE_INVALID:" + repr(scope)
            )

        position = order - 1
        if position >= len(timeline):
            raise GateError("A11_A10_DUPLICATE_REPAIR_ORDER_OUT_OF_RANGE:" + key)

        item = timeline[position]
        if not isinstance(item, dict):
            raise GateError("A11_A10_DUPLICATE_REPAIR_TIMELINE_ITEM_INVALID:" + key)

        if str(item.get("candidate_id", "")) != duplicate_id:
            raise GateError("A11_A10_DUPLICATE_REPAIR_TARGET_DRIFT:" + key)

        item["candidate_id"] = selected_id
        item["role"] = selected_role

    return repaired
'''.strip()

    call_model_index = patched.find("def call_model(")
    if call_model_index < 0:
        raise RuntimeError("CALL_MODEL_INSERTION_POINT_NOT_FOUND")

    patched = (
        patched[:call_model_index]
        + selector_functions
        + "\n\n\n"
        + patched[call_model_index:]
    )

    old_retry_block = '''        if last_errors:
            attempt_evidence["validation_errors_from_previous_attempt"] = last_errors
            if isinstance(previous_candidate, dict):
                attempt_evidence["rejected_proposal_from_previous_attempt"] = previous_candidate
                repair_directives = build_duplicate_repair_directives(
                    previous_candidate,
                    last_errors,
                    by_id,
                )
                if repair_directives:
                    attempt_evidence["repair_directives"] = repair_directives
                    print("A11_A10_DUPLICATE_REPAIR_DIRECTIVE_PASS=" + str(len(repair_directives)))'''

    new_retry_block = '''        if last_errors:
            attempt_evidence["validation_errors_from_previous_attempt"] = last_errors
            if isinstance(previous_candidate, dict):
                attempt_evidence["rejected_proposal_from_previous_attempt"] = previous_candidate
                repair_directives = build_duplicate_repair_directives(
                    previous_candidate,
                    last_errors,
                    by_id,
                )
                if repair_directives:
                    print(
                        "A11_A10_DUPLICATE_REPAIR_DIRECTIVE_PASS="
                        + str(len(repair_directives))
                    )
                    repair_selections = call_duplicate_repair_selector(
                        str(policy["base_url"]),
                        model,
                        repair_directives,
                        int(policy["timeout_seconds"]),
                        int(policy["maximum_output_tokens"]),
                    )
                    candidate = apply_duplicate_repair_selections(
                        previous_candidate,
                        repair_directives,
                        repair_selections,
                        by_id,
                    )
                    previous_candidate = candidate
                    last_errors = validate_proposal(
                        candidate,
                        challenge["challenge_id"],
                        by_id,
                    )
                    if not last_errors:
                        proposal = candidate
                        print(
                            "A11_A10_DUPLICATE_REPAIR_MODEL_SELECTION_PASS="
                            + str(len(repair_selections))
                        )
                        break
                    print(
                        "A11_A10_LOCAL_MODEL_ATTEMPT_REJECTED="
                        + "|".join(last_errors)
                    )
                    continue'''

    if patched.count(old_retry_block) != 1:
        raise RuntimeError(
            "MAIN_DUPLICATE_RETRY_BLOCK_ANCHOR_INVALID:"
            + str(patched.count(old_retry_block))
        )

    patched = patched.replace(old_retry_block, new_retry_block, 1)

    patched_tree = ast.parse(patched, filename=str(engine_path))
    patched_functions = {
        node.name: node
        for node in patched_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    required_after = {
        "proposal_format_schema",
        "build_duplicate_repair_directives",
        "call_duplicate_repair_selector",
        "apply_duplicate_repair_selections",
        "call_model",
        "validate_proposal",
        "main",
    }

    if not required_after.issubset(patched_functions):
        raise RuntimeError("R3_FUNCTION_SET_INVALID")

    validator_unchanged = (
        validator_ast_before
        == ast.dump(
            patched_functions["validate_proposal"],
            include_attributes=False,
        )
    )

    full_schema_unchanged = (
        schema_ast_before
        == ast.dump(
            patched_functions["proposal_format_schema"],
            include_attributes=False,
        )
    )

    helper_text = ast.get_source_segment(
        patched,
        patched_functions["build_duplicate_repair_directives"],
    ) or ""

    selector_text = ast.get_source_segment(
        patched,
        patched_functions["call_duplicate_repair_selector"],
    ) or ""

    apply_text = ast.get_source_segment(
        patched,
        patched_functions["apply_duplicate_repair_selections"],
    ) or ""

    main_text = ast.get_source_segment(
        patched,
        patched_functions["main"],
    ) or ""

    same_role_only_pass = (
        "allowed = same_role" in helper_text
        and "same_role if same_role else fallback" not in helper_text
    )

    selector_schema_pass = all([
        '"format": schema' in selector_text,
        '"temperature": 0' in selector_text,
        '"seed": 42' in selector_text,
        '"/api/chat"' in selector_text,
        "allowed_replacements" in selector_text,
    ])

    deterministic_apply_pass = all([
        'item["candidate_id"] = selected_id' in apply_text,
        'item["role"] = selected_role' in apply_text,
        "selected_role != expected_role" in apply_text,
        "SELECTION_COLLISION" in apply_text,
    ])

    retry_branch_pass = all([
        "call_duplicate_repair_selector(" in main_text,
        "apply_duplicate_repair_selections(" in main_text,
        "A11_A10_DUPLICATE_REPAIR_MODEL_SELECTION_PASS=" in main_text,
        "continue" in main_text,
    ])

    helper_node = patched_functions["build_duplicate_repair_directives"]
    apply_node = patched_functions["apply_duplicate_repair_selections"]

    isolated = ast.Module(
        body=[helper_node, apply_node],
        type_ignores=[],
    )

    class DummyGateError(RuntimeError):
        pass

    namespace = {
        "Any": Any,
        "json": json,
        "GateError": DummyGateError,
    }

    exec(
        compile(isolated, "<r3-pure-audit>", "exec"),
        namespace,
    )

    helper = namespace["build_duplicate_repair_directives"]
    apply_fn = namespace["apply_duplicate_repair_selections"]

    test_catalog = {
        "C_STENCIL_A": {"role": "STENCIL_CONTEXT", "source_file": "a.mp4"},
        "C_STENCIL_B": {"role": "STENCIL_CONTEXT", "source_file": "b.mp4"},
        "C_FINAL": {"role": "FINAL_RESULT", "source_file": "c.mp4"},
        "C_PROCESS": {"role": "PROCESS_CONTEXT", "source_file": "d.mp4"},
    }

    test_proposal = {
        "platforms": [
            {
                "platform": "TIKTOK",
                "surface": "FOR_YOU",
                "timeline": [
                    {
                        "order": 1,
                        "candidate_id": "C_STENCIL_A",
                        "role": "STENCIL_CONTEXT",
                        "label": "a",
                    },
                    {
                        "order": 2,
                        "candidate_id": "C_STENCIL_A",
                        "role": "STENCIL_CONTEXT",
                        "label": "b",
                    },
                    {
                        "order": 3,
                        "candidate_id": "C_FINAL",
                        "role": "FINAL_RESULT",
                        "label": "c",
                    },
                ],
            },
        ],
    }

    directives = helper(
        test_proposal,
        ["TIMELINE_CANDIDATES_NOT_UNIQUE:('TIKTOK', 'FOR_YOU')"],
        test_catalog,
    )

    pure_test_pass = len(directives) == 1

    if pure_test_pass:
        allowed_ids = {
            item["candidate_id"]
            for item in directives[0]["allowed_replacements"]
        }
        pure_test_pass = allowed_ids == {"C_STENCIL_B"}

    if pure_test_pass:
        repaired = apply_fn(
            test_proposal,
            directives,
            {"D0": "C_STENCIL_B"},
            test_catalog,
        )

        ids = [
            item["candidate_id"]
            for item in repaired["platforms"][0]["timeline"]
        ]

        roles = [
            item["role"]
            for item in repaired["platforms"][0]["timeline"]
        ]

        pure_test_pass = all([
            ids == [
                "C_STENCIL_A",
                "C_STENCIL_B",
                "C_FINAL",
            ],
            roles[1] == "STENCIL_CONTEXT",
            test_proposal["platforms"][0]["timeline"][1]["candidate_id"]
            == "C_STENCIL_A",
        ])

    static_validation_pass = all([
        validator_unchanged,
        full_schema_unchanged,
        same_role_only_pass,
        selector_schema_pass,
        deterministic_apply_pass,
        retry_branch_pass,
        pure_test_pass,
    ])

    if not static_validation_pass:
        raise RuntimeError(
            "R3_STATIC_VALIDATION_FAILED:"
            + json.dumps(
                {
                    "validator_unchanged": validator_unchanged,
                    "full_schema_unchanged": full_schema_unchanged,
                    "same_role_only_pass": same_role_only_pass,
                    "selector_schema_pass": selector_schema_pass,
                    "deterministic_apply_pass": deterministic_apply_pass,
                    "retry_branch_pass": retry_branch_pass,
                    "pure_test_pass": pure_test_pass,
                },
                sort_keys=True,
            )
        )

    engine_path.write_text(patched, encoding="utf-8")
    engine_sha_after = sha(engine_path)

    if engine_sha_after == engine_sha_before:
        raise RuntimeError("R3_ENGINE_SHA_UNCHANGED")

    manifest = load_json(manifest_path)
    artifacts = manifest.get("artifacts")

    if not isinstance(artifacts, list):
        raise RuntimeError("MANIFEST_ARTIFACTS_INVALID")

    matches = [
        item
        for item in artifacts
        if isinstance(item, dict)
        and item.get("file_name") == engine_path.name
    ]

    if len(matches) != 1:
        raise RuntimeError(
            "MANIFEST_ENGINE_ENTRY_CARDINALITY_INVALID:"
            + str(len(matches))
        )

    engine_entry = matches[0]
    manifest_engine_sha_before = str(engine_entry.get("sha256", ""))
    engine_entry["sha256"] = engine_sha_after

    for size_key in ("size_bytes", "bytes"):
        if size_key in engine_entry:
            engine_entry[size_key] = engine_path.stat().st_size

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest_sha_after = sha(manifest_path)

    persisted = load_json(manifest_path)
    persisted_matches = [
        item
        for item in persisted.get("artifacts", [])
        if isinstance(item, dict)
        and item.get("file_name") == engine_path.name
    ]

    manifest_update_pass = (
        len(persisted_matches) == 1
        and str(persisted_matches[0].get("sha256", "")).lower()
        == engine_sha_after
    )

    if not manifest_update_pass:
        raise RuntimeError("R3_MANIFEST_UPDATE_FAILED")

    ast.parse(
        engine_path.read_text(encoding="utf-8-sig"),
        filename=str(engine_path),
    )

    report = {
        "contract_version": "SM3_A11_A10_DUPLICATE_REPAIR_MODEL_SELECTOR_V1",
        "repair_revision": "V4-R1-R3",
        "engine_sha256_before": engine_sha_before,
        "engine_sha256_after": engine_sha_after,
        "manifest_sha256_before": manifest_sha_before,
        "manifest_sha256_after": manifest_sha_after,
        "manifest_engine_sha256_before": manifest_engine_sha_before,
        "manifest_engine_sha256_after": engine_sha_after,
        "validator_unchanged": validator_unchanged,
        "full_output_schema_unchanged": full_schema_unchanged,
        "same_role_alternatives_only": same_role_only_pass,
        "repair_model_selects_candidate": True,
        "engine_selects_candidate": False,
        "engine_applies_model_selection_deterministically": True,
        "selector_temperature": 0,
        "selector_seed": 42,
        "selector_paid_provider": False,
        "maximum_attempts_mutated": False,
        "fail_closed_mutated": False,
        "production_state_mutation_performed": False,
        "static_validation_pass": static_validation_pass,
        "manifest_update_pass": manifest_update_pass,
        "repair_pass": True,
        "engine_backup": str(engine_backup),
        "manifest_backup": str(manifest_backup),
    }

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"ENGINE_SHA256_AFTER={engine_sha_after}")
    print(f"MANIFEST_SHA256_AFTER={manifest_sha_after}")
    print(f"VALIDATOR_UNCHANGED={validator_unchanged}")
    print(f"FULL_OUTPUT_SCHEMA_UNCHANGED={full_schema_unchanged}")
    print(f"SAME_ROLE_ALTERNATIVES_ONLY_PASS={same_role_only_pass}")
    print(f"SELECTOR_SCHEMA_PASS={selector_schema_pass}")
    print(f"DETERMINISTIC_APPLY_PASS={deterministic_apply_pass}")
    print(f"RETRY_BRANCH_PASS={retry_branch_pass}")
    print(f"PURE_FUNCTION_TEST_PASS={pure_test_pass}")
    print(f"STATIC_VALIDATION_PASS={static_validation_pass}")
    print(f"MANIFEST_UPDATE_PASS={manifest_update_pass}")
    print("MODEL_SELECTS_REPLACEMENT=True")
    print("ENGINE_SELECTS_REPLACEMENT=False")
    print("ENGINE_APPLIES_MODEL_SELECTION=True")
    print("MAXIMUM_ATTEMPTS_MUTATED=False")
    print("FAIL_CLOSED_MUTATED=False")
    print("PRODUCTION_STATE_MUTATION_PERFORMED=False")
    print("REPAIR_PASS=True")
    print(f"REPAIR_REPORT={report_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            "A11_A10_V4_R1_R3_REPAIR_FAILED="
            + type(exc).__name__
            + ":"
            + str(exc)
        )
        raise
