#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path

PREEDIT_CONTRACT = "SM3_PREEDIT_CREATIVE_DIRECTION_V1"
EDITORIAL_CONTEXT_CONTRACT = "SM3_PREEDIT_EDITORIAL_CONTEXT_V1"
USER_OVERRIDE_CONTRACT = "SM3_USER_PREEDIT_DIRECTION_V1"

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha_obj(x):
    return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()

def load_json(path, default=None):
    p = Path(path)
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)

def selected_hypothesis(strategy):
    rid = ((strategy.get("selection") or {}).get("recommended_direction_id"))
    for h in strategy.get("hypotheses") or []:
        if h.get("direction_id") == rid:
            return h
    return None

def hypothesis_projection(h):
    if not isinstance(h, dict):
        return {}
    return {
        "direction_id": h.get("direction_id"),
        "generation_role": h.get("generation_role"),
        "creative_dimensions": h.get("creative_dimensions") or {},
        "platform_adaptations": h.get("platform_adaptations") or {},
        "edit_intent": h.get("edit_intent") or {},
        "experimentable": h.get("experimentable"),
        "confidence": h.get("confidence"),
        "score": h.get("score"),
        "rationale": h.get("rationale"),
        "evidence_refs": h.get("evidence_refs") or [],
    }

def semantic_projection(h):
    p = hypothesis_projection(h)
    return {
        "generation_role": p.get("generation_role"),
        "creative_dimensions": p.get("creative_dimensions") or {},
        "platform_adaptations": p.get("platform_adaptations") or {},
        "edit_intent": p.get("edit_intent") or {},
        "experimentable": p.get("experimentable"),
    }

def fingerprint(h):
    return sha_obj(semantic_projection(h))

def validate_override(x):
    if x is None:
        return None
    if not isinstance(x, dict):
        raise RuntimeError("R30_USER_OVERRIDE_NOT_OBJECT")
    if x.get("contract_version") != USER_OVERRIDE_CONTRACT:
        raise RuntimeError("R30_USER_OVERRIDE_CONTRACT_INVALID")
    requested_dimensions = x.get("requested_dimensions")
    if requested_dimensions is not None and not isinstance(requested_dimensions, dict):
        raise RuntimeError("R30_USER_OVERRIDE_DIMENSIONS_INVALID")
    creative_brief = x.get("creative_brief")
    if creative_brief is not None and not isinstance(creative_brief, str):
        raise RuntimeError("R30_USER_OVERRIDE_BRIEF_INVALID")
    return {
        "contract_version": USER_OVERRIDE_CONTRACT,
        "override_id": x.get("override_id") or ("UPO_" + sha_obj(x)[:24]),
        "created_at": x.get("created_at"),
        "creative_brief": creative_brief or "",
        "requested_dimensions": requested_dimensions or {},
        "platform_specific_requests": x.get("platform_specific_requests") or {},
        "notes": x.get("notes") or "",
        "source": "HUMAN_EXPLICIT",
        "feasibility_status": "PENDING_DOWNSTREAM_VALIDATION"
    }

def effective_direction(recommended, override):
    base = hypothesis_projection(recommended)
    if override is None:
        return {
            "source": "ADAPTIVE_RECOMMENDATION",
            "direction_id": base.get("direction_id"),
            "semantic_fingerprint": fingerprint(recommended),
            "generation_role": base.get("generation_role"),
            "creative_dimensions": base.get("creative_dimensions") or {},
            "platform_adaptations": base.get("platform_adaptations") or {},
            "edit_intent": base.get("edit_intent") or {},
            "experimentable": base.get("experimentable"),
            "human_creative_brief": None,
            "feasibility_status": "RECOMMENDATION_READY"
        }

    # Preserve adaptive recommendation, overlay only the explicit human request
    # in the effective execution intent. This does not mutate the learned prior.
    dims = dict(base.get("creative_dimensions") or {})
    dims.update(override.get("requested_dimensions") or {})

    platforms = dict(base.get("platform_adaptations") or {})
    for k,v in (override.get("platform_specific_requests") or {}).items():
        platforms[k] = v

    body = {
        "source": "HUMAN_EXPLICIT_OVERRIDE",
        "direction_id": base.get("direction_id"),
        "adaptive_semantic_fingerprint": fingerprint(recommended),
        "generation_role": base.get("generation_role"),
        "creative_dimensions": dims,
        "platform_adaptations": platforms,
        "edit_intent": base.get("edit_intent") or {},
        "experimentable": base.get("experimentable"),
        "human_creative_brief": override.get("creative_brief"),
        "human_override_id": override.get("override_id"),
        "feasibility_status": "PENDING_DOWNSTREAM_VALIDATION"
    }
    body["effective_semantic_fingerprint"] = sha_obj({
        "creative_dimensions": dims,
        "platform_adaptations": platforms,
        "edit_intent": body["edit_intent"],
        "human_creative_brief": body["human_creative_brief"]
    })
    return body

