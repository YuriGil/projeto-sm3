from pathlib import Path
import importlib.util, os

os.environ.setdefault("MEDIA_ROOT", "/tmp/sm3_media_verify")
p = Path(__file__).resolve().parents[1] / "worker" / "worker_service.py"
spec = importlib.util.spec_from_file_location("sm3_worker_verify", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

h = m.health()
assert h["version"] == "1.8.0", h
assert h["structural_downstream"] is True, h
assert h["contact_sheet_sampling"] == "ADAPTIVE_UNIFORM_V1", h
print("SM3_WORKER_1_8_SOURCE_OK", h)
