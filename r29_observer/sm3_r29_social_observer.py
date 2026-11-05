#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, os, sqlite3, statistics, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("SM3_PROJECT_ROOT", "/project")).resolve()
WORKER_BASE = os.environ.get("SM3_WORKER_BASE_URL", "http://media-worker:8090").rstrip("/")
INTERVAL = int(os.environ.get("SM3_R29_INTERVAL_SECONDS", "900"))
STATE = ROOT / "state" / "social_observer"
DB = STATE / "SM3_SOCIAL_OBSERVER_STATE_V1.sqlite3"
SOCIAL_DB = ROOT / "state" / "social_learning" / "SM3_SOCIAL_LEARNING_STATE_V1.sqlite3"
R28_CONTEXT = ROOT / "state" / "adaptive_strategy" / "contexts" / "SM3_R28_LIVE_CONTEXT_CURRENT.json"
R28_STRATEGY = ROOT / "state" / "adaptive_strategy" / "strategies" / "SM3_R28_LIVE_STRATEGY_CURRENT.json"
R18_STATE = ROOT / "state" / "human_review" / "SM3_HUMAN_REVIEW_STATE_CURRENT.json"
R19_STATE = ROOT / "state" / "publication_gate" / "SM3_PUBLICATION_GATE_STATE_CURRENT.json"
POLICY_PATH = ROOT / "SM3_09D_A11_A18_R29_SOCIAL_OBSERVER_POLICY_v1.json"


