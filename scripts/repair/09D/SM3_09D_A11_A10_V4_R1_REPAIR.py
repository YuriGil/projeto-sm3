from __future__ import annotations

import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

EXPECTED_ENGINE_SHA = "8121e44a017805018d6016b56378968144d8d1d1cda26869595632b9cfc497ee"
EXPECTED_MANIFEST_SHA = "0e604dd3e57275b908a32cd1f9c415b4bfdc5f60bd4c88823a054e776fbe3c1e"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def main() -> int:
    root = Path(sys.argv[1]).resolve()
    engine_path = root / "SM3_09D_A11_A10_MINIMAL_FEEDBACK_ENGINE.py"
    manifest_path = root / "SM3_09D_A11_A10_MINIMAL_FEEDBACK_MANIFEST.json"
    repair_dir = root / "reports" / "09D" / "A11_A10_V4_R1_DUPLICATE_RETRY"
    report_path = repair_dir / "SM3_09D_A11_A10_V4_R1_DUPLICATE_AWARE_RETRY.json"
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

    engine_backup = repair_dir / f"{engine_path.name}.before_v4_r1_{engine_sha_before[:16]}.bak"
    manifest_backup = repair_dir / f"{manifest_path.name}.before_v4_r1_{manifest_sha_before[:16]}.bak"
    shutil.copy2(engine_path, engine_backup)
    shutil.copy2(manifest_path, manifest_backup)

    source = engine_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(engine_path))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    required = {"proposal_format_schema", "call_model", "validate_proposal", "main"}
    missing = required - set(functions)
    if missing:
        raise RuntimeError("REQUIRED_FUNCTION_MISSING:" + "|".join(sorted(missing)))
    if "build_duplicate_repair_directives" in functions or "def build_duplicate_repair_directives(" in source:
        raise RuntimeError("DUPLICATE_REPAIR_ALREADY_PRESENT")

    validator_ast_before = ast.dump(functions["validate_proposal"], include_attributes=False)
    schema_ast_before = ast.dump(functions["proposal_format_schema"], include_attributes=False)

    helper_source = r"""
def build_duplicate_repair_directives(
    proposal: dict[str, Any],
    validation_errors: list[str],
    catalog: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not any(
        str(error).startswith("TIMELINE_CANDIDATES_NOT_UNIQUE:")
        for error in validation_errors
    ):
        return []

    platforms = proposal.get("platforms")
    if not isinstance(platforms, list):
        return []

    directives: list[dict[str, Any]] = []

    for platform in platforms:
        if not isinstance(platform, dict):
            continue

        timeline = platform.get("timeline")
        if not isinstance(timeline, list):
            continue

        ids = [
            str(item.get("candidate_id", ""))
            for item in timeline
            if isinstance(item, dict)
        ]

        if len(ids) != len(timeline) or len(ids) == len(set(ids)):
            continue

        used_ids = {candidate_id for candidate_id in ids if candidate_id}
        seen: set[str] = set()

        for index, item in enumerate(timeline):
            if not isinstance(item, dict):
                continue

            candidate_id = str(item.get("candidate_id", ""))
            if not candidate_id:
                continue

            if candidate_id not in seen:
                seen.add(candidate_id)
                continue

            current = catalog.get(candidate_id)
            current_role = (
                str(current.get("role", ""))
                if isinstance(current, dict)
                else str(item.get("role", ""))
            )

            same_role: list[dict[str, Any]] = []
            fallback: list[dict[str, Any]] = []

            for alternative_id in sorted(catalog):
                if alternative_id in used_ids:
                    continue

                alternative = catalog.get(alternative_id)
                if not isinstance(alternative, dict):
                    continue

                alternative_role = str(alternative.get("role", ""))
                if not alternative_role:
                    continue

                record = {
                    "candidate_id": str(alternative_id),
                    "role": alternative_role,
                    "source_file": str(alternative.get("source_file", "")),
                }
                fallback.append(record)

                if alternative_role == current_role:
                    same_role.append(record)

            allowed = same_role if same_role else fallback
            if not allowed:
                continue

            directives.append({
                "platform": str(platform.get("platform", "")),
                "surface": str(platform.get("surface", "")),
                "timeline_order": index + 1,
                "duplicate_candidate_id": candidate_id,
                "current_role": current_role,
                "kept_candidate_ids": sorted(used_ids),
                "allowed_replacements": allowed,
                "instruction": (
                    "Replace ONLY this duplicated timeline candidate. "
                    "Choose one candidate_id from allowed_replacements, "
                    "copy its exact role, keep this timeline order unchanged, "
                    "and do not alter unrelated proposal fields."
                ),
            })

    return directives
""".strip()

    call_model_index = source.find("def call_model(")
    if call_model_index < 0:
        raise RuntimeError("CALL_MODEL_INSERTION_POINT_NOT_FOUND")

    patched = source[:call_model_index] + helper_source + "\n\n\n" + source[call_model_index:]

    old_prompt_fragment = '"satisfy the schema exactly."'
    new_prompt_fragment = (
        '"satisfy the schema exactly. "'
        '"candidate_id values inside each individual platform timeline MUST be pairwise distinct; "'
        '"never repeat the same candidate_id in one timeline. "'
        '"If user evidence contains validation_errors_from_previous_attempt, "'
        '"rejected_proposal_from_previous_attempt, or repair_directives, treat the previous proposal "'
        '"as a draft and repair ONLY the listed validation failures. "'
        '"For TIMELINE_CANDIDATES_NOT_UNIQUE, preserve every unrelated field and replace each listed "'
        '"duplicate timeline position using one candidate_id from that directive allowed_replacements "'
        '"list, with the exact role paired with that candidate."'
    )
    if patched.count(old_prompt_fragment) != 1:
        raise RuntimeError("CALL_MODEL_RETRY_PROMPT_ANCHOR_INVALID:" + str(patched.count(old_prompt_fragment)))
    patched = patched.replace(old_prompt_fragment, new_prompt_fragment, 1)

    proposal_anchor = "    proposal = None\n    attempts = 0"
    proposal_replacement = "    proposal = None\n    previous_candidate = None\n    attempts = 0"
    if patched.count(proposal_anchor) != 1:
        raise RuntimeError("MAIN_PROPOSAL_ANCHOR_INVALID:" + str(patched.count(proposal_anchor)))
    patched = patched.replace(proposal_anchor, proposal_replacement, 1)

    retry_anchor = (
        '        if last_errors:\n'
        '            attempt_evidence["validation_errors_from_previous_attempt"] = last_errors'
    )
    retry_replacement = (
        '        if last_errors:\n'
        '            attempt_evidence["validation_errors_from_previous_attempt"] = last_errors\n'
        '            if isinstance(previous_candidate, dict):\n'
        '                attempt_evidence["rejected_proposal_from_previous_attempt"] = previous_candidate\n'
        '                repair_directives = build_duplicate_repair_directives(\n'
        '                    previous_candidate,\n'
        '                    last_errors,\n'
        '                    by_id,\n'
        '                )\n'
        '                if repair_directives:\n'
        '                    attempt_evidence["repair_directives"] = repair_directives\n'
        '                    print("A11_A10_DUPLICATE_REPAIR_DIRECTIVE_PASS=" + str(len(repair_directives)))'
    )
    if patched.count(retry_anchor) != 1:
        raise RuntimeError("MAIN_RETRY_ANCHOR_INVALID:" + str(patched.count(retry_anchor)))
    patched = patched.replace(retry_anchor, retry_replacement, 1)

    validation_anchor = '        last_errors = validate_proposal(candidate, challenge["challenge_id"], by_id)'
    validation_replacement = (
        '        previous_candidate = candidate\n'
        '        last_errors = validate_proposal(candidate, challenge["challenge_id"], by_id)'
    )
    if patched.count(validation_anchor) != 1:
        raise RuntimeError("MAIN_VALIDATION_ANCHOR_INVALID:" + str(patched.count(validation_anchor)))
    patched = patched.replace(validation_anchor, validation_replacement, 1)

    patched_tree = ast.parse(patched, filename=str(engine_path))
    patched_functions = {
        node.name: node
        for node in patched_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    required_after = {
        "proposal_format_schema",
        "build_duplicate_repair_directives",
        "call_model",
        "validate_proposal",
        "main",
    }
    if not required_after.issubset(patched_functions):
        raise RuntimeError("FUNCTION_SET_INVALID_AFTER_PATCH")

    validator_unchanged = (
        validator_ast_before
        == ast.dump(patched_functions["validate_proposal"], include_attributes=False)
    )
    full_schema_unchanged = (
        schema_ast_before
        == ast.dump(patched_functions["proposal_format_schema"], include_attributes=False)
    )

    main_text = ast.get_source_segment(patched, patched_functions["main"]) or ""
    call_text = ast.get_source_segment(patched, patched_functions["call_model"]) or ""

    main_previous_candidate_pass = all([
        "previous_candidate = None" in main_text,
        '"rejected_proposal_from_previous_attempt"] = previous_candidate' in main_text,
        "build_duplicate_repair_directives(" in main_text,
        "previous_candidate = candidate" in main_text,
    ])

    retry_prompt_pass = all([
        "pairwise distinct" in call_text,
        "repair_directives" in call_text,
        "allowed_replacements" in call_text,
        "replace each listed duplicate" in call_text,
    ])

    temperature_preserved = '"temperature": 0' in call_text
    seed_preserved = '"seed": 42' in call_text
    api_chat_preserved = '"/api/chat"' in call_text
    format_schema_preserved = '"format": schema' in call_text

    helper_node = patched_functions["build_duplicate_repair_directives"]
    isolated = ast.Module(body=[helper_node], type_ignores=[])
    namespace = {"Any": Any}
    exec(compile(isolated, "<duplicate-repair-audit>", "exec"), namespace)
    helper = namespace["build_duplicate_repair_directives"]

    test_catalog = {
        "C_STENCIL_A": {"role": "STENCIL_CONTEXT", "source_file": "a.mp4"},
        "C_STENCIL_B": {"role": "STENCIL_CONTEXT", "source_file": "b.mp4"},
        "C_FINAL": {"role": "FINAL_RESULT", "source_file": "c.mp4"},
        "C_PROCESS": {"role": "PROCESS_CONTEXT", "source_file": "d.mp4"},
    }
    test_proposal = {
        "platforms": [{
            "platform": "TIKTOK",
            "surface": "FOR_YOU",
            "timeline": [
                {"order": 1, "candidate_id": "C_STENCIL_A", "role": "STENCIL_CONTEXT", "label": ""},
                {"order": 2, "candidate_id": "C_STENCIL_A", "role": "STENCIL_CONTEXT", "label": ""},
                {"order": 3, "candidate_id": "C_FINAL", "role": "FINAL_RESULT", "label": ""},
            ],
        }],
    }

    directives = helper(
        test_proposal,
        ["TIMELINE_CANDIDATES_NOT_UNIQUE:('TIKTOK', 'FOR_YOU')"],
        test_catalog,
    )

    helper_test_pass = len(directives) == 1
    if helper_test_pass:
        directive = directives[0]
        allowed_ids = {item["candidate_id"] for item in directive["allowed_replacements"]}
        helper_test_pass = all([
            directive["platform"] == "TIKTOK",
            directive["surface"] == "FOR_YOU",
            directive["timeline_order"] == 2,
            directive["duplicate_candidate_id"] == "C_STENCIL_A",
            "C_STENCIL_A" not in allowed_ids,
            "C_STENCIL_B" in allowed_ids,
        ])

    static_validation_pass = all([
        validator_unchanged,
        full_schema_unchanged,
        main_previous_candidate_pass,
        retry_prompt_pass,
        temperature_preserved,
        seed_preserved,
        api_chat_preserved,
        format_schema_preserved,
        helper_test_pass,
    ])

    if not static_validation_pass:
        raise RuntimeError(
            "STATIC_VALIDATION_FAILED:"
            + json.dumps({
                "validator_unchanged": validator_unchanged,
                "full_schema_unchanged": full_schema_unchanged,
                "main_previous_candidate_pass": main_previous_candidate_pass,
                "retry_prompt_pass": retry_prompt_pass,
                "temperature_preserved": temperature_preserved,
                "seed_preserved": seed_preserved,
                "api_chat_preserved": api_chat_preserved,
                "format_schema_preserved": format_schema_preserved,
                "helper_test_pass": helper_test_pass,
            }, sort_keys=True)
        )

    engine_path.write_text(patched, encoding="utf-8")
    engine_sha_after = sha(engine_path)
    if engine_sha_after == engine_sha_before:
        raise RuntimeError("ENGINE_SHA_UNCHANGED")

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
        raise RuntimeError("MANIFEST_ENGINE_ENTRY_CARDINALITY_INVALID:" + str(len(matches)))

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
        and str(persisted_matches[0].get("sha256", "")).lower() == engine_sha_after
    )
    if not manifest_update_pass:
        raise RuntimeError("MANIFEST_UPDATE_FAILED")

    ast.parse(
        engine_path.read_text(encoding="utf-8-sig"),
        filename=str(engine_path),
    )

    report = {
        "contract_version": "SM3_A11_A10_DUPLICATE_AWARE_MODEL_RETRY_V1",
        "repair_revision": "V4-R1",
        "engine_sha256_before": engine_sha_before,
        "engine_sha256_after": engine_sha_after,
        "manifest_sha256_before": manifest_sha_before,
        "manifest_sha256_after": manifest_sha_after,
        "manifest_engine_sha256_before": manifest_engine_sha_before,
        "manifest_engine_sha256_after": engine_sha_after,
        "validator_unchanged": validator_unchanged,
        "full_output_schema_unchanged": full_schema_unchanged,
        "previous_rejected_proposal_forwarded": main_previous_candidate_pass,
        "duplicate_repair_directives_enabled": True,
        "repair_directives_choose_candidate": False,
        "model_remains_candidate_selector": True,
        "temperature_preserved": temperature_preserved,
        "seed_preserved": seed_preserved,
        "api_chat_preserved": api_chat_preserved,
        "format_schema_preserved": format_schema_preserved,
        "maximum_attempts_mutated": False,
        "fail_closed_mutated": False,
        "production_state_mutation_performed": False,
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
    print(f"PREVIOUS_REJECTED_PROPOSAL_FORWARD_PASS={main_previous_candidate_pass}")
    print(f"RETRY_PROMPT_PASS={retry_prompt_pass}")
    print(f"DUPLICATE_DIRECTIVE_HELPER_TEST_PASS={helper_test_pass}")
    print("MODEL_REMAINS_CANDIDATE_SELECTOR=True")
    print("DETERMINISTIC_CANDIDATE_REPLACEMENT_PERFORMED=False")
    print(f"TEMPERATURE_PRESERVED={temperature_preserved}")
    print(f"SEED_PRESERVED={seed_preserved}")
    print(f"API_CHAT_PRESERVED={api_chat_preserved}")
    print(f"FORMAT_SCHEMA_PRESERVED={format_schema_preserved}")
    print(f"STATIC_VALIDATION_PASS={static_validation_pass}")
    print(f"MANIFEST_UPDATE_PASS={manifest_update_pass}")
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
        print(f"A11_A10_V4_R1_REPAIR_FAILED={type(exc).__name__}:{exc}")
        raise
