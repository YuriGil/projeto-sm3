#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,math,os,sqlite3,statistics,sys,time
from pathlib import Path

CONTRACT="SM3_AUDIENCE_RESPONSE_MODEL_V2"
OBS_CONTRACT="SM3_AUDIENCE_RESPONSE_OBSERVATION_V1"
EVIDENCE_CONTRACT="SM3_STRATEGY_EVIDENCE_BINDING_V1"

def utcnow(): return dt.datetime.now(dt.timezone.utc)
def now(): return utcnow().isoformat()
def future(days): return (utcnow()+dt.timedelta(days=days)).isoformat()
def canon(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def sha_obj(x): return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()

def write_json(path,obj):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(tmp,p)

def load_json(path,default=None):
    p=Path(path)
    if not p.is_file(): return default
    try:return json.loads(p.read_text(encoding="utf-8-sig"))
    except:return default

def decode_payload(raw):
    if isinstance(raw,dict): return raw
    if not isinstance(raw,str): return {}
    try:
        x=json.loads(raw)
        return x if isinstance(x,dict) else {}
    except:return {}

def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)

def first_scalar(obj,names):
    for d in walk(obj):
        for n in names:
            if n in d and isinstance(d[n],(str,int,float,bool)) and not isinstance(d[n],bool):
                return d[n]
    return None

def numeric(obj,names):
    v=first_scalar(obj,names)
    if isinstance(v,(int,float)) and math.isfinite(float(v)): return float(v)
    if isinstance(v,str):
        try:
            z=float(v.replace(",","."))
            return z if math.isfinite(z) else None
        except:return None
    return None

def normalize_ratio(v):
    if v is None:return None
    v=float(v)
    if 0<=v<=1:return v
    if 1<v<=100:return v/100.0
    return None

def safe_rate(num,den):
    if num is None or den is None or den<=0:return None
    return float(num)/float(den)

def publication_lineage(payload):
    return {
      "strategy_id": first_scalar(payload,["strategy_id","adaptive_strategy_id"]),
      "direction_id": first_scalar(payload,["direction_id","creative_direction_id","recommended_direction_id"]),
      "content_id": first_scalar(payload,["content_id"]),
      "package_id": first_scalar(payload,["package_id","review_package_id"]),
      "variant_id": first_scalar(payload,["variant_id"]),
      "duration_seconds": numeric(payload,["duration_seconds","durationSeconds","duration"]),
    }

def social_rows(db):
    out={"publications":[],"metrics":[]}
    if not db.is_file():return out
    con=sqlite3.connect(str(db)); con.row_factory=sqlite3.Row
    try:
        try:
            out["publications"]=[dict(r) for r in con.execute(
              "SELECT * FROM publications WHERE synthetic=0 ORDER BY rowid ASC"
            ).fetchall()]
        except Exception:pass
        try:
            out["metrics"]=[dict(r) for r in con.execute(
              "SELECT * FROM metric_snapshots WHERE synthetic=0 ORDER BY rowid ASC"
            ).fetchall()]
        except Exception:pass
    finally:con.close()
    return out

def metric_map(payload,aliases):
    return {k:numeric(payload,v) for k,v in aliases.items()}

