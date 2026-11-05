#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sqlite3
import statistics
import sys
import time
from pathlib import Path

DRIFT_SET = "SM3_PLATFORM_AUDIENCE_DRIFT_SET_V2"
DRIFT_EVENT = "SM3_PLATFORM_AUDIENCE_DRIFT_EVENT_V1"
PLATFORM_CHANGE = "SM3_PLATFORM_CONTEXT_CHANGE_V1"
EVIDENCE = "SM3_STRATEGY_EVIDENCE_BINDING_V1"

def utcnow(): return dt.datetime.now(dt.timezone.utc)
def now(): return utcnow().isoformat()
def future(days): return (utcnow() + dt.timedelta(days=days)).isoformat()
def canon(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
def sha_obj(x): return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()

def load_json(path, default=None):
    p = Path(path)
    if not p.is_file(): return default
    try: return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception: return default

def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)

def finite_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))

def observation_series(observations):
    series = {}
    for o in observations:
        network = str(o.get("network") or "UNKNOWN").upper()
        horizon = int(o.get("horizon_hours") or 0)
        sid = str(o.get("snapshot_id") or "")
        captured = str(o.get("captured_at") or "")
        lineage = o.get("lineage") or {}
        direction_id = lineage.get("direction_id")
        dims = o.get("dimensions") or {}

        for dim, values in dims.items():
            if not isinstance(values, dict): continue
            for metric, val in values.items():
                if not finite_num(val): continue
                key = (network, horizon, str(dim), str(metric))
                series.setdefault(key, []).append({
                    "value": float(val),
                    "snapshot_id": sid,
                    "captured_at": captured,
                    "direction_id": direction_id,
                    "observation_id": o.get("observation_id"),
                })
    return series

def median_abs_deviation(vals, med=None):
    if not vals: return 0.0
    if med is None: med = statistics.median(vals)
    return statistics.median([abs(x-med) for x in vals])

def detect_series(key, points, policy):
    min_points = int(policy["activation"]["minimum_points_per_metric_series"])
    min_base = int(policy["activation"]["minimum_baseline_points"])
    recent_n = int(policy["detection"]["recent_window_points"])
    base_max = int(policy["detection"]["baseline_window_max_points"])
    rel_floor = float(policy["detection"]["relative_change_floor"])
    warn_thr = float(policy["detection"]["warning_robust_deviation_threshold"])
    conf_thr = float(policy["detection"]["robust_deviation_threshold"])
    confirm_distinct = int(policy["detection"]["confirmation_requires_distinct_snapshot_ids"])

    # Distinct snapshot ids only; repeated daemon cycles do not manufacture evidence.
    dedup = []
    seen = set()
    for p in points:
        sid = p["snapshot_id"]
        identity = sid or (p["captured_at"], p["observation_id"])
        if identity in seen: continue
        seen.add(identity)
        dedup.append(p)

    if len(dedup) < min_points:
        return None

    recent = dedup[-recent_n:]
    baseline = dedup[:-recent_n]
    if len(baseline) < min_base:
        return None
    baseline = baseline[-base_max:]

    bvals = [x["value"] for x in baseline]
    rvals = [x["value"] for x in recent]
    bmed = statistics.median(bvals)
    rmed = statistics.median(rvals)
    mad = median_abs_deviation(bvals, bmed)
    denom = abs(bmed) if abs(bmed) > 1e-9 else 1.0
    rel = (rmed - bmed) / denom
    robust = abs(rmed - bmed) / (mad if mad > 1e-9 else max(1.0, abs(bmed)*0.05))

    if abs(rel) < rel_floor or robust < warn_thr:
        return None

    distinct_recent = len({x["snapshot_id"] for x in recent if x["snapshot_id"]})
    severity = "WARNING"
    status = "CANDIDATE"
    if robust >= conf_thr and distinct_recent >= confirm_distinct:
        severity = "CONFIRMED"
        status = "CONFIRMED_DRIFT"

    network, horizon, dim, metric = key
    event = {
        "contract_version": DRIFT_EVENT,
        "event_id": "",
        "observed_at": now(),
        "status": status,
        "severity": severity,
        "network": network,
        "horizon_hours": horizon,
        "semantic_dimension": dim,
        "metric": metric,
        "baseline": {
            "count": len(bvals),
            "median": bmed,
            "mad": mad,
        },
        "recent": {
            "count": len(rvals),
            "median": rmed,
            "distinct_snapshot_count": distinct_recent,
            "snapshot_ids": [x["snapshot_id"] for x in recent],
        },
        "relative_change": rel,
        "robust_deviation": robust,
        "direction": "UP" if rmed > bmed else "DOWN",
        "interpretation_guard": {
            "causal_claim": False,
            "automatic_strategy_change_allowed": False,
            "metric_definition_change_ruled_out": False
        }
    }
    event["event_id"] = "DVT_" + sha_obj(event)[:24]
    return event