def build(root, policy):
    inputs = policy["inputs"]
    strategy = load_json(root / inputs["feedback_strategy"])
    strategy_source = "R29_3_FEEDBACK_STRATEGY"

    if not isinstance(strategy, dict):
        strategy = load_json(root / inputs["fallback_live_strategy"])
        strategy_source = "R28_LIVE_STRATEGY"

    if not isinstance(strategy, dict):
        return {
            "status": "WAITING_FOR_STRATEGY",
            "preedit": None,
            "editorial_context": None,
            "strategy_source": None
        }

    if strategy.get("contract_version") != "SM3_ADAPTIVE_CREATIVE_STRATEGY_V1":
        raise RuntimeError("R30_STRATEGY_CONTRACT_INVALID")

    if strategy.get("status") != "READY":
        return {
            "status": "WAITING_FOR_READY_STRATEGY",
            "preedit": None,
            "editorial_context": None,
            "strategy_source": strategy_source
        }

    selected = selected_hypothesis(strategy)
    if selected is None:
        raise RuntimeError("R30_RECOMMENDED_HYPOTHESIS_MISSING")

    alternatives = []
    for h in strategy.get("hypotheses") or []:
        if h.get("direction_id") == selected.get("direction_id"):
            continue
        p = hypothesis_projection(h)
        p["semantic_fingerprint"] = fingerprint(h)
        alternatives.append(p)

    override_raw = load_json(root / inputs["optional_user_override"])
    override = validate_override(override_raw)
    effective = effective_direction(selected, override)
    recommended = hypothesis_projection(selected)
    recommended["semantic_fingerprint"] = fingerprint(selected)

    feedback_result = load_json(root / inputs["feedback_result"], {}) or {}
    evidence_context = {
        "feedback_status": feedback_result.get("feedback_status"),
        "active_feedback_evidence_count": feedback_result.get("active_feedback_evidence_count"),
        "evidence_type_counts": feedback_result.get("evidence_type_counts") or {},
        "strategy_delta": feedback_result.get("delta") or {},
    }

    status = "READY_USER_OVERRIDE" if override else "READY_RECOMMENDED_DIRECTION"

    preedit = {
        "contract_version": PREEDIT_CONTRACT,
        "generated_at": now(),
        "status": status,
        "strategy_source": strategy_source,
        "strategy_id": strategy.get("strategy_id"),
        "strategy_status": strategy.get("status"),
        "recommended_direction": recommended,
        "alternative_directions": alternatives,
        "user_override": override,
        "effective_direction": effective,
        "evidence_context": evidence_context,
        "next_stage": "EXISTING_EDITORIAL_INTENT_AND_NATIVE_FORMAT_PLANNER",
        "guards": {
            "fixed_style_presets": False,
            "adaptive_recommendation_preserved": True,
            "user_override_rewrites_learned_prior": False,
            "user_override_requires_feasibility_validation": bool(override),
            "bridge_renders_media": False,
            "automatic_publication": False,
            "automatic_reply": False
        }
    }
    preedit["preedit_id"] = "PED_" + sha_obj(preedit)[:24]
    preedit["preedit_sha256"] = sha_obj(preedit)

    editorial_context = {
        "contract_version": EDITORIAL_CONTEXT_CONTRACT,
        "generated_at": now(),
        "target_contract": "NativePublicationArtifactRequest.editorial_context",
        "adaptive_strategy": {
            "strategy_id": strategy.get("strategy_id"),
            "strategy_source": strategy_source,
            "strategy_status": strategy.get("status"),
        },
        "creative_direction": {
            "recommended": recommended,
            "effective": effective,
            "alternatives": alternatives,
        },
        "human_direction": {
            "present": override is not None,
            "override": override,
            "adaptive_prior_preserved": True,
        },
        "evidence_context": evidence_context,
        "planner_handoff": {
            "editorial_intent_contract": "SM3_EDITORIAL_INTENT_V1",
            "editorial_planner": "SM3_NATIVE_FORMAT_PLANNER_V1",
            "publication_artifact_contract": "SM3_PUBLICATION_ARTIFACT_V1",
            "instruction": "COMPILE_EDITORIAL_INTENT_FROM_EFFECTIVE_DIRECTION_BEFORE_RENDERING"
        },
        "guards": {
            "no_parallel_planner": True,
            "no_rendering_in_bridge": True,
            "no_reference_copying": True,
            "no_fake_account_learning": True,
            "automatic_publication": False,
            "automatic_reply": False
        }
    }
    editorial_context["editorial_context_sha256"] = sha_obj(editorial_context)

    return {
        "status": status,
        "preedit": preedit,
        "editorial_context": editorial_context,
        "strategy_source": strategy_source
    }

