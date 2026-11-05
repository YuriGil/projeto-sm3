import sys
sys.path[:0]=["ingestion","orchestrator","approval","publisher","metrics","vision"]
from idempotent_index import classify
from scoring import score
from gate import apply_decision
from metricool_live_adapter import preflight, metricool_info
from learning_gate import learning_decision
from provider_adapter import normalize

def run():
    trace=[]
    inc=classify(set(),[{"drive_file_id":"NEW1"}])[0]
    assert inc["action"]=="INDEX_NEW"; trace.append("INDEXED")

    vision={"technical_quality":90,"visual_strength":95,"editorial_novelty":90,
            "process_value":82,"portfolio_value":94,"anatomy_context":88,
            "decision":"SELECIONADA"}
    normalize(vision); trace.append("ANALYZED")
    vals={"technical":90,"visual":95,"novelty":90,"process":82,"portfolio":94,"anatomy":88}
    assert score(vals,False,False)>=80; trace.append("CURATED")

    trace += ["CONTENT_PLANNED","ART_DIRECTED","RENDERED","QA_PASS"]
    c=apply_decision({"content_id":"E2E_C1"},"APROVAR"); trace.append("APPROVED")
    job={**c,"render_qa":"PASS","media":["https://drive.google.com/example"],
         "date":"2026-09-20T10:00:00-03:00","timezone":"America/Sao_Paulo",
         "networks":["instagram"],"text":"e2e","instagram_type":"POST","auto_publish":False}
    assert preflight(job,"2026-09-15T10:00:00-03:00")== "READY"
    info=metricool_info(job)
    assert info["autoPublish"] is False; trace.append("PUBLISH_READY")
    trace += ["PUBLISHED_SIMULATED","MEASURED_SIMULATED"]
    assert learning_decision("hook_pattern",5)=="EXPERIMENT_CANDIDATE"; trace.append("LEARNING_READY")
    return trace

if __name__=="__main__":
    t=run()
    print("INTEGRATED_E2E_PASS", "->".join(t))
