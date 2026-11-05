
# SM3 Media Worker 2.2.1 — Preview Source Kind Hardened

Fixes a production preview failure where M0085 was an MP4 but arrived from the
workflow declared as `image`.

Root cause:
- `03_MIDIAS.TIPO` can contain the localized value `VÍDEO`.
- 07B v1 compared the value only against the exact ASCII string `VIDEO`.
- M0085 was therefore marked `image`.
- The renderer applied the still-image ffmpeg input option `-loop 1` to an MP4.
- FFmpeg rejected the input with `Option loop not found`.

Hardening:
1. 07B v1.1 normalizes diacritics and also uses MIME type + extension.
2. Worker 2.2.1 independently detects the actual source type from extension,
   MIME and a guarded ffprobe fallback.
3. Spreadsheet metadata is no longer trusted as the sole authority for decoder behavior.
4. Preview manifests record declared kind, effective kind, and detection source.

No 05/06/07A rerun is required.
Rerun only 07B after rebuilding the worker and importing v1.1.
