
# SM3 07A v1.1 — Write contract + idempotent variant recovery

The v1 workflow failed in `BUILD — VARIANT STATE WRITE` because the Code node was configured as
`Run Once for Each Item` but returned an array (`[{ json: ... }]`). In this mode n8n expects a
single item object (`{ json: ... }`).

The failure happened *after* `AI — PLAN EDIT VARIANTS`, so variant-set JSON files may already exist
in the media worker. A naive rerun would generate a second set and spend another model call.

v1.1 therefore fixes both problems:

1. `BUILD — VARIANT STATE WRITE` returns one object per item.
2. Media Worker 2.1.1 makes `/production/plan-variants` idempotent.
   Existing matching v2.1.0 sets are reused automatically.
3. New sets persist a SHA-256 request fingerprint.
4. Fresh variants are generated only with `force_new=true`.

Expected audit on the first recovery rerun:
- `status = VARIANT_SETS_PLANNED`
- `rows_updated = 2`
- `reused_existing_count` will normally be 2 if both v2.1.0 sets survived the failed run.
