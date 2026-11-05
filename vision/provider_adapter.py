import json
REQUIRED=["technical_quality","visual_strength","editorial_novelty","process_value","portfolio_value","anatomy_context","decision"]
DECISIONS={"SELECIONADA","RESERVA","DESCARTAR"}

def build_request(project_id,media_id,proxy_ref,kind="image"):
    return {"task":"semantic_media_analysis","project_id":project_id,"media_id":media_id,
            "media":{"kind":kind,"proxy_ref":proxy_ref},
            "rules":{"discard_does_not_delete":True,"tattoo_is_protagonist":True,
                     "near_duplicates_do_not_advance":True},
            "response_contract":"media_analysis.schema.json"}

def validate_response(x):
    missing=[k for k in REQUIRED if k not in x]
    if missing: raise ValueError("MISSING:"+",".join(missing))
    if x["decision"] not in DECISIONS: raise ValueError("INVALID_DECISION")
    for k in REQUIRED[:-1]:
        v=x[k]
        if not isinstance(v,(int,float)) or not 0<=v<=100: raise ValueError("INVALID_SCORE:"+k)
    if x.get("near_duplicate_of") and x["decision"]=="SELECIONADA":
        raise ValueError("DUPLICATE_CANNOT_ADVANCE")
    return x

def normalize(provider_response):
    # Provider-specific transport ends here; downstream receives one canonical object.
    return validate_response(dict(provider_response))