def observation(pub,metric,aliases):
    pp=decode_payload(pub.get("payload_json"))
    mp=decode_payload(metric.get("payload_json"))
    raw=metric_map(mp,aliases)
    lineage=publication_lineage(pp)
    if lineage["duration_seconds"] is None:
        lineage["duration_seconds"]=raw.get("duration")

    reach=raw.get("reach")
    views=raw.get("views")
    likes=raw.get("likes")
    comments=raw.get("comments")
    shares=raw.get("shares")
    saved=raw.get("saved")
    reposts=raw.get("reposts")
    avg_watch=raw.get("average_watch_time")
    duration=lineage.get("duration_seconds")

    explicit_ret=normalize_ratio(raw.get("retention"))
    derived_ret=safe_rate(avg_watch,duration)
    retention=explicit_ret if explicit_ret is not None else derived_ret
    retention_source="EXPLICIT" if explicit_ret is not None else ("DERIVED_AVG_WATCH_OVER_DURATION" if derived_ret is not None else "UNKNOWN")

    dimensions={
      "ATTENTION":{
        "views":views,
        "reach":reach,
        "views_per_reach":safe_rate(views,reach),
        "three_second_view_rate":normalize_ratio(raw.get("view_rate_3s")),
      },
      "RETENTION":{
        "average_watch_time_seconds":avg_watch,
        "total_watch_time_seconds":raw.get("total_watch_time"),
        "retention_ratio":retention,
        "retention_source":retention_source,
        "full_watch_rate":normalize_ratio(raw.get("full_watch_rate")),
        "duration_seconds":duration,
      },
      "AMPLIFICATION":{
        "shares":shares,
        "reposts":reposts,
        "share_rate_per_reach":safe_rate(shares,reach),
        "repost_rate_per_reach":safe_rate(reposts,reach),
        "amplification_rate_per_reach":safe_rate(
          (shares or 0)+(reposts or 0) if shares is not None or reposts is not None else None,
          reach
        ),
      },
      "CONVERSATION":{
        "comments":comments,
        "comment_rate_per_reach":safe_rate(comments,reach),
      },
      "INTENT":{
        "saves":saved,
        "save_rate_per_reach":safe_rate(saved,reach),
      },
      "AFFINITY":{
        "likes":likes,
        "like_rate_per_reach":safe_rate(likes,reach),
      },
      "DISCOVERY_MIX":{
        "for_you":normalize_ratio(raw.get("for_you")),
        "following":normalize_ratio(raw.get("following")),
        "hashtag":normalize_ratio(raw.get("hashtag")),
        "sound":normalize_ratio(raw.get("sound")),
        "profile":normalize_ratio(raw.get("profile")),
        "search":normalize_ratio(raw.get("search")),
      }
    }

    known=sum(
      1 for d in dimensions.values() for v in d.values()
      if v is not None and not isinstance(v,str)
    )
    lineage_complete=bool(lineage.get("strategy_id") and lineage.get("direction_id"))

    base={
      "contract_version":OBS_CONTRACT,
      "publication_id":str(pub.get("publication_id") or ""),
      "snapshot_id":str(metric.get("snapshot_id") or ""),
      "network":str(metric.get("network") or pub.get("network") or "UNKNOWN").upper(),
      "horizon_hours":int(metric.get("horizon_hours") or 0),
      "captured_at":metric.get("captured_at"),
      "published_at":pub.get("published_at"),
      "metric_source":metric.get("metric_source"),
      "synthetic":False,
      "lineage":lineage,
      "strategy_lineage_complete":lineage_complete,
      "raw_metric_payload_sha256":metric.get("payload_sha256") or sha_obj(mp),
      "raw_metrics":raw,
      "dimensions":dimensions,
      "known_numeric_signal_count":known,
    }
    base["observation_id"]="ARO_"+sha_obj(base)[:24]
    return base

def aggregate(observations):
    buckets={}
    for o in observations:
        key=(o["network"],o["horizon_hours"])
        b=buckets.setdefault(key,[])
        b.append(o)

    out={}
    for (network,horizon),obs in buckets.items():
        k=f"{network}|H{horizon}"
        out[k]={
          "network":network,
          "horizon_hours":horizon,
          "observation_count":len(obs),
          "strategy_lineage_complete_count":sum(1 for x in obs if x["strategy_lineage_complete"]),
          "dimensions":{}
        }
        for dim in ["ATTENTION","RETENTION","AMPLIFICATION","CONVERSATION","INTENT","AFFINITY","DISCOVERY_MIX"]:
            paths={}
            for x in obs:
                for metric,val in x["dimensions"][dim].items():
                    if isinstance(val,(int,float)) and not isinstance(val,bool) and math.isfinite(float(val)):
                        paths.setdefault(metric,[]).append(float(val))
            out[k]["dimensions"][dim]={}
            for metric,vals in paths.items():
                out[k]["dimensions"][dim][metric]={
                  "count":len(vals),
                  "median":statistics.median(vals),
                  "mean":sum(vals)/len(vals),
                  "min":min(vals),
                  "max":max(vals),
                }
    return out

