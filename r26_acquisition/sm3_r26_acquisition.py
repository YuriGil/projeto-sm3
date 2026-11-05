#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,threading,traceback,urllib.request,urllib.error
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

ROOT=Path(os.environ.get("SM3_PROJECT_ROOT","/project")).resolve()
PORT=int(os.environ.get("SM3_R26_PORT","8093"))
R25_URL=os.environ.get("SM3_R25_URL","http://sm3-r25-relay:8092/ingest")
LOCK=threading.Lock()

REQUEST_CONTRACT="SM3_R26_AUTHORIZED_ACQUISITION_REQUEST_V1"
ACQUISITION_CONTRACT="SM3_R26_AUTHORIZED_ACQUISITION_V1"
RESPONSE_CONTRACT="SM3_R26_AUTHORIZED_ACQUISITION_RESULT_V1"
PROVIDER_RESPONSE_CONTRACT="SM3_METRICOOL_AUTHORIZED_RESPONSE_V1"
R25_REQUEST_CONTRACT="SM3_R25_PROVIDER_RELAY_REQUEST_V1"

ALLOWED_TRANSPORTS={"CHATGPT_CONNECTED_METRICOOL_PLUGIN","CHATGPT_METRICOOL_CONNECTOR"}
NETWORK_ORDER={"INSTAGRAM":0,"TIKTOK":1}
EXPECTED_CONNECTORS={"INSTAGRAM":"REELS","TIKTOK":"POSTS"}

def now():
    return datetime.now(timezone.utc).isoformat()

