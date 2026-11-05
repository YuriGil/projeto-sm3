#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,subprocess,sys,threading,traceback
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

ROOT=Path(os.environ.get("SM3_PROJECT_ROOT","/project")).resolve()
PORT=int(os.environ.get("SM3_R25_PORT","8092"))
LOCK=threading.Lock()
REQUEST_CONTRACT="SM3_R25_PROVIDER_RELAY_REQUEST_V1"
RESPONSE_CONTRACT="SM3_METRICOOL_AUTHORIZED_RESPONSE_V1"
R22_ENGINE="SM3_09D_A11_A18_R22_AUTHORIZED_ANALYTICS_COLLECTOR_v1.py"
R22_REGISTRY="SM3_09D_A11_A18_R22_METRICOOL_FIELD_REGISTRY_v1.json"
R7_DISPATCHER="SM3_09D_A11_A18_R7_INBOX_DISPATCHER.py"

def now(): return datetime.now(timezone.utc).isoformat()
def canon(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def sha_obj(x): return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def write_json(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(t,p)
def required(name):
    p=ROOT/name
    if not p.is_file(): raise RuntimeError("R25_REQUIRED_FILE_MISSING:"+str(p))
    return p
def run_cmd(args,allowed=(0,),timeout=240):
    p=subprocess.run(args,cwd=str(ROOT),capture_output=True,text=True,timeout=timeout)
    if p.returncode not in allowed:
        raise RuntimeError("R25_COMMAND_FAILED:"+str(p.returncode)+":"+(" ".join(map(str,args)))+":"+(p.stderr or p.stdout)[-5000:])
    return p

def validate_request(req):
    if not isinstance(req,dict) or req.get("contract_version")!=REQUEST_CONTRACT:
        raise RuntimeError("R25_REQUEST_CONTRACT_INVALID")
    rid=str(req.get("receipt_id") or "")
    declared=str(req.get("receipt_sha256") or "").lower()
    resp=req.get("provider_response")
    if not rid.startswith("MCR_"): raise RuntimeError("R25_RECEIPT_ID_INVALID")
    if not isinstance(resp,dict) or resp.get("contract_version")!=RESPONSE_CONTRACT:
        raise RuntimeError("R25_PROVIDER_RESPONSE_CONTRACT_INVALID")
    if resp.get("provider")!="METRICOOL_MCP": raise RuntimeError("R25_PROVIDER_INVALID")
    if str(resp.get("brand_id") or "")!="6935248": raise RuntimeError("R25_BRAND_ID_INVALID")
    if str(resp.get("timezone") or "")!="America/Sao_Paulo": raise RuntimeError("R25_TIMEZONE_INVALID")
    prov=resp.get("provenance") or {}
    if prov.get("authorized_connector") is not True: raise RuntimeError("R25_AUTHORIZED_CONNECTOR_REQUIRED")
    if prov.get("synthetic") is not False: raise RuntimeError("R25_SYNTHETIC_FORBIDDEN")
    if str(prov.get("transport") or "") not in (
        "CHATGPT_CONNECTED_METRICOOL_PLUGIN","CHATGPT_METRICOOL_CONNECTOR","GOOGLE_SHEETS_RELAY"
    ): raise RuntimeError("R25_TRANSPORT_INVALID")
    datasets=resp.get("datasets")
    if not isinstance(datasets,list) or not datasets: raise RuntimeError("R25_DATASETS_REQUIRED")
    seen=set()
    for d in datasets:
        n=str(d.get("network") or "").upper();c=str(d.get("connector") or "").upper()
        if n not in ("INSTAGRAM","TIKTOK"): raise RuntimeError("R25_NETWORK_INVALID:"+n)
        if n in seen: raise RuntimeError("R25_DUPLICATE_NETWORK:"+n)
        seen.add(n)
        if (n=="INSTAGRAM" and c!="REELS") or (n=="TIKTOK" and c!="POSTS"):
            raise RuntimeError("R25_CONNECTOR_INVALID:"+n)
        if not isinstance(d.get("metrics_requested"),list): raise RuntimeError("R25_METRICS_REQUIRED:"+n)
        if not isinstance(d.get("rows"),list): raise RuntimeError("R25_ROWS_REQUIRED:"+n)
    actual=sha_obj(resp)
    if declared!=actual: raise RuntimeError("R25_RECEIPT_SHA_MISMATCH")
    if rid!="MCR_"+actual[:28]: raise RuntimeError("R25_RECEIPT_ID_SHA_BINDING_INVALID")
    return rid,actual,resp

def inbox_state(filename):
    base=ROOT/"state"/"authorized_analytics_inbox"
    for state in ("done","failed","pending","processing"):
        d=base/state
        if not d.exists(): continue
        p=d/filename
        if p.is_file(): return state,p
        hits=list(d.glob("*_"+filename))
        if hits:return state,hits[-1]
    return None,None

def ack_rows(resp,rid,digest,status,detail,ingested_at):
    pstate="CONNECTED_NO_ROWS" if all(len(d.get("rows") or [])==0 for d in resp["datasets"]) else "READY_WITH_DATA"
    out=[]
    for d in resp["datasets"]:
        out.append({
            "RECEIPT_ID":rid,"PROVIDER":"METRICOOL_MCP","BRAND_ID":"6935248",
            "CAPTURED_AT":resp["captured_at"],"NETWORK":str(d["network"]).upper(),
            "CONNECTOR":str(d["connector"]).upper(),"FROM":d["query_window"]["from"],
            "TO":d["query_window"]["to"],"PROVIDER_STATE":pstate,
            "METRICS_JSON":json.dumps(d["metrics_requested"],ensure_ascii=False,separators=(",",":")),
            "ROWS_JSON":json.dumps(d["rows"],ensure_ascii=False,separators=(",",":")),
            "SOURCE_TRANSPORT":str((resp.get("provenance") or {}).get("transport") or ""),
            "SYNTHETIC":False,"ACK_STATUS":status,"ACK_DETAIL":detail,
            "INGESTED_AT":ingested_at,"RECEIPT_SHA256":digest
        })
    return out

def ingest(req):
    if not LOCK.acquire(blocking=False):
        return {"ok":True,"contract_version":"SM3_R25_PROVIDER_RELAY_RESULT_V1","status":"BUSY_RETRY","ack_rows":[]}
    try:
        rid,digest,resp=validate_request(req)
        committed=ROOT/"state"/"r25"/"receipts"/(rid+".json")
        if committed.is_file():
            old=load(committed)
            if old.get("receipt_sha256")!=digest: raise RuntimeError("R25_IDEMPOTENCY_CONFLICT")
            old["status"]="COMMITTED"
            return old

        incoming=ROOT/"state"/"r25"/"incoming"/(rid+"_"+digest[:16]+".json")
        envelope=ROOT/"state"/"r25"/"envelopes"/(rid+"_"+digest[:16]+".json")
        write_json(incoming,resp)

        engine=required(R22_ENGINE); registry=required(R22_REGISTRY); dispatcher=required(R7_DISPATCHER)
        run_cmd([sys.executable,str(engine),"--root",str(ROOT),"--action","CompileEnvelope",
                 "--input",str(incoming),"--registry",str(registry),"--output",str(envelope)])
        run_cmd([sys.executable,str(engine),"--root",str(ROOT),"--action","SubmitToR7","--input",str(envelope)])

        sub=load(ROOT/"state"/"authorized_analytics_collector"/"SM3_R22_LAST_SUBMISSION.json")
        fn=str(sub.get("inbox_filename") or "")
        if not fn: raise RuntimeError("R25_R22_SUBMISSION_FILENAME_MISSING")
        state,path=inbox_state(fn)
        if state=="pending":
            run_cmd([sys.executable,str(dispatcher),"--root",str(ROOT),"--action","Dispatch","--max-items","100"],allowed=(0,2))
            state,path=inbox_state(fn)
        if state=="failed": raise RuntimeError("R25_TARGET_ENVELOPE_DEAD_LETTER:"+str(path))
        if state!="done":
            return {"ok":True,"contract_version":"SM3_R25_PROVIDER_RELAY_RESULT_V1",
                    "status":"QUEUED_AWAITING_R7_COMMIT","receipt_id":rid,
                    "receipt_sha256":digest,"ack_rows":[],"windows_powershell_polling":False}

        ing=now()
        pstate="CONNECTED_NO_ROWS" if all(len(d.get("rows") or [])==0 for d in resp["datasets"]) else "READY_WITH_DATA"
        result={"ok":True,"contract_version":"SM3_R25_PROVIDER_RELAY_RESULT_V1",
                "status":"COMMITTED","receipt_id":rid,"receipt_sha256":digest,
                "provider_state":pstate,"r7_done_path":str(path),
                "ack_rows":ack_rows(resp,rid,digest,"COMMITTED","R22_R7_R6_COMMITTED|provider_state="+pstate,ing),
                "committed_at":ing,"windows_powershell_polling":False,
                "provider_network_call_performed_by_r25":False}
        write_json(committed,result)
        return result
    finally:
        LOCK.release()

class H(BaseHTTPRequestHandler):
    server_version="SM3-R25/1.0"
    def log_message(self,fmt,*args): sys.stdout.write("[%s] %s\n"%(now(),fmt%args));sys.stdout.flush()
    def sendj(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False,separators=(",",":")).encode("utf-8")
        self.send_response(code);self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        if self.path=="/health":
            missing=[x for x in (R22_ENGINE,R22_REGISTRY,R7_DISPATCHER) if not (ROOT/x).is_file()]
            self.sendj(200,{"ok":not missing,"contract_version":"SM3_R25_PROVIDER_RELAY_SERVICE_V1",
                            "missing_dependencies":missing,"provider_network_call_performed_by_r25":False,
                            "windows_powershell_polling":False})
        else:self.sendj(404,{"ok":False,"error":"NOT_FOUND"})
    def do_POST(self):
        if self.path!="/ingest": self.sendj(404,{"ok":False,"error":"NOT_FOUND"});return
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<2 or n>5_000_000: raise RuntimeError("R25_BODY_SIZE_INVALID")
            result=ingest(json.loads(self.rfile.read(n).decode("utf-8")))
            self.sendj(200,result)
        except Exception as e:
            err={"ok":False,"contract_version":"SM3_R25_PROVIDER_RELAY_RESULT_V1",
                 "error":type(e).__name__+":"+str(e),"failed_at":now(),
                 "traceback":traceback.format_exc()[-5000:],
                 "provider_network_call_performed_by_r25":False,"windows_powershell_polling":False}
            try:write_json(ROOT/"state"/"r25"/"SM3_R25_LAST_ERROR.json",err)
            except Exception:pass
            self.sendj(500,err)

if __name__=="__main__":
    s=ThreadingHTTPServer(("0.0.0.0",PORT),H)
    print("SM3_R25_RELAY_READY port="+str(PORT),flush=True)
    s.serve_forever()
