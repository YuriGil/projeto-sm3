# SM3 08F — Worker 2.14.1 — stable review idempotency fix

The first R2 feedback POST succeeded and created:

- review_id: `AR_a6726768de114250df83550751114472`
- review_sha256: `c8ffa545320d077bdde66ce30519a532d7446f553d63f460bb09b3a46fcda1c9`

A second identical POST returned `ART_DIRECTION_REVIEW_IDEMPOTENCY_CONFLICT`.

Cause: Worker 2.14.0 generated a fresh `created_at` before calculating `review_sha256`.
The idempotency branch then compared the fresh hash to the persisted hash. Because
timestamps differ, a legitimate retry could never be considered identical.

Worker 2.14.1 fixes only this contract behavior. The art-direction renderer remains
version 2.14.0 because no pixels/render algorithm changed.

The existing review is preserved byte-for-byte. On retry, the Worker verifies its
stored hash and stable canonical request fields, then returns the original record
with `reused_existing=true`.

No REV5 is created.

Install:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08F_INSTALL_WORKER_2_14_1_R2.ps1"
```

Then verify the exact already-persisted review can be retried:

Set `SM3_08F_EDIT_SESSION_ID` in the local environment first. Do not commit the session ID.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08F_VERIFICAR_IDEMPOTENCIA_REVIEW.ps1"
```

Expected:

`SM3_08F_REVIEW_IDEMPOTENCY_FIX_VERIFY_PASS`

Import and execute:

`PROJETO_SM3_08F_ART_DIRECTION_VARIANT_LAB_v1_1_IDEMPOTENCY_FIX.json`

Then download/verify:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08F_VERIFICAR_E_BAIXAR_VARIANTES_R2.ps1"
```
