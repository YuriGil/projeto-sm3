#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CONTRACT="SM3_R21_INTERNAL_METRIC_LOOP_ORCHESTRATOR_V1"
ROOT=Path(os.environ.get("SM3_PROJECT_ROOT","/project")).resolve()
PORT=int(os.environ.get("SM3_R21_PORT","8091"))
LOCK=threading.Lock()

R20_ENGINE="SM3_09D_A11_A18_R20_METRIC_HORIZON_ENGINE_v1.py"
R20_POLICY="SM3_09D_A11_A18_R20_METRIC_HORIZON_POLICY_v1.json"
R7_DISPATCHER="SM3_09D_A11_A18_R7_INBOX_DISPATCHER.py"
R6_BRIDGE="SM3_09D_A11_A18_R6_AUTHORIZED_ANALYTICS_BRIDGE.py"

def now():
    return datetime.now(timezone.utc).isoformat()

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def canon(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def sha_obj(obj):
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()

def write_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def run_cmd(args, timeout=300, allowed=(0,)):
    p=subprocess.run(args,cwd=str(ROOT),text=True,capture_output=True,timeout=timeout)
    if p.returncode not in allowed:
        raise RuntimeError(
            "R21_COMMAND_FAILED:"
            +str(p.returncode)+":"
            +" ".join(str(x) for x in args)+":"
            +(p.stderr or p.stdout)[-4000:]
        )
    return {"exit_code":p.returncode,"stdout":p.stdout or "","stderr":p.stderr or ""}

def required_file(name):
    p=ROOT/name
    if not p.is_file():
        raise RuntimeError("R21_REQUIRED_FILE_MISSING:"+str(p))
    return p

def run_r20():
    engine=required_file(R20_ENGINE)
    policy=required_file(R20_POLICY)
    out=ROOT/"state"/"metric_horizons"/"SM3_METRIC_HORIZON_STATE_CURRENT.json"
    result=run_cmd([
        sys.executable,str(engine),
        "--root",str(ROOT),
        "--policy",str(policy),
        "--output",str(out)
    ])
    state=load(out)
    return result,state

def dispatch_r7():
    dispatcher=required_file(R7_DISPATCHER)
    # R7 returns 2 when any item dead-letters. That is an intentional classified result,
    # not a reason to loop indefinitely.
    result=run_cmd([
        sys.executable,str(dispatcher),
        "--root",str(ROOT),
        "--action","Dispatch",
        "--max-items","10"
    ], allowed=(0,2))
    return result

def build_learner_input():
    bridge=required_file(R6_BRIDGE)
    out=ROOT/"state"/"learner_triggers"/"SM3_REAL_LEARNER_INPUT_CURRENT.json"
    result=run_cmd([
        sys.executable,str(bridge),
        "--root",str(ROOT),
        "--action","BuildLearnerInput",
        "--output",str(out)
    ])
    payload=load(out)
    pubs=payload.get("publications") or []
    snaps=payload.get("metric_snapshots") or []
    return result,out,payload,len(pubs),len(snaps)

def emit_learner_trigger(r20_state, learner_path, learner_payload, pub_count, snap_count):
    base=ROOT/"state"/"learner_triggers"
    base.mkdir(parents=True,exist_ok=True)
    identity={
        "r20_state_sha256":r20_state.get("state_sha256"),
        "publication_count":pub_count,
        "snapshot_count":snap_count,
        "learner_payload_sha256":sha_obj(learner_payload)
    }
    tid="LTR_"+sha_obj(identity)[:28]
    trigger={
        "contract_version":"SM3_REAL_LEARNER_TRIGGER_REQUEST_V1",
        "trigger_id":tid,
        "created_at":now(),
        "source":"SM3_R21_INTERNAL_METRIC_LOOP",
        "r20_state_sha256":r20_state.get("state_sha256"),
        "learner_input_path":str(learner_path),
        "learner_input_sha256":sha_obj(learner_payload),
        "real_publication_count":pub_count,
        "real_snapshot_count":snap_count,
        "synthetic_evidence_allowed":False,
        "target":"A11_A17_PLATFORM_LEARNER",
        "automatic_prior_promotion":False,
        "human_foundation_override_forbidden":True,
        "status":"READY_FOR_CANONICAL_LEARNER_CONSUMER"
    }
    trigger["trigger_sha256"]=sha_obj(trigger)
    current=base/"SM3_REAL_LEARNER_TRIGGER_CURRENT.json"
    write_json(current,trigger)
    events=base/"events";events.mkdir(parents=True,exist_ok=True)
    ep=events/(tid+".json")
    if not ep.exists():
        write_json(ep,trigger)
    return trigger

def tick():
    if not LOCK.acquire(blocking=False):
        return {
            "ok":True,
            "contract_version":CONTRACT,
            "route":"BUSY_SKIP",
            "audit_code":"R21_CONCURRENCY_LOCK_SKIP_PASS",
            "at":now()
        }
    try:
        started=now()
        r20_before_result,r20_before=run_r20()
        r7=dispatch_r7()
        r20_after_result,r20_after=run_r20()

        pending=int(r20_after.get("pending_collection_request_count") or 0)
        learner_allowed=bool(r20_after.get("learner_required_horizon_run_allowed") is True)
        trigger=None
        learner_counts={"publications":0,"snapshots":0}

        if learner_allowed:
            _,lp,payload,pc,sc=build_learner_input()
            trigger=emit_learner_trigger(r20_after,lp,payload,pc,sc)
            learner_counts={"publications":pc,"snapshots":sc}

        if trigger is not None:
            route="LEARNER_INPUT_READY"
        elif pending>0:
            route="COLLECTION_REQUIRED"
        elif "A11_A18_R7_DISPATCHER=WORK" in r7["stdout"]:
            route="ANALYTICS_DISPATCHED"
        else:
            route="IDLE"

        result={
            "ok":True,
            "contract_version":CONTRACT,
            "route":route,
            "started_at":started,
            "finished_at":now(),
            "r20_before_status":r20_before.get("status"),
            "r20_after_status":r20_after.get("status"),
            "pending_collection_request_count":pending,
            "learner_required_horizon_run_allowed":learner_allowed,
            "learner_counts":learner_counts,
            "learner_trigger":trigger,
            "r7_exit_code":r7["exit_code"],
            "r7_committed_marker":"A11_A18_R7_COMMITTED=" in r7["stdout"],
            "r7_dead_letter_marker":"A11_A18_R7_DEAD_LETTER=" in r7["stdout"],
            "provider_network_collection_performed_by_r21":False,
            "windows_powershell_polling":False
        }
        result["result_sha256"]=sha_obj(result)
        state=ROOT/"state"/"r21"/"SM3_R21_INTERNAL_LOOP_LAST_TICK.json"
        write_json(state,result)
        return result
    finally:
        LOCK.release()

class Handler(BaseHTTPRequestHandler):
    server_version="SM3-R21/1.0"
    def log_message(self,fmt,*args):
        sys.stdout.write("[%s] %s\n"%(now(),fmt%args))
        sys.stdout.flush()

    def send_json(self,status,obj):
        data=json.dumps(obj,ensure_ascii=False,separators=(",",":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path=="/health":
            missing=[n for n in (R20_ENGINE,R20_POLICY,R7_DISPATCHER,R6_BRIDGE) if not (ROOT/n).is_file()]
            self.send_json(200,{
                "ok":len(missing)==0,
                "contract_version":CONTRACT,
                "project_root":str(ROOT),
                "missing_dependencies":missing,
                "windows_powershell_polling":False
            })
            return
        if self.path=="/status":
            p=ROOT/"state"/"r21"/"SM3_R21_INTERNAL_LOOP_LAST_TICK.json"
            self.send_json(200,load(p) if p.is_file() else {
                "ok":True,"contract_version":CONTRACT,"route":"NEVER_RUN"
            })
            return
        self.send_json(404,{"ok":False,"error":"NOT_FOUND"})

    def do_POST(self):
        if self.path!="/tick":
            self.send_json(404,{"ok":False,"error":"NOT_FOUND"})
            return
        try:
            result=tick()
            self.send_json(200,result)
        except Exception as e:
            err={
                "ok":False,
                "contract_version":CONTRACT,
                "error":type(e).__name__+":"+str(e),
                "traceback":traceback.format_exc()[-6000:],
                "failed_at":now(),
                "provider_network_collection_performed_by_r21":False,
                "windows_powershell_polling":False
            }
            try:
                write_json(ROOT/"state"/"r21"/"SM3_R21_INTERNAL_LOOP_LAST_ERROR.json",err)
            except Exception:
                pass
            self.send_json(500,err)

def main():
    server=ThreadingHTTPServer(("0.0.0.0",PORT),Handler)
    print("SM3_R21_ORCHESTRATOR_READY port="+str(PORT)+" root="+str(ROOT),flush=True)
    server.serve_forever()

if __name__=="__main__":
    main()
