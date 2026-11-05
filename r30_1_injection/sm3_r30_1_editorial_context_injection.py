#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, datetime as dt, hashlib, json, os, sys, time, urllib.request
from pathlib import Path

REPORT_CONTRACT="SM3_EDITORIAL_CONTEXT_INJECTION_REPORT_V1"
BOUND_CONTRACT="SM3_NATIVE_PUBLICATION_ARTIFACT_BOUND_REQUEST_V1"

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",",":"))

def sha_obj(x):
    return hashlib.sha256(canon(x).encode("utf-8")).hexdigest()

def load_json(path, default=None):
    p=Path(path)
    if not p.is_file(): return default
    try: return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception: return default

def write_json(path,obj):
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    os.replace(tmp,p)

def fetch_json(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def resolve_ref(openapi, ref):
    if not isinstance(ref,str) or not ref.startswith("#/"):
        raise RuntimeError("R30_1_UNSUPPORTED_SCHEMA_REF:"+str(ref))
    node=openapi
    for part in ref[2:].split("/"):
        if part not in node:
            raise RuntimeError("R30_1_SCHEMA_REF_NOT_FOUND:"+ref)
        node=node[part]
    return node

def schema_info(openapi, name):
    schemas=((openapi.get("components") or {}).get("schemas") or {})
    s=schemas.get(name)
    if not isinstance(s,dict):
        raise RuntimeError("R30_1_TARGET_SCHEMA_MISSING:"+name)
    props=s.get("properties") or {}
    required=list(s.get("required") or [])
    return {
        "name":name,
        "required":required,
        "properties":list(props.keys()),
        "schema_sha256":sha_obj(s),
        "schema":s
    }

def validate_type(name, value, spec):
    # Minimal fail-closed validation for the request envelope.
    if "$ref" in spec:
        return
    typ=spec.get("type")
    if typ=="string" and not isinstance(value,str):
        raise RuntimeError("R30_1_FIELD_TYPE_INVALID:"+name+":string")
    if typ=="integer" and (not isinstance(value,int) or isinstance(value,bool)):
        raise RuntimeError("R30_1_FIELD_TYPE_INVALID:"+name+":integer")
    if typ=="number" and (not isinstance(value,(int,float)) or isinstance(value,bool)):
        raise RuntimeError("R30_1_FIELD_TYPE_INVALID:"+name+":number")
    if typ=="array" and not isinstance(value,list):
        raise RuntimeError("R30_1_FIELD_TYPE_INVALID:"+name+":array")
    if typ=="object" and not isinstance(value,dict):
        raise RuntimeError("R30_1_FIELD_TYPE_INVALID:"+name+":object")
    if typ=="boolean" and not isinstance(value,bool):
        raise RuntimeError("R30_1_FIELD_TYPE_INVALID:"+name+":boolean")

def validate_base(base, info):
    if not isinstance(base,dict):
        raise RuntimeError("R30_1_BASE_REQUEST_NOT_OBJECT")
    missing=[k for k in info["required"] if k not in base]
    if missing:
        raise RuntimeError("R30_1_BASE_REQUEST_REQUIRED_FIELDS_MISSING:"+",".join(missing))

    props=info["schema"].get("properties") or {}
    for k in info["required"]:
        if k in props:
            validate_type(k,base.get(k),props[k])

    if "editorial_context" in base:
        raise RuntimeError("R30_1_BASE_REQUEST_ALREADY_HAS_EDITORIAL_CONTEXT")

def validate_context(ctx):
    if not isinstance(ctx,dict):
        raise RuntimeError("R30_1_EDITORIAL_CONTEXT_MISSING_OR_INVALID")
    if ctx.get("contract_version")!="SM3_PREEDIT_EDITORIAL_CONTEXT_V1":
        raise RuntimeError("R30_1_EDITORIAL_CONTEXT_CONTRACT_INVALID")
    if ctx.get("target_contract")!="NativePublicationArtifactRequest.editorial_context":
        raise RuntimeError("R30_1_EDITORIAL_CONTEXT_TARGET_INVALID")
    guards=ctx.get("guards") or {}
    if guards.get("no_rendering_in_bridge") is not True:
        raise RuntimeError("R30_1_EDITORIAL_CONTEXT_GUARD_INVALID")

def bind(base, ctx, info):
    validate_base(base,info)
    validate_context(ctx)

    out=copy.deepcopy(base)
    out["editorial_context"]=ctx

    # Validate that injection did not alter any upstream field.
    for k,v in base.items():
        if out.get(k)!=v:
            raise RuntimeError("R30_1_UPSTREAM_FIELD_MUTATED:"+str(k))

    # Schema allows editorial_context in the live target.
    if "editorial_context" not in info["properties"]:
        raise RuntimeError("R30_1_LIVE_SCHEMA_NO_EDITORIAL_CONTEXT")

    return out

def paths(root,policy):
    p=policy["paths"]
    return {k:root/v for k,v in p.items()}

def run_once(root,policy, openapi_override=None):
    p=paths(root,policy)
    ctx=load_json(p["editorial_context"])
    validate_context(ctx)

    openapi=openapi_override
    if openapi is None:
        openapi=fetch_json(policy["worker_openapi_url"])
    info=schema_info(openapi,policy["target_schema"])

    report={
      "contract_version":REPORT_CONTRACT,
      "generated_at":now(),
      "status":None,
      "target_schema":info["name"],
      "target_schema_sha256":info["schema_sha256"],
      "live_required_fields":info["required"],
      "live_property_names":info["properties"],
      "editorial_context_sha256":sha_obj(ctx),
      "base_request_present":p["inbox"].is_file(),
      "bound_request_written":False,
      "guards":{
        "required_fields_guessed":False,
        "source_media_fabricated":False,
        "revision_fabricated":False,
        "state_etag_fabricated":False,
        "upstream_fields_mutated":False,
        "render_called":False,
        "worker_mutated":False,
        "automatic_publication":False,
        "automatic_reply":False
      }
    }

    if not p["inbox"].is_file():
        report["status"]="WAITING_FOR_BASE_NATIVE_REQUEST"
        report["next_action"]="UPSTREAM_NATIVE_REQUEST_BUILDER_MUST_WRITE_CANONICAL_BASE_REQUEST"
        report["report_sha256"]=sha_obj(report)
        write_json(p["binding_report"],report)
        return report

    base=load_json(p["inbox"])
    bound=bind(base,ctx,info)

    envelope={
      "contract_version":BOUND_CONTRACT,
      "generated_at":now(),
      "target_endpoint":"/production/native-publication-artifact/render",
      "target_schema":info["name"],
      "target_schema_sha256":info["schema_sha256"],
      "base_request_sha256":sha_obj(base),
      "editorial_context_sha256":sha_obj(ctx),
      "request":bound,
      "guards":{
        "validated_against_live_openapi":True,
        "upstream_request_preserved":True,
        "only_editorial_context_injected":True,
        "render_called":False,
        "automatic_publication":False
      }
    }
    envelope["bound_request_sha256"]=sha_obj(envelope)
    write_json(p["outbox"],envelope)

    report["status"]="BOUND_READY_FOR_NATIVE_RENDER_CALL"
    report["bound_request_written"]=True
    report["base_request_sha256"]=sha_obj(base)
    report["bound_request_sha256"]=envelope["bound_request_sha256"]
    report["next_action"]="DOWNSTREAM_MAY_CALL_NATIVE_RENDER_ONLY_AFTER_SEPARATE_EXECUTION_GATE"
    report["report_sha256"]=sha_obj(report)
    write_json(p["binding_report"],report)
    return report

def health_from_report(report):
    return {
      "contract_version":"SM3_EDITORIAL_CONTEXT_INJECTION_HEALTH_V1",
      "ok":True,
      "observed_at":now(),
      "status":report["status"],
      "target_schema":report["target_schema"],
      "target_schema_sha256":report["target_schema_sha256"],
      "live_required_field_count":len(report["live_required_fields"]),
      "live_required_fields":report["live_required_fields"],
      "base_request_present":report["base_request_present"],
      "bound_request_written":report["bound_request_written"],
      "render_called":False,
      "worker_mutated":False,
      "automatic_publication":False,
      "automatic_reply":False
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default=os.environ.get("SM3_PROJECT_ROOT","/project"))
    ap.add_argument("--policy",default=None)
    ap.add_argument("--once",action="store_true")
    ap.add_argument("--daemon",action="store_true")
    ap.add_argument("--interval",type=int,default=int(os.environ.get("SM3_R30_1_INTERVAL_SECONDS","900")))
    a=ap.parse_args()

    root=Path(a.project_root).resolve()
    pp=Path(a.policy) if a.policy else root/"SM3_09D_A11_A18_R30_1_INJECTION_POLICY_v1.json"
    policy=load_json(pp)
    if not isinstance(policy,dict) or policy.get("contract_version")!="SM3_EDITORIAL_CONTEXT_INJECTION_POLICY_V1":
        raise RuntimeError("R30_1_POLICY_INVALID")

    def cycle():
        report=run_once(root,policy)
        h=health_from_report(report)
        write_json(paths(root,policy)["health"],h)
        return h

    if a.once:
        h=cycle()
        print("R30_1_STATUS="+str(h["status"]))
        print("R30_1_TARGET_SCHEMA="+str(h["target_schema"]))
        print("R30_1_TARGET_SCHEMA_SHA256="+str(h["target_schema_sha256"]))
        print("R30_1_LIVE_REQUIRED_FIELD_COUNT="+str(h["live_required_field_count"]))
        print("R30_1_LIVE_REQUIRED_FIELDS="+",".join(h["live_required_fields"]))
        print("R30_1_BASE_REQUEST_PRESENT="+str(h["base_request_present"]))
        print("R30_1_BOUND_REQUEST_WRITTEN="+str(h["bound_request_written"]))
        print("R30_1_RENDER_CALLED=False")
        print("R30_1_AUTOMATIC_PUBLICATION=False")
        print("SM3_09D_A11_A18_R30_1_EDITORIAL_CONTEXT_INJECTION_v1_PASS")
        return

    if not a.daemon: raise RuntimeError("R30_1_MODE_REQUIRED")
    while True:
        started=time.time()
        try:
            h=cycle()
            print("R30_1_CYCLE_PASS|status="+h["status"]+"|base="+str(h["base_request_present"])+"|bound="+str(h["bound_request_written"]),flush=True)
        except Exception as e:
            write_json(paths(root,policy)["health"],{
              "contract_version":"SM3_EDITORIAL_CONTEXT_INJECTION_HEALTH_V1",
              "ok":False,"observed_at":now(),
              "error":type(e).__name__+":"+str(e),
              "render_called":False,"worker_mutated":False,
              "automatic_publication":False,"automatic_reply":False
            })
            print("R30_1_CYCLE_FAIL_CLOSED="+type(e).__name__+":"+str(e),file=sys.stderr,flush=True)
        time.sleep(max(1,a.interval-(time.time()-started)))

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("SM3_R30_1_FAIL_CLOSED:"+type(e).__name__+":"+str(e),file=sys.stderr)
        raise SystemExit(1)