def now_dt(): return dt.datetime.now(dt.timezone.utc)
def now(): return now_dt().isoformat()
def future(days): return (now_dt() + dt.timedelta(days=days)).isoformat()
def canon(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
def sha_obj(x): return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()
def sha_file(p):
    p = Path(p)
    if not p.is_file(): return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()
def load_json(p, default=None):
    p = Path(p)
    if not p.is_file(): return default
    try: return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception: return default
def write_json(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)
def fetch_internal(path):
    try:
        with urllib.request.urlopen(WORKER_BASE + path, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

def init_store():
    STATE.mkdir(parents=True, exist_ok=True)
    for d in ["snapshots", "evidence", "audience_models", "drift", "strategies"]:
        (STATE / d).mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB))
    try:
        con.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS snapshots(
          snapshot_id TEXT PRIMARY KEY, observed_at TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL UNIQUE, payload_json TEXT NOT NULL,
          real_publication_count INTEGER NOT NULL,
          real_metric_snapshot_count INTEGER NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS drift_events(
          drift_id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, network TEXT,
          horizon_hours INTEGER, metric_path TEXT NOT NULL, baseline_median REAL,
          baseline_mad REAL, latest_value REAL, relative_change REAL,
          robust_deviation REAL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidence_events(
          evidence_id TEXT PRIMARY KEY, source_type TEXT NOT NULL,
          observed_at TEXT NOT NULL, payload_json TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """)
        con.commit()
    finally:
        con.close()

def social_truth():
    out = {"publication_count": 0, "metric_snapshot_count": 0, "metric_snapshots": []}
    if not SOCIAL_DB.is_file(): return out
    con = sqlite3.connect(str(SOCIAL_DB)); con.row_factory = sqlite3.Row
    try:
        try: out["publication_count"] = int(con.execute("SELECT count(*) FROM publications WHERE synthetic=0").fetchone()[0])
        except Exception: pass
        try: out["metric_snapshot_count"] = int(con.execute("SELECT count(*) FROM metric_snapshots WHERE synthetic=0").fetchone()[0])
        except Exception: pass
        try: out["metric_snapshots"] = [dict(r) for r in con.execute("SELECT * FROM metric_snapshots WHERE synthetic=0 ORDER BY rowid DESC LIMIT 500").fetchall()]
        except Exception: pass
    finally: con.close()
    return out

def numeric_paths(x, prefix=""):
    out = {}
    if isinstance(x, dict):
        for k, v in x.items(): out.update(numeric_paths(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x)):
        out[prefix] = float(x)
    return out

def payload_metrics(row):
    raw = row.get("payload_json")
    if not isinstance(raw, str): return {}
    try: return numeric_paths(json.loads(raw))
    except Exception: return {}

def audience_model(social, policy):
    pubs, snaps = int(social["publication_count"]), int(social["metric_snapshot_count"])
    minp = int(policy["audience_model"]["minimum_real_publications_for_active_model"])
    mins = int(policy["audience_model"]["minimum_real_metric_snapshots_for_active_model"])
    status = "WAITING_FOR_REAL_PUBLICATIONS"
    if pubs > 0 or snaps > 0: status = "BOOTSTRAP_REAL_DATA"
    if pubs >= minp and snaps >= mins: status = "ACTIVE_REAL_DATA"
    groups = {}
    for row in social["metric_snapshots"]:
        key = f"{str(row.get('network') or 'UNKNOWN').upper()}|H{int(row.get('horizon_hours') or 0)}"
        for path, val in payload_metrics(row).items(): groups.setdefault(key, {}).setdefault(path, []).append(val)
    agg = {}
    for key, metrics in groups.items():
        agg[key] = {p: {"count": len(v), "median": statistics.median(v), "mean": sum(v)/len(v)} for p, v in metrics.items() if v}
    return {
      "contract_version": "SM3_AUDIENCE_RESPONSE_MODEL_V1", "generated_at": now(), "status": status,
      "real_publication_count": pubs, "real_metric_snapshot_count": snaps, "aggregates": agg,
      "synthetic_training_allowed": False, "claims": {"audience_known": status == "ACTIVE_REAL_DATA"}
    }

def drift_events(social, policy):
    min_points = int(policy["drift_detection"]["minimum_comparable_points"])
    rel_floor = float(policy["drift_detection"]["relative_change_floor"])
    dev_floor = float(policy["drift_detection"]["robust_deviation_threshold"])
    series = {}
    for row in reversed(social["metric_snapshots"]):
        net = str(row.get("network") or "UNKNOWN").upper(); h = int(row.get("horizon_hours") or 0)
        for path, val in payload_metrics(row).items(): series.setdefault((net, h, path), []).append(val)
    out = []
    for (net, h, path), vals in series.items():
        if len(vals) < min_points: continue
        latest, base = vals[-1], vals[:-1]
        if len(base) < max(3, min_points - 1): continue
        med = statistics.median(base); mad = statistics.median([abs(v-med) for v in base])
        rel = (latest-med)/(abs(med) if abs(med) > 1e-9 else 1.0)
        robust = abs(latest-med)/(mad if mad > 1e-9 else max(1.0, abs(med)*0.05))
        if abs(rel) < rel_floor or robust < dev_floor: continue
        ev = {"contract_version":"SM3_PLATFORM_AUDIENCE_DRIFT_V1","observed_at":now(),"network":net,"horizon_hours":h,"metric_path":path,"baseline_median":med,"baseline_mad":mad,"latest_value":latest,"relative_change":rel,"robust_deviation":robust,"direction":"UP" if latest>med else "DOWN","automatic_strategy_change_allowed":False}
        ev["drift_id"] = "DRIFT_" + sha_obj(ev)[:24]; out.append(ev)
    return out

def human_review():
    r = load_json(R18_STATE, {}) or {}
    return {k: r.get(k) for k in ["status","package_count","approved_candidate_count","revision_required_count","pending_count","discarded_count"]}

def worker_context():
    out = {}
    for p in ["/production/reference-corpus/summary","/production/culture-intelligence/platform-dynamics/summary","/production/culture-intelligence/platform-preference-signals"]:
        x = fetch_internal(p); out[p] = {"available": x is not None, "sha256": sha_obj(x) if x is not None else None}
    return out

def build_snapshot(policy):
    social = social_truth(); audience = audience_model(social, policy); drifts = drift_events(social, policy)
    r28c = load_json(R28_CONTEXT, {}) or {}; r28s = load_json(R28_STRATEGY, {}) or {}
    snap = {
      "contract_version":"SM3_SOCIAL_OBSERVER_SNAPSHOT_V1","observed_at":now(),
      "source_hashes":{"r18":sha_file(R18_STATE),"r19":sha_file(R19_STATE),"r28_context":sha_file(R28_CONTEXT),"r28_strategy":sha_file(R28_STRATEGY),"social_learning_db":sha_file(SOCIAL_DB)},
      "real_publication_count":social["publication_count"],"real_metric_snapshot_count":social["metric_snapshot_count"],
      "audience_model":audience,"drift_event_count":len(drifts),"drift_events":drifts,"human_review":human_review(),
      "r28":{"context_id":r28c.get("context_id"),"strategy_id":r28s.get("strategy_id"),"strategy_status":r28s.get("status"),"recommended_direction_id":(r28s.get("selection") or {}).get("recommended_direction_id")},
      "internal_worker_context":worker_context(),
      "guards":{"external_provider_calls":False,"automatic_publication":False,"automatic_reply":False,"synthetic_metrics_train_model":False,"unknown_remains_unknown":True}
    }
    snap["snapshot_id"] = "OBS_" + sha_obj(snap)[:24]; snap["payload_sha256"] = sha_obj(snap)
    return snap

def evidence_from(snapshot, policy):
    evs = []; audience = snapshot["audience_model"]
    if audience["status"] in {"BOOTSTRAP_REAL_DATA","ACTIVE_REAL_DATA"}:
        e = {"contract_version":"SM3_STRATEGY_EVIDENCE_BINDING_V1","evidence_id":"","source_type":"OWN_ACCOUNT_OBSERVATION","observed_at":snapshot["observed_at"],"valid_until":future(14),"confidence":0.55 if audience["status"]=="BOOTSTRAP_REAL_DATA" else 0.85,"claims":{"audience_model_status":audience["status"],"real_publication_count":audience["real_publication_count"],"real_metric_snapshot_count":audience["real_metric_snapshot_count"],"aggregates_sha256":sha_obj(audience["aggregates"])},"provenance":{"source_db":"state/social_learning/SM3_SOCIAL_LEARNING_STATE_V1.sqlite3","observer_snapshot_id":snapshot["snapshot_id"],"synthetic":False},"platform_id":None,"content_id":None}
        e["evidence_id"] = "EVD_" + sha_obj(e)[:24]; evs.append(e)
    h = snapshot["human_review"]
    if any(int(h.get(k) or 0) > 0 for k in ["approved_candidate_count","revision_required_count","discarded_count"]):
        e = {"contract_version":"SM3_STRATEGY_EVIDENCE_BINDING_V1","evidence_id":"","source_type":"HUMAN_PREFERENCE","observed_at":snapshot["observed_at"],"valid_until":None,"confidence":0.90,"claims":h,"provenance":{"source":"R18_HUMAN_REVIEW","observer_snapshot_id":snapshot["snapshot_id"]},"platform_id":None,"content_id":None}
        e["evidence_id"] = "EVD_" + sha_obj(e)[:24]; evs.append(e)
    for d in snapshot["drift_events"]:
        e = {"contract_version":"SM3_STRATEGY_EVIDENCE_BINDING_V1","evidence_id":"","source_type":"INFERENCE","observed_at":snapshot["observed_at"],"valid_until":future(int(policy["drift_detection"]["evidence_ttl_days"])),"confidence":min(0.80,0.45+min(0.35,d["robust_deviation"]/20.0)),"claims":{"drift_detected":True,"network":d["network"],"metric_path":d["metric_path"],"relative_change":d["relative_change"],"direction":d["direction"],"automatic_strategy_change_allowed":False},"provenance":{"observer_snapshot_id":snapshot["snapshot_id"],"drift_id":d["drift_id"],"method":"ROBUST_MEDIAN_MAD_V1"},"platform_id":d["network"],"content_id":None}
        e["evidence_id"] = "EVD_" + sha_obj(e)[:24]; evs.append(e)
    return evs

def persist(snapshot, evs):
    con = sqlite3.connect(str(DB))
    try:
        con.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?,?,?,?,?,?)", (snapshot["snapshot_id"],snapshot["observed_at"],snapshot["payload_sha256"],canon(snapshot),snapshot["real_publication_count"],snapshot["real_metric_snapshot_count"],now()))
        for d in snapshot["drift_events"]:
            con.execute("INSERT OR IGNORE INTO drift_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (d["drift_id"],d["observed_at"],d["network"],d["horizon_hours"],d["metric_path"],d["baseline_median"],d["baseline_mad"],d["latest_value"],d["relative_change"],d["robust_deviation"],canon(d),now()))
        for e in evs: con.execute("INSERT OR IGNORE INTO evidence_events VALUES(?,?,?,?,?,?)", (e["evidence_id"],e["source_type"],e["observed_at"],canon(e),sha_obj(e),now()))
        con.commit()
    finally: con.close()
    write_json(STATE/"SM3_SOCIAL_OBSERVER_CURRENT.json",snapshot)
    write_json(STATE/"snapshots"/(snapshot["snapshot_id"]+".json"),snapshot)
    write_json(STATE/"audience_models"/"SM3_AUDIENCE_RESPONSE_MODEL_CURRENT.json",snapshot["audience_model"])
    write_json(STATE/"drift"/"SM3_PLATFORM_AUDIENCE_DRIFT_CURRENT.json",{"contract_version":"SM3_PLATFORM_AUDIENCE_DRIFT_SET_V1","generated_at":snapshot["observed_at"],"event_count":len(snapshot["drift_events"]),"events":snapshot["drift_events"]})
    write_json(STATE/"evidence"/"SM3_STRATEGY_EVIDENCE_CURRENT.json",{"contract_version":"SM3_SOCIAL_OBSERVER_EVIDENCE_SET_V1","generated_at":snapshot["observed_at"],"observer_snapshot_id":snapshot["snapshot_id"],"evidence_count":len(evs),"evidence":evs})

def compile_r28(snapshot, evs):
    engine = ROOT/"SM3_09D_A11_A18_R28_ADAPTIVE_CREATIVE_STRATEGY_ENGINE_v1.py"; policy = ROOT/"SM3_09D_A11_A18_R28_ADAPTIVE_CREATIVE_STRATEGY_POLICY_v1.json"
    if not (R28_CONTEXT.is_file() and engine.is_file() and policy.is_file()): return {"status":"WAITING_FOR_R28_LIVE_CONTEXT"}
    ctx = load_json(R28_CONTEXT,{}) or {}; merged = list(ctx.get("evidence") or []); ids = {str(x.get("evidence_id")) for x in merged if isinstance(x,dict)}
    for e in evs:
        if e["evidence_id"] not in ids: merged.append(e)
    ctx["evidence"] = merged; ctx["ghost_layer"] = {"observer_snapshot_id":snapshot["snapshot_id"],"audience_model_status":snapshot["audience_model"]["status"],"drift_event_count":snapshot["drift_event_count"],"real_publication_count":snapshot["real_publication_count"],"real_metric_snapshot_count":snapshot["real_metric_snapshot_count"]}
    ctx.pop("context_sha256",None); ctx["context_sha256"] = sha_obj(ctx)
    merged_path = STATE/"SM3_R29_CONTEXT_CURRENT.json"; out = STATE/"strategies"/"SM3_R29_ADAPTIVE_STRATEGY_CURRENT.json"; write_json(merged_path,ctx)
    p = subprocess.run([sys.executable,str(engine),"compile","--context",str(merged_path),"--policy",str(policy),"--output",str(out)],capture_output=True,text=True)
    if p.returncode != 0: return {"status":"COMPILE_FAILED","detail":(p.stderr or p.stdout)[-2000:]}
    r = load_json(out,{}) or {}; return {"status":r.get("status"),"strategy_id":r.get("strategy_id"),"recommended_direction_id":(r.get("selection") or {}).get("recommended_direction_id"),"path":str(out)}

def cycle(policy):
    init_store(); snap = build_snapshot(policy); evs = evidence_from(snap,policy); persist(snap,evs); strategy = compile_r28(snap,evs)
    health = {"contract_version":"SM3_SOCIAL_OBSERVER_HEALTH_V1","ok":True,"observed_at":now(),"observer_snapshot_id":snap["snapshot_id"],"audience_model_status":snap["audience_model"]["status"],"real_publication_count":snap["real_publication_count"],"real_metric_snapshot_count":snap["real_metric_snapshot_count"],"drift_event_count":snap["drift_event_count"],"evidence_count":len(evs),"strategy":strategy,"external_provider_calls":False,"automatic_publication":False,"automatic_reply":False,"windows_powershell_polling":False}
    write_json(STATE/"SM3_SOCIAL_OBSERVER_HEALTH.json",health); return health

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--once",action="store_true"); ap.add_argument("--daemon",action="store_true"); ap.add_argument("--interval",type=int,default=INTERVAL); a = ap.parse_args()
    policy = load_json(POLICY_PATH)
    if not isinstance(policy,dict) or policy.get("contract_version") != "SM3_SOCIAL_OBSERVER_POLICY_V1": raise RuntimeError("R29_POLICY_INVALID")
    if a.once:
        h = cycle(policy)
        for k,v in [("R29_OBSERVER_SNAPSHOT_ID",h["observer_snapshot_id"]),("R29_AUDIENCE_MODEL_STATUS",h["audience_model_status"]),("R29_REAL_PUBLICATION_COUNT",h["real_publication_count"]),("R29_REAL_METRIC_SNAPSHOT_COUNT",h["real_metric_snapshot_count"]),("R29_DRIFT_EVENT_COUNT",h["drift_event_count"]),("R29_EVIDENCE_COUNT",h["evidence_count"]),("R29_STRATEGY_STATUS",(h["strategy"] or {}).get("status"))]: print(f"{k}={v}")
        print("R29_EXTERNAL_PROVIDER_CALLS=False\nR29_AUTOMATIC_PUBLICATION=False\nR29_AUTOMATIC_REPLY=False\nSM3_09D_A11_A18_R29_SOCIAL_OBSERVER_v1_PASS"); return
    if not a.daemon: raise RuntimeError("R29_MODE_REQUIRED")
    while True:
        start=time.time()
        try:
            h=cycle(policy); print(f"R29_CYCLE_PASS|snapshot={h['observer_snapshot_id']}|audience={h['audience_model_status']}|publications={h['real_publication_count']}|metrics={h['real_metric_snapshot_count']}|drift={h['drift_event_count']}",flush=True)
        except Exception as e:
            write_json(STATE/"SM3_SOCIAL_OBSERVER_HEALTH.json",{"contract_version":"SM3_SOCIAL_OBSERVER_HEALTH_V1","ok":False,"observed_at":now(),"error":type(e).__name__+":"+str(e),"external_provider_calls":False,"automatic_publication":False,"automatic_reply":False,"windows_powershell_polling":False}); print("R29_CYCLE_FAIL_CLOSED="+type(e).__name__+":"+str(e),file=sys.stderr,flush=True)
        time.sleep(max(1,a.interval-(time.time()-start)))

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print("SM3_R29_FAIL_CLOSED:"+type(e).__name__+":"+str(e),file=sys.stderr); raise SystemExit(1)