def observer_platform_context_changes(root):
    snap_dir = root / "state" / "social_observer" / "snapshots"
    if not snap_dir.is_dir():
        return []

    rows = []
    for p in sorted(snap_dir.glob("OBS_*.json"), key=lambda x: x.stat().st_mtime)[-50:]:
        x = load_json(p, {}) or {}
        rows.append({
            "snapshot_id": x.get("snapshot_id"),
            "observed_at": x.get("observed_at"),
            "internal": x.get("internal_worker_context") or {}
        })

    changes = []
    for prev, cur in zip(rows, rows[1:]):
        pctx, cctx = prev["internal"], cur["internal"]
        paths = sorted(set(pctx) | set(cctx))
        for path in paths:
            a = pctx.get(path) or {}
            b = cctx.get(path) or {}
            if a.get("sha256") and b.get("sha256") and a.get("sha256") != b.get("sha256"):
                body = {
                    "contract_version": PLATFORM_CHANGE,
                    "change_id": "",
                    "observed_at": cur["observed_at"],
                    "source_path": path,
                    "previous_snapshot_id": prev["snapshot_id"],
                    "current_snapshot_id": cur["snapshot_id"],
                    "previous_sha256": a.get("sha256"),
                    "current_sha256": b.get("sha256"),
                    "classification": "PLATFORM_OR_CULTURE_CONTEXT_CHANGED",
                    "audience_drift_claimed": False,
                    "automatic_strategy_change_allowed": False
                }
                body["change_id"] = "PCC_" + sha_obj(body)[:24]
                changes.append(body)

    # de-dup by semantic transition
    out, seen = [], set()
    for x in changes:
        k = (x["source_path"], x["previous_sha256"], x["current_sha256"])
        if k in seen: continue
        seen.add(k); out.append(x)
    return out[-50:]

def build(root, policy):
    obs_path = root / "state" / "social_observer" / "audience_response_v2" / "SM3_AUDIENCE_RESPONSE_OBSERVATIONS_CURRENT.json"
    model_path = root / "state" / "social_observer" / "audience_response_v2" / "SM3_AUDIENCE_RESPONSE_MODEL_V2_CURRENT.json"
    obs_set = load_json(obs_path, {}) or {}
    model = load_json(model_path, {}) or {}
    observations = list(obs_set.get("observations") or [])

    pcount = int(model.get("real_publication_count") or 0)
    mcount = int(model.get("real_metric_snapshot_count") or 0)
    active = (
        pcount >= int(policy["activation"]["minimum_real_publications"]) and
        mcount >= int(policy["activation"]["minimum_real_metric_snapshots"])
    )

    events = []
    if active:
        for key, pts in observation_series(observations).items():
            e = detect_series(key, pts, policy)
            if e: events.append(e)

    context_changes = observer_platform_context_changes(root)

    if pcount == 0:
        status = "WAITING_FOR_REAL_PUBLICATIONS"
    elif not active:
        status = "BASELINE_ACCUMULATING"
    else:
        status = "ACTIVE"

    result = {
        "contract_version": DRIFT_SET,
        "generated_at": now(),
        "status": status,
        "real_publication_count": pcount,
        "real_metric_snapshot_count": mcount,
        "audience_drift_event_count": len(events),
        "confirmed_audience_drift_count": sum(1 for x in events if x["status"]=="CONFIRMED_DRIFT"),
        "candidate_audience_drift_count": sum(1 for x in events if x["status"]=="CANDIDATE"),
        "platform_context_change_count": len(context_changes),
        "audience_drift_events": events,
        "platform_context_changes": context_changes,
        "guards": {
            "real_data_only": True,
            "synthetic_used": False,
            "platform_context_change_treated_as_audience_drift": False,
            "causal_claims_allowed": False,
            "automatic_strategy_change": False,
            "automatic_publication": False,
            "automatic_reply": False
        }
    }
    result["state_sha256"] = sha_obj(result)
    return result

def evidence(result, policy):
    evs = []
    ttl = int(policy["detection"]["evidence_ttl_days"])

    for d in result["audience_drift_events"]:
        if d["status"] != "CONFIRMED_DRIFT":
            continue
        e = {
            "contract_version": EVIDENCE,
            "evidence_id": "",
            "source_type": "OWN_ACCOUNT_OBSERVATION",
            "observed_at": result["generated_at"],
            "valid_until": future(ttl),
            "confidence": min(0.90, 0.60 + min(0.30, d["robust_deviation"]/20.0)),
            "claims": {
                "confirmed_audience_drift": True,
                "network": d["network"],
                "horizon_hours": d["horizon_hours"],
                "semantic_dimension": d["semantic_dimension"],
                "metric": d["metric"],
                "direction": d["direction"],
                "relative_change": d["relative_change"],
                "automatic_strategy_change_allowed": False
            },
            "provenance": {
                "engine": "SM3_R29_2_DRIFT_DETECTOR_V1",
                "drift_event_id": d["event_id"],
                "method": "ROBUST_MEDIAN_MAD_RECENT_VS_BASELINE_V1",
                "synthetic": False
            },
            "platform_id": d["network"],
            "content_id": None
        }
        e["evidence_id"] = "EVD_" + sha_obj(e)[:24]
        evs.append(e)

    for c in result["platform_context_changes"]:
        e = {
            "contract_version": EVIDENCE,
            "evidence_id": "",
            "source_type": "INFERENCE",
            "observed_at": result["generated_at"],
            "valid_until": future(7),
            "confidence": 0.60,
            "claims": {
                "platform_or_culture_context_changed": True,
                "source_path": c["source_path"],
                "audience_drift_claimed": False,
                "refresh_platform_model_recommended": True,
                "automatic_strategy_change_allowed": False
            },
            "provenance": {
                "engine": "SM3_R29_2_DRIFT_DETECTOR_V1",
                "platform_change_id": c["change_id"]
            },
            "platform_id": None,
            "content_id": None
        }
        e["evidence_id"] = "EVD_" + sha_obj(e)[:24]
        evs.append(e)

    return evs

