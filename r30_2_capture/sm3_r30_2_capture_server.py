#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, json, os, re, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(os.environ.get("SM3_PROJECT_ROOT","/project")).resolve()
POLICY_PATH=ROOT/"SM3_09D_A11_A18_R30_2_CAPTURE_POLICY_v1.json"
POLICY=None
CAP=None
INBOX=None
RECEIPT=None
HISTORY=None

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def canon(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def sha_obj(x): return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()
def load_json(path): return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def write_json(path,obj):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(t,p)

def configure(root=None, policy=None):
    global ROOT,POLICY_PATH,POLICY,CAP,INBOX,RECEIPT,HISTORY
    if root is not None:
        ROOT=Path(root).resolve()
        POLICY_PATH=ROOT/"SM3_09D_A11_A18_R30_2_CAPTURE_POLICY_v1.json"
    POLICY = policy if policy is not None else load_json(POLICY_PATH)
    if POLICY.get("contract_version")!="SM3_NATIVE_REQUEST_CAPTURE_POLICY_V1":
        raise RuntimeError("R30_2_POLICY_INVALID")
    CAP=POLICY["capture"]
    INBOX=ROOT/CAP["inbox_path"]
    RECEIPT=ROOT/CAP["receipt_path"]
    HISTORY=ROOT/CAP["history_dir"]

def ensure_config():
    if CAP is None:
        configure()

def validate_request(x):
    ensure_config()
    if not isinstance(x,dict):
        raise ValueError("R30_2_REQUEST_NOT_OBJECT")
    missing=[k for k in CAP["required_fields"] if k not in x]
    if missing:
        raise ValueError("R30_2_REQUIRED_FIELDS_MISSING:"+",".join(missing))
    for k in ("project_id","content_id","edit_session_id","expected_state_etag"):
        if not isinstance(x[k],str) or not x[k].strip():
            raise ValueError("R30_2_FIELD_INVALID:"+k)
    if not isinstance(x["expected_revision"],int) or isinstance(x["expected_revision"],bool):
        raise ValueError("R30_2_FIELD_INVALID:expected_revision")
    if not re.fullmatch(r"[a-fA-F0-9]{64}",x["expected_state_etag"]):
        raise ValueError("R30_2_STATE_ETAG_INVALID")
    if not isinstance(x["source_media"],list) or not x["source_media"]:
        raise ValueError("R30_2_SOURCE_MEDIA_INVALID")
    for i,m in enumerate(x["source_media"]):
        if not isinstance(m,dict):
            raise ValueError("R30_2_SOURCE_MEDIA_ITEM_INVALID:"+str(i))
        for k in ("media_id","source_path","expected_sha256"):
            if not isinstance(m.get(k),str) or not m.get(k):
                raise ValueError("R30_2_SOURCE_MEDIA_FIELD_INVALID:"+str(i)+":"+k)
        if not re.fullmatch(r"[a-fA-F0-9]{64}",m["expected_sha256"]):
            raise ValueError("R30_2_SOURCE_MEDIA_SHA_INVALID:"+str(i))

def capture(x):
    ensure_config()
    validate_request(x)
    original_context=x.get("editorial_context")
    strip=set(CAP["strip_fields_from_base"])
    base={k:v for k,v in x.items() if k not in strip}
    receipt={
      "contract_version":"SM3_NATIVE_REQUEST_CAPTURE_RECEIPT_V1",
      "captured_at":now(),
      "capture_id":"",
      "base_request_sha256":sha_obj(base),
      "original_request_sha256":sha_obj(x),
      "original_editorial_context_present":original_context is not None,
      "original_editorial_context_sha256":sha_obj(original_context) if original_context is not None else None,
      "project_id":base["project_id"],
      "content_id":base["content_id"],
      "edit_session_id":base["edit_session_id"],
      "expected_revision":base["expected_revision"],
      "expected_state_etag":base["expected_state_etag"],
      "source_media_count":len(base["source_media"]),
      "identity_asset_count":len(base.get("identity_assets") or []),
      "guards":{
        "source_media_fabricated":False,
        "revision_fabricated":False,
        "state_etag_fabricated":False,
        "editorial_context_stripped_from_base":True,
        "render_called":False,
        "publication_called":False
      }
    }
    receipt["capture_id"]="NRC_"+sha_obj(receipt)[:24]
    HISTORY.mkdir(parents=True,exist_ok=True)
    write_json(INBOX,base)
    write_json(RECEIPT,receipt)
    write_json(HISTORY/(receipt["capture_id"]+".base.json"),base)
    write_json(HISTORY/(receipt["capture_id"]+".receipt.json"),receipt)
    return receipt

class H(BaseHTTPRequestHandler):
    server_version="SM3R30Capture/1"
    def log_message(self,fmt,*args):
        sys.stdout.write("R30_2_HTTP="+(fmt%args)+"\n");sys.stdout.flush()
    def sendj(self,status,obj):
        b=json.dumps(obj,ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        if self.path=="/health":
            self.sendj(200,{
              "ok":True,
              "contract_version":"SM3_NATIVE_REQUEST_CAPTURE_HEALTH_V1",
              "capture_only":True,
              "render_called":False,
              "publication_called":False
            })
        else:
            self.sendj(404,{"ok":False,"error":"NOT_FOUND"})
    def do_POST(self):
        if self.path!="/capture":
            return self.sendj(404,{"ok":False,"error":"NOT_FOUND"})
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<=0 or n>20_000_000:
                raise ValueError("R30_2_BODY_SIZE_INVALID")
            x=json.loads(self.rfile.read(n).decode("utf-8"))
            r=capture(x)
            self.sendj(200,{
              "ok":True,
              "status":"CAPTURED_NOT_RENDERED",
              "capture_id":r["capture_id"],
              "base_request_sha256":r["base_request_sha256"],
              "render_called":False,
              "publication_called":False
            })
        except Exception as e:
            self.sendj(422,{
              "ok":False,
              "error":type(e).__name__+":"+str(e),
              "render_called":False,
              "publication_called":False
            })

if __name__=="__main__":
    configure()
    port=int(os.environ.get("SM3_R30_2_PORT","8099"))
    print("R30_2_CAPTURE_SERVER_READY|port="+str(port),flush=True)
    ThreadingHTTPServer(("0.0.0.0",port),H).serve_forever()
