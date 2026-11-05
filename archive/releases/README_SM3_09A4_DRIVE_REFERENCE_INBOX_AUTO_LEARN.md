# SM3 09A.4 — Drive Reference Inbox Auto-Learn

Google Drive inbox:
`SM3_REFERENCE_INBOX`

Folder ID:
`1WRP5VrSRh54RVjf-zhTMqz4HJVqMVQud`

## Minimal human flow

1. Register the Reel/video in `32_REFERENCE_ITEMS` with 09A.2.
2. Upload the actual video file to `SM3_REFERENCE_INBOX`.
3. Best filename form:

`RI_<32hex>__qualquer_nome.mp4`

The matcher also tries:
- PLATFORM_ITEM_ID contained in the filename;
- PROFILE_HANDLE contained in the filename, only when exactly one pending video item exists for that handle.

Ambiguous files are left untouched and return:
`SM3_09A4_DRIVE_FILE_LEFT_UNMATCHED`

## Automated chain

Drive file created
→ match RI
→ download
→ stream to Worker 2.16.2
→ canonical acquisition + SHA-256 verify
→ update 32_REFERENCE_ITEMS
→ 09B video analysis
→ write 33_REFERENCE_FEATURES
→ mark ANALYZED_V1

No Instagram scraping is required.

## Activation

Import:
`PROJETO_SM3_09A4_DRIVE_REFERENCE_INBOX_AUTO_LEARN_v1.json`

First test it manually with one reference item/video.
After validation, Publish the workflow so the Google Drive Trigger can watch the folder.

## Compatibility

After upgrading to Worker 2.16.2, use:
`PROJETO_SM3_09B_VIDEO_STYLE_FEATURE_EXTRACTOR_v1_1_WORKER_2_16_2.json`

because the original 09B v1 intentionally asserted exactly Worker 2.16.0.