def persist(root, result, evs):
    state = root / "state" / "social_observer" / "drift_v2"
    state.mkdir(parents=True, exist_ok=True)
    write_json(state / "SM3_PLATFORM_AUDIENCE_DRIFT_V2_CURRENT.json", result)
    write_json(state / "SM3_PLATFORM_AUDIENCE_DRIFT_EVIDENCE_CURRENT.json", {
        "contract_version": "SM3_PLATFORM_AUDIENCE_DRIFT_EVIDENCE_SET_V1",
        "generated_at": result["generated_at"],
        "evidence_count": len(evs),
        "evidence": evs
    })
    hist = state / "history"; hist.mkdir(exist_ok=True)
    write_json(hist / (result["state_sha256"] + ".json"), result)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=os.environ.get("SM3_PROJECT_ROOT","/project"))
    ap.add_argument("--policy", default=None)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--daemon", action="store_true")
    ap.add_argument("--interval", type=int, default=int(os.environ.get("SM3_R29_2_INTERVAL_SECONDS","900")))
    a = ap.parse_args()

    root = Path(a.project_root).resolve()
    policy_path = Path(a.policy) if a.policy else root / "SM3_09D_A11_A18_R29_2_DRIFT_POLICY_v1.json"
    policy = load_json(policy_path)
    if not isinstance(policy, dict) or policy.get("contract_version") != "SM3_PLATFORM_AUDIENCE_DRIFT_POLICY_V1":
        raise RuntimeError("R29_2_POLICY_INVALID")

    def cycle():
        result = build(root, policy)
        evs = evidence(result, policy)
        persist(root, result, evs)
        health = {
            "contract_version": "SM3_PLATFORM_AUDIENCE_DRIFT_HEALTH_V1",
            "ok": True,
            "observed_at": now(),
            "status": result["status"],
            "real_publication_count": result["real_publication_count"],
            "real_metric_snapshot_count": result["real_metric_snapshot_count"],
            "audience_drift_event_count": result["audience_drift_event_count"],
            "confirmed_audience_drift_count": result["confirmed_audience_drift_count"],
            "platform_context_change_count": result["platform_context_change_count"],
            "evidence_count": len(evs),
            "state_sha256": result["state_sha256"],
            "automatic_strategy_change": False,
            "automatic_publication": False,
            "automatic_reply": False
        }
        write_json(root / "state" / "social_observer" / "SM3_PLATFORM_AUDIENCE_DRIFT_HEALTH.json", health)
        return health

    if a.once:
        h = cycle()
        for k,v in h.items():
            if k not in {"contract_version","ok","observed_at"}:
                print("R29_2_"+k.upper()+"="+str(v))
        print("SM3_09D_A11_A18_R29_2_DRIFT_DETECTOR_v1_PASS")
        return

    if not a.daemon:
        raise RuntimeError("R29_2_MODE_REQUIRED")

    while True:
        started=time.time()
        try:
            h=cycle()
            print("R29_2_CYCLE_PASS|status="+str(h["status"])+"|confirmed="+str(h["confirmed_audience_drift_count"])+"|platform_changes="+str(h["platform_context_change_count"]),flush=True)
        except Exception as e:
            write_json(root / "state" / "social_observer" / "SM3_PLATFORM_AUDIENCE_DRIFT_HEALTH.json", {
                "contract_version":"SM3_PLATFORM_AUDIENCE_DRIFT_HEALTH_V1",
                "ok":False,"observed_at":now(),"error":type(e).__name__+":"+str(e),
                "automatic_strategy_change":False,"automatic_publication":False,"automatic_reply":False
            })
            print("R29_2_CYCLE_FAIL_CLOSED="+type(e).__name__+":"+str(e),file=sys.stderr,flush=True)
        time.sleep(max(1,a.interval-(time.time()-started)))

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("SM3_R29_2_FAIL_CLOSED:"+type(e).__name__+":"+str(e),file=sys.stderr)
        raise SystemExit(1)