def build(root,policy):
    db=root/"state"/"social_learning"/"SM3_SOCIAL_LEARNING_STATE_V1.sqlite3"
    rows=social_rows(db)
    pubs={str(x.get("publication_id")):x for x in rows["publications"] if x.get("publication_id")}
    observations=[]
    unmatched=0
    for m in rows["metrics"]:
        pid=str(m.get("publication_id") or "")
        p=pubs.get(pid)
        if not p:
            unmatched+=1
            continue
        observations.append(observation(p,m,policy["metric_aliases"]))

    pcount=len(rows["publications"]); mcount=len(rows["metrics"])
    if pcount==0:
        status="WAITING_FOR_REAL_PUBLICATIONS"
    elif pcount < int(policy["activation"]["active_min_real_publications"]) or mcount < int(policy["activation"]["active_min_real_metric_snapshots"]):
        status="BOOTSTRAP_REAL_DATA"
    else:
        status="ACTIVE_REAL_DATA"

    model={
      "contract_version":CONTRACT,
      "generated_at":now(),
      "status":status,
      "real_publication_count":pcount,
      "real_metric_snapshot_count":mcount,
      "matched_observation_count":len(observations),
      "unmatched_metric_snapshot_count":unmatched,
      "strategy_lineage_complete_observation_count":sum(1 for x in observations if x["strategy_lineage_complete"]),
      "semantic_dimensions":policy["semantic_dimensions"],
      "aggregates":aggregate(observations),
      "guards":{
        "synthetic_metrics_used":False,
        "missing_metric_imputed":False,
        "causal_claims_allowed":False,
        "strategy_effect_claims_require_lineage":True,
        "automatic_publication":False,
        "automatic_reply":False,
      }
    }
    model["model_sha256"]=sha_obj(model)
    return model,observations

def evidence(model):
    if model["matched_observation_count"]<=0:return None
    conf=0.55 if model["status"]=="BOOTSTRAP_REAL_DATA" else 0.82
    e={
      "contract_version":EVIDENCE_CONTRACT,
      "evidence_id":"",
      "source_type":"OWN_ACCOUNT_OBSERVATION",
      "observed_at":now(),
      "valid_until":future(14),
      "confidence":conf,
      "claims":{
        "audience_response_model_status":model["status"],
        "real_publication_count":model["real_publication_count"],
        "real_metric_snapshot_count":model["real_metric_snapshot_count"],
        "matched_observation_count":model["matched_observation_count"],
        "strategy_lineage_complete_observation_count":model["strategy_lineage_complete_observation_count"],
        "model_sha256":model["model_sha256"],
      },
      "provenance":{
        "engine":"SM3_R29_1_AUDIENCE_RESPONSE_MODEL_V1",
        "source_db":"state/social_learning/SM3_SOCIAL_LEARNING_STATE_V1.sqlite3",
        "synthetic":False
      },
      "platform_id":None,
      "content_id":None
    }
    e["evidence_id"]="EVD_"+sha_obj(e)[:24]
    return e