def persist(root, result):
    state = root / "state" / "preedit_strategy"
    state.mkdir(parents=True, exist_ok=True)

    if result["preedit"] is not None:
        write_json(state / "SM3_PREEDIT_CREATIVE_DIRECTION_CURRENT.json", result["preedit"])
        write_json(state / "SM3_PREEDIT_EDITORIAL_CONTEXT_CURRENT.json", result["editorial_context"])
        hist = state / "history"
        hist.mkdir(exist_ok=True)
        write_json(hist / (result["preedit"]["preedit_sha256"] + ".json"), result["preedit"])

def cycle(root, policy):
    result = build(root, policy)
    persist(root, result)

    p = result.get("preedit") or {}
    h = {
        "contract_version": "SM3_PREEDIT_BRIDGE_HEALTH_V1",
        "ok": True,
        "observed_at": now(),
        "status": result["status"],
        "strategy_source": result.get("strategy_source"),
        "strategy_id": p.get("strategy_id"),
        "preedit_id": p.get("preedit_id"),
        "recommended_direction_id": ((p.get("recommended_direction") or {}).get("direction_id")),
        "effective_source": ((p.get("effective_direction") or {}).get("source")),
        "alternative_direction_count": len(p.get("alternative_directions") or []),
        "user_override_present": p.get("user_override") is not None if p else False,
        "target_contract": "NativePublicationArtifactRequest.editorial_context",
        "existing_editorial_intent_contract": "SM3_EDITORIAL_INTENT_V1",
        "existing_editorial_planner": "SM3_NATIVE_FORMAT_PLANNER_V1",
        "bridge_renders_media": False,
        "automatic_publication": False,
        "automatic_reply": False
    }
    write_json(root / "state" / "preedit_strategy" / "SM3_PREEDIT_BRIDGE_HEALTH.json", h)
    return h

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=os.environ.get("SM3_PROJECT_ROOT", "/project"))
    ap.add_argument("--policy", default=None)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--daemon", action="store_true")
    ap.add_argument("--interval", type=int, default=int(os.environ.get("SM3_R30_INTERVAL_SECONDS", "900")))
    a = ap.parse_args()

    root = Path(a.project_root).resolve()
    pp = Path(a.policy) if a.policy else root / "SM3_09D_A11_A18_R30_PREEDIT_POLICY_v1.json"
    policy = load_json(pp)
    if not isinstance(policy, dict) or policy.get("contract_version") != "SM3_PREEDIT_CREATIVE_DIRECTION_POLICY_V1":
        raise RuntimeError("R30_POLICY_INVALID")

    if a.once:
        h = cycle(root, policy)
        for k,v in h.items():
            if k not in {"contract_version","ok","observed_at"}:
                print("R30_"+k.upper()+"="+str(v))
        print("SM3_09D_A11_A18_R30_PREEDIT_BRIDGE_v1_PASS")
        return

    if not a.daemon:
        raise RuntimeError("R30_MODE_REQUIRED")

    while True:
        started = time.time()
        try:
            h = cycle(root, policy)
            print(
                "R30_CYCLE_PASS|status="+str(h["status"])+
                "|strategy="+str(h["strategy_id"])+
                "|effective="+str(h["effective_source"])+
                "|alternatives="+str(h["alternative_direction_count"]),
                flush=True
            )
        except Exception as e:
            write_json(root / "state" / "preedit_strategy" / "SM3_PREEDIT_BRIDGE_HEALTH.json", {
                "contract_version":"SM3_PREEDIT_BRIDGE_HEALTH_V1",
                "ok":False,
                "observed_at":now(),
                "error":type(e).__name__+":"+str(e),
                "bridge_renders_media":False,
                "automatic_publication":False,
                "automatic_reply":False
            })
            print("R30_CYCLE_FAIL_CLOSED="+type(e).__name__+":"+str(e), file=sys.stderr, flush=True)
        time.sleep(max(1, a.interval-(time.time()-started)))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("SM3_R30_FAIL_CLOSED:"+type(e).__name__+":"+str(e), file=sys.stderr)
        raise SystemExit(1)
