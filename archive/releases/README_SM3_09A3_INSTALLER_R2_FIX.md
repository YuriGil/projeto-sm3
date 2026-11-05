# SM3 09A.3 — Installer R2 hotfix

The original 09A.3 installer had one stale package validation regex:

`WORKER_VERSION\s*=\s*"2\.16\.0"`

but the packaged worker is correctly:

`WORKER_VERSION = "2.16.1"`

The installer therefore aborted before copying/building the worker.

R2 changes only that stale package-contract check to:

`WORKER_VERSION\s*=\s*"2\.16\.1"`

No Worker code change is required beyond the already packaged 2.16.1 source.

Run:

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09A3_INSTALL_WORKER_2_16_1_R2.ps1"
```

Expected:

`SM3_09A3_REFERENCE_MEDIA_ACQUISITION_INSTALL_PASS`
