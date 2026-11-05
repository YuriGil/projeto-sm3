import sys
sys.path[:0]=["approval","publisher","metrics"]
from gate import apply_decision
from metricool_live_adapter import preflight,metricool_info
from learning_gate import learning_decision
c=apply_decision({"content_id":"C1"},"APROVAR")
assert c["publish_eligible"] and c["status"]=="APROVADO"
job={**c,"render_qa":"PASS","media":["https://drive.google.com/example"],"date":"2026-09-20T10:00:00-03:00",
     "timezone":"America/Sao_Paulo","networks":["instagram","tiktok"],"text":"teste","instagram_type":"POST"}
assert preflight(job,"2026-09-15T10:00:00-03:00")== "READY"
assert preflight(job,"2026-09-15T10:00:00-03:00",["C1"])=="BLOCKED_DUPLICATE"
assert preflight({**job,"status":"REVISAR"},"2026-09-15T10:00:00-03:00")=="BLOCKED_APPROVAL"
assert preflight(job,"2026-09-21T10:00:00-03:00")=="BLOCKED_PAST_SLOT"
info=metricool_info(job)
assert info["providers"]==[{"network":"instagram"},{"network":"tiktok"}]
assert info["publicationDate"]["timezone"]=="America/Sao_Paulo"
assert info["autoPublish"] is False
assert learning_decision("semantic_crop",99)=="HUMAN_REVIEW"
assert learning_decision("hook_pattern",4)=="INSUFFICIENT_SAMPLE"
assert learning_decision("hook_pattern",5)=="EXPERIMENT_CANDIDATE"
print("PUBLISH_LEARNING_ACCEPTANCE_PASS")
