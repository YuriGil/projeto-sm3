import sys
sys.path[:0]=["ingestion","approval","publisher","metrics","vision"]
from idempotent_index import classify
from gate import apply_decision
from metricool_live_adapter import preflight
from learning_gate import learning_decision
from provider_adapter import normalize

# duplicate ingestion
assert classify({"A"},[{"drive_file_id":"A"}])[0]["action"]=="SKIP_EXISTING"
# rejection/review never publishes
for d in ["REVISAR","DESCARTAR"]:
    c=apply_decision({"content_id":"X"},d)
    assert c["publish_eligible"] is False
# missing QA/assets / duplicate / past slot
base={"content_id":"X","status":"APROVADO","approval_decision":"APROVAR","render_qa":"PASS",
      "media":["x"],"date":"2026-09-20T10:00:00-03:00"}
assert preflight({**base,"render_qa":"FAIL"},"2026-09-15T10:00:00-03:00")=="BLOCKED_ASSET_QA"
assert preflight({**base,"media":[]},"2026-09-15T10:00:00-03:00")=="BLOCKED_ASSET_QA"
assert preflight(base,"2026-09-15T10:00:00-03:00",["X"])=="BLOCKED_DUPLICATE"
assert preflight(base,"2026-09-21T10:00:00-03:00")=="BLOCKED_PAST_SLOT"
# protected learning
assert learning_decision("approval_required",100)=="HUMAN_REVIEW"
# malformed AI response fails closed
try:
    normalize({"decision":"SELECIONADA"})
    raise AssertionError()
except ValueError: pass
print("HARDENING_PASS")
