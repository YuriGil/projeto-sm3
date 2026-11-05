# Projeto SM3 — 07B Variant Previews v1

Purpose: turn the immutable AI variant recipes created by 07A into low-resolution visual review previews.

## Worker 2.2.0

New endpoints:
- POST `/production/render-variant-previews`
- GET `/production/variant-previews/{project_id}/{content_id}/{variant_set_id}`

The renderer is idempotent: an existing valid manifest is reused unless `force=true`.

## Preview behavior

- REEL / STORY: 540x960 review MP4.
- CARROSSEL / POST: 540x675 review MP4 slideshow.
- Uses recipe media order, timeline, focal point and conservative framing.
- Does not destroy originals.
- Final typography, identity overlays, audio mix, animated pan/scan and final QA are intentionally deferred.
- These previews are for choosing a variant, not for publishing.

## Sheet state after success

`VARIANT_REVIEW_STATUS = PREVIEW_READY`
`RENDER_STATUS = VARIANT_PREVIEWS_READY`
`PIPELINE_STATE = VARIANT_REVIEW_READY`
`STATE_VERSION = SM3_STATE_V4`
