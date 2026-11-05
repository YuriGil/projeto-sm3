#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, subprocess, sys, time
from pathlib import Path

EVIDENCE_CONTRACT = "SM3_STRATEGY_EVIDENCE_BINDING_V1"
RESULT_CONTRACT = "SM3_STRATEGY_FEEDBACK_RESULT_V1"

def utcnow():
    return dt.datetime.now(dt.timezone.utc)

def now():
    return utcnow().isoformat()

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

def parse_time(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None

def is_alive(e, t):
    vu = parse_time(e.get("valid_until"))
    return vu is None or vu >= t

def collect_evidence(root, policy):
    t = utcnow()
    active = {}
    expired = []
    invalid = []
    source_stats = []
    max_per = int(policy.get("max_evidence_per_source_file", 64))

    for rel in policy["sources"]:
        p = root / rel
        x = load_json(p, {}) or {}
        items = list(x.get("evidence") or [])[:max_per]
        accepted = 0
        for e in items:
            if not isinstance(e, dict) or e.get("contract_version") != EVIDENCE_CONTRACT or not e.get("evidence_id"):
                invalid.append({"source": rel, "reason": "INVALID_CONTRACT_OR_ID"})
                continue
            eid = str(e["evidence_id"])
            digest = sha_obj(e)
            if eid in active:
                if active[eid]["sha256"] != digest:
                    raise RuntimeError("R29_3_EVIDENCE_ID_COLLISION:" + eid)
                continue
            if not is_alive(e, t):
                expired.append(eid)
                continue
            active[eid] = {"evidence": e, "sha256": digest, "source": rel}
            accepted += 1
        source_stats.append({
            "source": rel,
            "file_present": p.is_file(),
            "declared_count": len(items),
            "accepted_active_count": accepted,
        })
    return [v["evidence"] for v in active.values()], expired, invalid, source_stats

def direction_semantic_projection(h):
    if not isinstance(h, dict):
        return {}
    return {
        "generation_role": h.get("generation_role"),
        "creative_dimensions": h.get("creative_dimensions") or {},
        "platform_adaptations": h.get("platform_adaptations") or {},
        "edit_intent": h.get("edit_intent") or {},
        "experimentable": h.get("experimentable"),
    }

def selected_hypothesis(strategy):
    rid = ((strategy.get("selection") or {}).get("recommended_direction_id"))
    for h in strategy.get("hypotheses") or []:
        if h.get("direction_id") == rid:
            return h
    return None

def semantic_fingerprint(strategy):
    h = selected_hypothesis(strategy)
    if not h:
        return None
    return sha_obj(direction_semantic_projection(h))

def strategy_snapshot(strategy):
    h = selected_hypothesis(strategy)
    return {
        "strategy_id": strategy.get("strategy_id"),
        "status": strategy.get("status"),
        "recommended_direction_id": ((strategy.get("selection") or {}).get("recommended_direction_id")),
        "selected_semantic_fingerprint": semantic_fingerprint(strategy),
        "selected_generation_role": h.get("generation_role") if h else None,
        "selected_creative_dimensions": h.get("creative_dimensions") if h else None,
        "hypothesis_count": len(strategy.get("hypotheses") or []),
        "evidence_summary": strategy.get("evidence_summary") or {},
        "next_stage": strategy.get("next_stage"),
    }

def compare(prev, new):
    if not prev:
        return {
            "classification": "INITIAL_FEEDBACK_COMPILE",
            "semantic_direction_changed": False,
            "status_changed": False,
            "evidence_only_refresh": False,
        }
    pf = prev.get("selected_semantic_fingerprint")
    nf = new.get("selected_semantic_fingerprint")
    sem_changed = bool(pf and nf and pf != nf)
    status_changed = prev.get("status") != new.get("status")
    if sem_changed:
        cls = "SEMANTIC_RECOMMENDATION_CHANGED"
    elif status_changed:
        cls = "STRATEGY_STATUS_CHANGED"
    else:
        cls = "EVIDENCE_REFRESH_NO_SEMANTIC_CHANGE"
    return {
        "classification": cls,
        "semantic_direction_changed": sem_changed,
        "status_changed": status_changed,
        "evidence_only_refresh": not sem_changed and not status_changed,
    }

def compile_strategy(root, ctx_path, out_path):
    engine = root / "SM3_09D_A11_A18_R28_ADAPTIVE_CREATIVE_STRATEGY_ENGINE_v1.py"
    policy = root / "SM3_09D_A11_A18_R28_ADAPTIVE_CREATIVE_STRATEGY_POLICY_v1.json"
    if not engine.is_file():
        raise RuntimeError("R29_3_R28_ENGINE_MISSING")
    if not policy.is_file():
        raise RuntimeError("R29_3_R28_POLICY_MISSING")
    q = subprocess.run(
        [sys.executable, str(engine), "compile", "--context", str(ctx_path), "--policy", str(policy), "--output", str(out_path)],
        capture_output=True, text=True
    )
    if q.returncode != 0:
        raise RuntimeError("R29_3_R28_COMPILE_FAILED:" + (q.stderr or q.stdout)[-2000:])
    out = load_json(out_path)
    if not isinstance(out, dict) or out.get("contract_version") != "SM3_ADAPTIVE_CREATIVE_STRATEGY_V1":
        raise RuntimeError("R29_3_R28_OUTPUT_INVALID")
    return out

def cycle(root, policy):
    base_path = root / "state" / "adaptive_strategy" / "contexts" / "SM3_R28_LIVE_CONTEXT_CURRENT.json"
    if not base_path.is_file():
        raise RuntimeError("R29_3_BASE_R28_CONTEXT_MISSING")
    base = load_json(base_path)
    if not isinstance(base, dict) or base.get("contract_version") != "SM3_ADAPTIVE_CREATIVE_CONTEXT_V1":
        raise RuntimeError("R29_3_BASE_R28_CONTEXT_INVALID")

    extra, expired, invalid, source_stats = collect_evidence(root, policy)

    merged = json.loads(json.dumps(base))
    original = list(merged.get("evidence") or [])
    by_id = {}
    for e in original:
        if isinstance(e, dict) and e.get("evidence_id"):
            by_id[str(e["evidence_id"])] = e
    for e in extra:
        by_id[str(e["evidence_id"])] = e
    merged["evidence"] = list(by_id.values())
    merged["feedback_loop"] = {
        "contract_version": "SM3_STRATEGY_FEEDBACK_CONTEXT_BINDING_V1",
        "generated_at": now(),
        "base_context_id": base.get("context_id"),
        "base_context_sha256": base.get("context_sha256"),
        "extra_active_evidence_count": len(extra),
        "expired_evidence_excluded_count": len(expired),
        "invalid_evidence_count": len(invalid),
        "source_stats": source_stats,
        "automatic_publication": False,
        "automatic_reply": False,
        "automatic_irreversible_strategy_change": False,
    }
    merged.pop("context_sha256", None)
    merged["context_sha256"] = sha_obj(merged)

    state = root / "state" / "social_observer" / "feedback_loop"
    state.mkdir(parents=True, exist_ok=True)
    ctx_path = state / "SM3_STRATEGY_FEEDBACK_CONTEXT_CURRENT.json"
    strategy_path = state / "SM3_STRATEGY_FEEDBACK_STRATEGY_CURRENT.json"
    prev_result = load_json(state / "SM3_STRATEGY_FEEDBACK_RESULT_CURRENT.json", {}) or {}
    prev_snapshot = prev_result.get("current_strategy") if prev_result else None

    write_json(ctx_path, merged)
    strategy = compile_strategy(root, ctx_path, strategy_path)
    current = strategy_snapshot(strategy)
    delta = compare(prev_snapshot, current)

    real_account = sum(1 for e in extra if e.get("source_type") == "OWN_ACCOUNT_OBSERVATION")
    human = sum(1 for e in extra if e.get("source_type") == "HUMAN_PREFERENCE")
    inference = sum(1 for e in extra if e.get("source_type") == "INFERENCE")

    if len(extra) == 0:
        feedback_status = "BASE_CONTEXT_ONLY_WAITING_FOR_LIVE_EVIDENCE"
    elif real_account == 0:
        feedback_status = "LIVE_NON_ACCOUNT_EVIDENCE_BOUND"
    else:
        feedback_status = "LIVE_ACCOUNT_EVIDENCE_BOUND"

    result = {
        "contract_version": RESULT_CONTRACT,
        "generated_at": now(),
        "feedback_status": feedback_status,
        "base_context_id": base.get("context_id"),
        "derived_context_sha256": merged["context_sha256"],
        "active_feedback_evidence_count": len(extra),
        "expired_evidence_excluded_count": len(expired),
        "invalid_evidence_count": len(invalid),
        "evidence_type_counts": {
            "OWN_ACCOUNT_OBSERVATION": real_account,
            "HUMAN_PREFERENCE": human,
            "INFERENCE": inference,
        },
        "current_strategy": current,
        "delta": delta,
        "guards": {
            "base_r28_context_mutated": False,
            "fake_account_learning": False,
            "expired_evidence_used": False,
            "causal_claim_made": False,
            "automatic_publication": False,
            "automatic_reply": False,
            "automatic_irreversible_strategy_change": False,
        },
    }
    result["result_sha256"] = sha_obj(result)
    write_json(state / "SM3_STRATEGY_FEEDBACK_RESULT_CURRENT.json", result)
    hist = state / "history"
    hist.mkdir(exist_ok=True)
    write_json(hist / (result["result_sha256"] + ".json"), result)
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=os.environ.get("SM3_PROJECT_ROOT", "/project"))
    ap.add_argument("--policy", default=None)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--daemon", action="store_true")
    ap.add_argument("--interval", type=int, default=int(os.environ.get("SM3_R29_3_INTERVAL_SECONDS", "900")))
    a = ap.parse_args()

    root = Path(a.project_root).resolve()
    pp = Path(a.policy) if a.policy else root / "SM3_09D_A11_A18_R29_3_FEEDBACK_POLICY_v1.json"
    policy = load_json(pp)
    if not isinstance(policy, dict) or policy.get("contract_version") != "SM3_STRATEGY_FEEDBACK_LOOP_POLICY_V1":
        raise RuntimeError("R29_3_POLICY_INVALID")

    def run():
        r = cycle(root, policy)
        health = {
            "contract_version": "SM3_STRATEGY_FEEDBACK_HEALTH_V1",
            "ok": True,
            "observed_at": now(),
            "feedback_status": r["feedback_status"],
            "active_feedback_evidence_count": r["active_feedback_evidence_count"],
            "expired_evidence_excluded_count": r["expired_evidence_excluded_count"],
            "strategy_status": r["current_strategy"]["status"],
            "strategy_id": r["current_strategy"]["strategy_id"],
            "selected_semantic_fingerprint": r["current_strategy"]["selected_semantic_fingerprint"],
            "delta_classification": r["delta"]["classification"],
            "semantic_direction_changed": r["delta"]["semantic_direction_changed"],
            "automatic_publication": False,
            "automatic_reply": False,
            "automatic_irreversible_strategy_change": False,
        }
        write_json(root / "state" / "social_observer" / "SM3_STRATEGY_FEEDBACK_HEALTH.json", health)
        return health

    if a.once:
        h = run()
        for k, v in h.items():
            if k not in {"contract_version", "ok", "observed_at"}:
                print("R29_3_" + k.upper() + "=" + str(v))
        print("SM3_09D_A11_A18_R29_3_STRATEGY_FEEDBACK_LOOP_v1_PASS")
        return

    if not a.daemon:
        raise RuntimeError("R29_3_MODE_REQUIRED")

    while True:
        started = time.time()
        try:
            h = run()
            print("R29_3_CYCLE_PASS|feedback=" + str(h["feedback_status"]) + "|strategy=" + str(h["strategy_status"]) + "|delta=" + str(h["delta_classification"]), flush=True)
        except Exception as e:
            write_json(root / "state" / "social_observer" / "SM3_STRATEGY_FEEDBACK_HEALTH.json", {
                "contract_version": "SM3_STRATEGY_FEEDBACK_HEALTH_V1",
                "ok": False,
                "observed_at": now(),
                "error": type(e).__name__ + ":" + str(e),
                "automatic_publication": False,
                "automatic_reply": False,
                "automatic_irreversible_strategy_change": False,
            })
            print("R29_3_CYCLE_FAIL_CLOSED=" + type(e).__name__ + ":" + str(e), file=sys.stderr, flush=True)
        time.sleep(max(1, a.interval - (time.time() - started)))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("SM3_R29_3_FAIL_CLOSED:" + type(e).__name__ + ":" + str(e), file=sys.stderr)
        raise SystemExit(1)
