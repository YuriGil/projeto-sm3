# Projeto SM3 — Video Scene-Aware Backfill v1

## Purpose
Reprocess only legacy video analyses that used VIDEO_CONTACT_SHEET but do not yet persist `ADAPTIVE_SCENE_V2`.

## Canonical selection
A row is eligible only when:
- it is a video;
- `STORAGE_STATUS = ONLINE`;
- `PROCESS_STATUS != DEAD_LETTER`;
- `ANALYSIS_SOURCE = VIDEO_CONTACT_SHEET`;
- `VIDEO_SAMPLING_MODE != ADAPTIVE_SCENE_V2`; and
- legacy `TECHNICAL_METADATA_JSON.contact_sheet_sampling.sampling_mode` is also not v2.

Batch size comes from `11_OS_CONFIG.video.sampling.backfill_batch_limit` (default current value: 6).

## What is updated
The video is downloaded once, reprocessed by media-worker 2.0, a new scene-aware contact sheet is generated, and Vision analysis runs again. This refreshes:
- triage/visual summary and best moment;
- technical/editorial scores;
- Structural Vision/body region/tattoo subject/crop guidance;
- technical metadata;
- sampling diagnostics.

It does not reset curation/content-plan/human approval fields. Downstream stages decide whether a refreshed analysis needs a new explicit curation pass.

## Sampling persistence
New columns:
- VIDEO_SAMPLING_MODE
- VIDEO_SAMPLING_VERSION
- SCENE_DETECTED_COUNT
- SELECTED_FRAME_COUNT
- SAMPLING_FALLBACK_USED
- SAMPLING_FALLBACK_REASON
- SAMPLING_DETAILS_JSON
- VIDEO_REANALYZED_AT

## Reliability
Uses SM3_RELIABILITY_V1 per-media isolation and dual dead-letter sinks.
