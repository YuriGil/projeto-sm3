# Projeto SM3 — 09B — Video Style Feature Extractor

09B is the first module whose primary object is VIDEO editing language.

It does not copy a reference creator. It converts a real reference video into abstract, reusable evidence.

## Worker 2.16.0

New contracts:
- `SM3_REFERENCE_VIDEO_ANALYSIS_V1`
- `SM3_REFERENCE_VIDEO_ANALYZER_V1`
- `SM3_REFERENCE_VIDEO_VISION_V1`

Preserved:
- reference profile/item/metric/features contracts
- canonical renderer 2.8.0
- native publication renderer 2.13.1
- art-direction renderer 2.14.0

## What is measured mechanically

- duration via ffprobe
- scene/cut evidence via FFmpeg scene scoring
- cuts per 10 seconds
- median shot duration
- contact sheet using ADAPTIVE_SCENE_V2
- audio onset evidence and cut/onset proximity
- adaptive contrast / saturation / temperature
- sharpness evidence

## What vision describes

- approximate hook duration
- camera motion
- subject scale and coverage
- text density and position
- transition family
- speed-ramp evidence only when visible
- identity usage
- tattoo presentation
- story structure

`UNKNOWN` is an acceptable answer. Absence of evidence is not converted into certainty.

## Important media rule

Instagram URL != video bytes.

09B only analyzes a row when `32_REFERENCE_ITEMS.LOCAL_MEDIA_REF` points to a real file visible to the Worker inside `/data/media`. Example:

`/data/media/reference_sources/gogoo_reel_01.mp4`

Rows without a local media file stay in the corpus as provenance but are skipped by 09B.

## Install

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09B_INSTALL_WORKER_2_16_0.ps1"
```

Expected: `SM3_09B_REFERENCE_VIDEO_ANALYZER_INSTALL_PASS`

Then:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09B_VERIFICAR_ANALISADOR_VIDEO.ps1"
```

Expected: `SM3_09B_REFERENCE_VIDEO_ANALYZER_VERIFY_PASS`

Import `PROJETO_SM3_09B_VIDEO_STYLE_FEATURE_EXTRACTOR_v1.json`.

With the current corpus (`item_count = 0`) the valid workflow result is:
`SM3_09B_NO_ANALYZABLE_REFERENCE_VIDEOS`.

Once a video-like item has a local media ref, 09B writes one immutable feature observation into `33_REFERENCE_FEATURES` and marks the row in `32_REFERENCE_ITEMS` as `ANALYZED_V1`.

## Next bridge

The missing bridge is reference media acquisition. We will add a controlled ingestion path for media the user legitimately provides/downloads into Drive or the shared `/data/media` volume. We will not make the learning system depend on fragile Instagram scraping.
