import sys
sys.path.insert(0,"ingestion")
from idempotent_index import *
assert validate_project_id("TATTOO_0001")=="TATTOO_0001"
try: validate_project_id("tattoo-1"); raise AssertionError()
except ValueError: pass
x=classify({"A","B"},[{"drive_file_id":"B"},{"drive_file_id":"C"},{"drive_file_id":"C"}])
assert [i["action"] for i in x]==["SKIP_EXISTING","INDEX_NEW","SKIP_EXISTING"]
assert media_key("C")=="gdrive:C"
print("IDEMPOTENT_INGESTION_PASS")