def canon(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def sha_obj(x):
    return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()

def write_json(p,obj):
    p=Path(p)
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(t,p)

def as_false(v):
    if v is False: return True
    return str(v).strip().upper() in {"FALSE","0","NO","NAO","NÃO"}

def parse_json_array(v,label):
    if isinstance(v,list):
        return v
    try:
        x=json.loads(str(v))
    except Exception:
        raise RuntimeError("R26_JSON_PARSE_FAILED:"+label)
    if not isinstance(x,list):
        raise RuntimeError("R26_JSON_NOT_ARRAY:"+label)
    return x

def validate_rows(req):
    if not isinstance(req,dict) or req.get("contract_version")!=REQUEST_CONTRACT:
        raise RuntimeError("R26_REQUEST_CONTRACT_INVALID")
    capture_id=str(req.get("capture_id") or "").strip()
    if not capture_id.startswith("MCA_"):
        raise RuntimeError("R26_CAPTURE_ID_INVALID")
    rows=req.get("acquisition_rows")
    if not isinstance(rows,list) or len(rows)!=2:
        raise RuntimeError("R26_TWO_NETWORK_ROWS_REQUIRED")

    normalized=[]
    seen=set()
    common=None
    for raw in rows:
        if not isinstance(raw,dict):
            raise RuntimeError("R26_ACQUISITION_ROW_INVALID")
        network=str(raw.get("NETWORK") or "").strip().upper()
        connector=str(raw.get("CONNECTOR") or "").strip().upper()
        if network not in EXPECTED_CONNECTORS:
            raise RuntimeError("R26_NETWORK_INVALID:"+network)
        if network in seen:
            raise RuntimeError("R26_DUPLICATE_NETWORK:"+network)
        seen.add(network)
        if connector!=EXPECTED_CONNECTORS[network]:
            raise RuntimeError("R26_CONNECTOR_INVALID:"+network)
        if str(raw.get("CAPTURE_ID") or "").strip()!=capture_id:
            raise RuntimeError("R26_CAPTURE_ID_MISMATCH:"+network)
        if str(raw.get("ROW_KEY") or "").strip()!=capture_id+"|"+network:
            raise RuntimeError("R26_ROW_KEY_INVALID:"+network)
        if str(raw.get("BRAND_ID") or "").strip()!="6935248":
            raise RuntimeError("R26_BRAND_ID_INVALID")
        if str(raw.get("BRAND_LABEL") or "").strip()!="molotov7684":
            raise RuntimeError("R26_BRAND_LABEL_INVALID")
        if str(raw.get("TIMEZONE") or "").strip()!="America/Sao_Paulo":
            raise RuntimeError("R26_TIMEZONE_INVALID")
        if str(raw.get("ACQUISITION_CONTRACT") or "").strip()!=ACQUISITION_CONTRACT:
            raise RuntimeError("R26_ACQUISITION_CONTRACT_INVALID")
        if not as_false(raw.get("SYNTHETIC")):
            raise RuntimeError("R26_SYNTHETIC_FORBIDDEN")
        if str(raw.get("INGEST_STATUS") or "").strip().upper()!="PENDING":
            raise RuntimeError("R26_INGEST_STATUS_NOT_PENDING")
        transport=str(raw.get("SOURCE_TRANSPORT") or "").strip()
        if transport not in ALLOWED_TRANSPORTS:
            raise RuntimeError("R26_SOURCE_TRANSPORT_INVALID")

        metrics=parse_json_array(raw.get("METRICS_JSON"),network+":METRICS_JSON")
        provider_rows=parse_json_array(raw.get("ROWS_JSON"),network+":ROWS_JSON")
        expected_state="CONNECTED_NO_ROWS" if len(provider_rows)==0 else "READY_WITH_DATA"
        if str(raw.get("PROVIDER_STATE") or "").strip().upper()!=expected_state:
            raise RuntimeError("R26_PROVIDER_STATE_MISMATCH:"+network)

        common_now=(
            str(raw.get("CAPTURED_AT") or "").strip(),
            str(raw.get("FROM") or "").strip(),
            str(raw.get("TO") or "").strip(),
            transport,
        )
        if common is None: common=common_now
        elif common_now!=common: raise RuntimeError("R26_GROUP_COMMON_FIELDS_MISMATCH")

        normalized.append({
            "CAPTURE_ID":capture_id,
            "BRAND_ID":"6935248",
            "BRAND_LABEL":"molotov7684",
            "TIMEZONE":"America/Sao_Paulo",
            "CAPTURED_AT":common_now[0],
            "NETWORK":network,
            "CONNECTOR":connector,
            "FROM":common_now[1],
            "TO":common_now[2],
            "METRICS":metrics,
            "ROWS":provider_rows,
            "PROVIDER_STATE":expected_state,
            "SOURCE_TRANSPORT":transport,
            "SYNTHETIC":False,
            "INGEST_STATUS":"PENDING",
            "ACQUISITION_CONTRACT":ACQUISITION_CONTRACT,
            "ROW_KEY":capture_id+"|"+network,
        })

    if seen!={"INSTAGRAM","TIKTOK"}:
        raise RuntimeError("R26_REQUIRED_NETWORK_SET_INVALID")
    normalized.sort(key=lambda r:NETWORK_ORDER[r["NETWORK"]])
    return capture_id,normalized

def build_provider_response(rows):
    datasets=[]
    any_rows=False
    for r in rows:
        if r["ROWS"]: any_rows=True
        datasets.append({
            "network":r["NETWORK"],
            "connector":r["CONNECTOR"],
            "query_window":{"from":r["FROM"],"to":r["TO"]},
            "metrics_requested":r["METRICS"],
            "rows":r["ROWS"],
        })
    interpretation=(
        "AUTHORIZED_CONNECTOR_RETURNED_REAL_ROWS"
        if any_rows else
        "AUTHORIZED_CONNECTOR_RETURNED_ZERO_ROWS; ZERO_ROWS_IS_NOT_ZERO_PERFORMANCE"
    )
    return {
        "contract_version":PROVIDER_RESPONSE_CONTRACT,
        "provider":"METRICOOL_MCP",
        "brand_id":"6935248",
        "brand_label":"molotov7684",
        "timezone":"America/Sao_Paulo",
        "captured_at":rows[0]["CAPTURED_AT"],
        "datasets":datasets,
        "provenance":{
            "authorized_connector":True,
            "connector":"METRICOOL_MCP",
            "transport":rows[0]["SOURCE_TRANSPORT"],
            "synthetic":False,
            "interpretation":interpretation,
        },
    }

def post_json(url,obj,timeout=260):
    b=json.dumps(obj,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    req=urllib.request.Request(url,data=b,headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return r.status,json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        raise RuntimeError("R26_INTERNAL_R25_HTTP_"+str(e.code)+":"+body[-4000:])

def acquisition_ack_rows(rows,receipt_id,provider_state,ingested_at):
    detail="R26_R25_R22_R7_R6_COMMITTED|receipt_id="+receipt_id+"|provider_state="+provider_state
    out=[]
    for r in rows:
        out.append({
            "CAPTURE_ID":r["CAPTURE_ID"],
            "BRAND_ID":r["BRAND_ID"],
            "BRAND_LABEL":r["BRAND_LABEL"],
            "TIMEZONE":r["TIMEZONE"],
            "CAPTURED_AT":r["CAPTURED_AT"],
            "NETWORK":r["NETWORK"],
            "CONNECTOR":r["CONNECTOR"],
            "FROM":r["FROM"],
            "TO":r["TO"],
            "METRICS_JSON":json.dumps(r["METRICS"],ensure_ascii=False,separators=(",",":")),
            "ROWS_JSON":json.dumps(r["ROWS"],ensure_ascii=False,separators=(",",":")),
            "PROVIDER_STATE":r["PROVIDER_STATE"],
            "SOURCE_TRANSPORT":r["SOURCE_TRANSPORT"],
            "SYNTHETIC":False,
            "INGEST_STATUS":"COMMITTED",
            "INGEST_DETAIL":detail,
            "INGESTED_AT":ingested_at,
            "ACQUISITION_CONTRACT":ACQUISITION_CONTRACT,
            "ROW_KEY":r["ROW_KEY"],
        })
    return out

def relay_ack_rows(r25_rows):
    out=[]
    for x in r25_rows:
        y=dict(x)
        network=str(y.get("NETWORK") or "").upper()
        rid=str(y.get("RECEIPT_ID") or "")
        if network not in EXPECTED_CONNECTORS or not rid.startswith("MCR_"):
            raise RuntimeError("R26_R25_ACK_ROW_INVALID")
        y["ROW_KEY"]=rid+"|"+network
        out.append(y)
    out.sort(key=lambda r:NETWORK_ORDER[str(r["NETWORK"]).upper()])
    return out

def ingest(req):
    if not LOCK.acquire(blocking=False):
        return {"ok":True,"contract_version":RESPONSE_CONTRACT,"status":"BUSY_RETRY",
                "relay_rows":[],"acquisition_ack_rows":[]}
    try:
        capture_id,rows=validate_rows(req)
        provider_response=build_provider_response(rows)
        digest=sha_obj(provider_response)
        receipt_id="MCR_"+digest[:28]
        req_fingerprint=sha_obj({"capture_id":capture_id,"rows":rows})
        committed=ROOT/"state"/"r26"/"captures"/(capture_id+".json")

        if committed.is_file():
            old=json.loads(committed.read_text(encoding="utf-8-sig"))
            if old.get("request_fingerprint")!=req_fingerprint:
                raise RuntimeError("R26_IDEMPOTENCY_CONFLICT")
            return old

        r25_req={
            "contract_version":R25_REQUEST_CONTRACT,
            "receipt_id":receipt_id,
            "receipt_sha256":digest,
            "provider_response":provider_response,
        }
        code,r25=post_json(R25_URL,r25_req)
        if code!=200 or not isinstance(r25,dict) or r25.get("ok") is not True:
            raise RuntimeError("R26_R25_RESPONSE_INVALID")

        r25_status=str(r25.get("status") or "")
        if r25_status in {"BUSY_RETRY","QUEUED_AWAITING_R7_COMMIT"}:
            return {
                "ok":True,"contract_version":RESPONSE_CONTRACT,"status":r25_status,
                "capture_id":capture_id,"receipt_id":receipt_id,"receipt_sha256":digest,
                "provider_state":r25.get("provider_state"),
                "relay_rows":[],"acquisition_ack_rows":[],
                "provider_network_call_performed_by_r26":False,
                "internal_r25_call_performed":True,
                "windows_powershell_polling":False,
            }
        if r25_status!="COMMITTED":
            raise RuntimeError("R26_R25_NOT_COMMITTED:"+r25_status)

        rr=relay_ack_rows(r25.get("ack_rows") or [])
        if len(rr)!=2:
            raise RuntimeError("R26_R25_ACK_ROW_COUNT_INVALID")
        pstate=str(r25.get("provider_state") or "")
        ing=now()
        result={
            "ok":True,
            "contract_version":RESPONSE_CONTRACT,
            "status":"COMMITTED",
            "capture_id":capture_id,
            "receipt_id":receipt_id,
            "receipt_sha256":digest,
            "provider_state":pstate,
            "relay_rows":rr,
            "acquisition_ack_rows":acquisition_ack_rows(rows,receipt_id,pstate,ing),
            "request_fingerprint":req_fingerprint,
            "committed_at":ing,
            "provider_network_call_performed_by_r26":False,
            "internal_r25_call_performed":True,
            "r25_provider_network_call_performed":bool(r25.get("provider_network_call_performed_by_r25",False)),
            "windows_powershell_polling":False,
        }
        write_json(committed,result)
        return result
    finally:
        LOCK.release()

class H(BaseHTTPRequestHandler):
    server_version="SM3-R26/1.0"
    def log_message(self,fmt,*args):
        print("[%s] %s"%(now(),fmt%args),flush=True)
    def sendj(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False,separators=(",",":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        if self.path!="/health":
            self.sendj(404,{"ok":False,"error":"NOT_FOUND"}); return
        reachable=False
        detail=None
        try:
            with urllib.request.urlopen(R25_URL.rsplit("/",1)[0]+"/health",timeout=3) as r:
                x=json.loads(r.read().decode("utf-8"))
                reachable=bool(x.get("ok"))
        except Exception as e:
            detail=type(e).__name__+":"+str(e)
        self.sendj(200 if reachable else 503,{
            "ok":reachable,
            "contract_version":"SM3_R26_AUTHORIZED_ACQUISITION_SERVICE_V1",
            "r25_relay_reachable":reachable,
            "r25_detail":detail,
            "provider_network_call_performed_by_r26":False,
            "windows_powershell_polling":False,
        })
    def do_POST(self):
        if self.path!="/compile-and-ingest":
            self.sendj(404,{"ok":False,"error":"NOT_FOUND"}); return
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<2 or n>8_000_000:
                raise RuntimeError("R26_BODY_SIZE_INVALID")
            req=json.loads(self.rfile.read(n).decode("utf-8"))
            self.sendj(200,ingest(req))
        except Exception as e:
            err={
                "ok":False,
                "contract_version":RESPONSE_CONTRACT,
                "error":type(e).__name__+":"+str(e),
                "failed_at":now(),
                "traceback":traceback.format_exc()[-5000:],
                "provider_network_call_performed_by_r26":False,
                "windows_powershell_polling":False,
            }
            try:
                write_json(ROOT/"state"/"r26"/"SM3_R26_LAST_ERROR.json",err)
            except Exception:
                pass
            self.sendj(500,err)

if __name__=="__main__":
    s=ThreadingHTTPServer(("0.0.0.0",PORT),H)
    print("SM3_R26_ACQUISITION_READY port="+str(PORT),flush=True)
    s.serve_forever()
