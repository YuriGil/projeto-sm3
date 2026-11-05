import sys
sys.path.insert(0,"vision")
from provider_adapter import *
q=build_request("TATTOO_0002","M0004","proxy.jpg")
assert q["response_contract"]=="media_analysis.schema.json"
good={"technical_quality":90,"visual_strength":95,"editorial_novelty":88,"process_value":75,"portfolio_value":96,"anatomy_context":90,"decision":"SELECIONADA"}
assert normalize(good)["decision"]=="SELECIONADA"
bad=dict(good); bad["near_duplicate_of"]="M0004"
try: normalize(bad); raise AssertionError()
except ValueError as e: assert str(e)=="DUPLICATE_CANNOT_ADVANCE"
bad2=dict(good); bad2["technical_quality"]=101
try: normalize(bad2); raise AssertionError()
except ValueError: pass
bad3=dict(good); del bad3["visual_strength"]
try: normalize(bad3); raise AssertionError()
except ValueError: pass
print("VISION_ADAPTER_ACCEPTANCE_PASS")