def persist(root,model,observations):
    state=root/"state"/"social_observer"/"audience_response_v2"
    state.mkdir(parents=True,exist_ok=True)
    write_json(state/"SM3_AUDIENCE_RESPONSE_MODEL_V2_CURRENT.json",model)
    write_json(state/"SM3_AUDIENCE_RESPONSE_OBSERVATIONS_CURRENT.json",{
      "contract_version":"SM3_AUDIENCE_RESPONSE_OBSERVATION_SET_V1",
      "generated_at":now(),
      "count":len(observations),
      "observations":observations[-500:]
    })
    ev=evidence(model)
    write_json(state/"SM3_AUDIENCE_RESPONSE_EVIDENCE_CURRENT.json",{
      "contract_version":"SM3_AUDIENCE_RESPONSE_EVIDENCE_SET_V1",
      "generated_at":now(),
      "evidence_count":1 if ev else 0,
      "evidence":[ev] if ev else []
    })
    hist=state/"history"; hist.mkdir(exist_ok=True)
    write_json(hist/(model["model_sha256"]+".json"),model)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default=os.environ.get("SM3_PROJECT_ROOT","/project"))
    ap.add_argument("--policy",default=None)
    ap.add_argument("--once",action="store_true")
    ap.add_argument("--daemon",action="store_true")
    ap.add_argument("--interval",type=int,default=int(os.environ.get("SM3_R29_1_INTERVAL_SECONDS","900")))
    a=ap.parse_args()
    root=Path(a.project_root).resolve()
    policy_path=Path(a.policy) if a.policy else root/"SM3_09D_A11_A18_R29_1_AUDIENCE_RESPONSE_POLICY_v1.json"
    policy=load_json(policy_path)
    if not isinstance(policy,dict) or policy.get("contract_version")!="SM3_AUDIENCE_RESPONSE_POLICY_V1":
        raise RuntimeError("R29_1_POLICY_INVALID")

    def cycle():
        model,obs=build(root,policy)
        persist(root,model,obs)
        health={
          "contract_version":"SM3_AUDIENCE_RESPONSE_HEALTH_V1",
          "ok":True,
          "observed_at":now(),
          "status":model["status"],
          "real_publication_count":model["real_publication_count"],
          "real_metric_snapshot_count":model["real_metric_snapshot_count"],
          "matched_observation_count":model["matched_observation_count"],
          "strategy_lineage_complete_observation_count":model["strategy_lineage_complete_observation_count"],
          "model_sha256":model["model_sha256"],
          "automatic_publication":False,
          "automatic_reply":False,
          "external_provider_calls":False,
        }
        write_json(root/"state"/"social_observer"/"SM3_AUDIENCE_RESPONSE_HEALTH.json",health)
        return health

    if a.once:
        h=cycle()
        for k in ["status","real_publication_count","real_metric_snapshot_count","matched_observation_count","strategy_lineage_complete_observation_count","model_sha256"]:
            print("R29_1_"+k.upper()+"="+str(h[k]))
        print("R29_1_EXTERNAL_PROVIDER_CALLS=False")
        print("R29_1_AUTOMATIC_PUBLICATION=False")
        print("R29_1_AUTOMATIC_REPLY=False")
        print("SM3_09D_A11_A18_R29_1_AUDIENCE_RESPONSE_v1_PASS")
        return

    if not a.daemon: raise RuntimeError("R29_1_MODE_REQUIRED")
    while True:
        started=time.time()
        try:
            h=cycle()
            print("R29_1_CYCLE_PASS|status="+str(h["status"])+"|pubs="+str(h["real_publication_count"])+"|metrics="+str(h["real_metric_snapshot_count"])+"|matched="+str(h["matched_observation_count"]),flush=True)
        except Exception as e:
            write_json(root/"state"/"social_observer"/"SM3_AUDIENCE_RESPONSE_HEALTH.json",{
              "contract_version":"SM3_AUDIENCE_RESPONSE_HEALTH_V1","ok":False,"observed_at":now(),
              "error":type(e).__name__+":"+str(e),"automatic_publication":False,"automatic_reply":False,"external_provider_calls":False
            })
            print("R29_1_CYCLE_FAIL_CLOSED="+type(e).__name__+":"+str(e),file=sys.stderr,flush=True)
        time.sleep(max(1,a.interval-(time.time()-started)))

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("SM3_R29_1_FAIL_CLOSED:"+type(e).__name__+":"+str(e),file=sys.stderr)
        raise SystemExit(1)
