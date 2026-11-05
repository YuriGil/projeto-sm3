# SM3 08F — Installer R3 hotfix

The R2 installer had one stale package-validation regex:

`WORKER_VERSION\s*=\s*"2\.14\.0"`

The actual patched worker is intentionally:

- Worker: `2.14.1`
- Art-direction renderer: `2.14.0`

The renderer version stays 2.14.0 because the pixel/render algorithm did not change;
only review idempotency changed.

R3 changes only that stale package-validation regex to:

`WORKER_VERSION\s*=\s*"2\.14\.1"`

The earlier failed R2 installation stopped before copying/rebuilding the Worker, so the
running service remains 2.14.0 until R3 is executed.

Run:

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08F_INSTALL_WORKER_2_14_1_R3.ps1"
```

Then:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08F_VERIFICAR_IDEMPOTENCIA_REVIEW.ps1"
```

Expected:
`SM3_08F_REVIEW_IDEMPOTENCY_FIX_VERIFY_PASS`
