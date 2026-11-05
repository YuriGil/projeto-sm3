import subprocess,sys
tests=[
"tests/e2e/acceptance.py",
"tests/e2e/test_idempotent_ingestion.py",
"tests/unit/test_media_worker.py",
"tests/unit/test_vision_adapter.py",
"tests/unit/test_publish_learning.py",
"tests/integration/test_full_pipeline.py",
"tests/integration/test_hardening.py"]
ok=0
for t in tests:
    p=subprocess.run([sys.executable,t],capture_output=True,text=True)
    print(f"[{'PASS' if p.returncode==0 else 'FAIL'}] {t}")
    if p.stdout.strip(): print(" ",p.stdout.strip())
    if p.stderr.strip(): print(" ",p.stderr.strip())
    if p.returncode: sys.exit(p.returncode)
    ok+=1
print(f"REGRESSION_SUITE_PASS {ok}/{len(tests)}")
