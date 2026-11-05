# Projeto SM3 — Scene-Aware Sampling Contract v2

## Canonical sampler
`ADAPTIVE_SCENE_V2`

## Candidate sources
- adaptive uniform timestamps (coverage)
- FFmpeg scene-change timestamps
- post-cut frames (+0.18 s)
- boundary frames near start/end

## Quality signals
- sharpness / edge variance
- exposure / clipping
- temporal visual novelty (histogram difference)
- FFmpeg scene score

## Selection
Coverage buckets choose a strong frame in every temporal region, then quality-ranked
frames fill remaining slots with a temporal-distance guard. This prevents a high-quality
cluster from replacing the rest of the video.

## Duration targets
- <=15 s: 6
- <=45 s: 10
- <=120 s: 14
- >120 s: 18

## Fail-safe
If scene detection fails, uniform candidates remain available. The result reports
`fallback_used=true` and preserves the v2 schema. No vision call depends on a successful
scene-detection pass.

## Explicit non-goals
This is not semantic subject tracking. Tracking remains a Production/Render capability.
Scene-aware sampling improves analysis coverage; it does not decide crops or follow the tattoo.
