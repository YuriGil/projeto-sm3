# SM3 09A.4 — Verifier R2

The original 09A.4 verifier correctly passed the Worker health/contract checks,
but then tried to read:

`$s.media_acquisition_count`

from `/production/reference-corpus/summary`.

That property is not part of the summary contract.

The canonical media acquisition count is exposed by:

`GET /production/reference-corpus/reference-media`

R2 uses that endpoint, matching the already validated 09A.3 verifier behavior.

No Worker reinstall and no workflow change are required.
