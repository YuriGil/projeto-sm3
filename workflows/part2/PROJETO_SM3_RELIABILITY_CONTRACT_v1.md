# Projeto SM3 — Reliability Contract v1

## Goal

Transient failures should heal automatically. Persistent failures must become visible and durable without corrupting pipeline state.

## Canonical rules

- Network/Google calls: retry up to 3 times, 5000 ms between attempts.
- Local media processing (FFmpeg/ffprobe): 2 attempts.
- Vision/API analysis: 3 attempts.
- Dead-letter primary storage: `/data/media/system/dead_letter/events.jsonl`.
- Google Sheet `17_OS_FAILURES` is a best-effort mirror, not the authority during a Sheets outage.
- Automatic replay is disabled in v1.
- Ingestion is **fail-closed**: after retries, a discovery/registry/storage error stops the run. Partial discovery never becomes authoritative.
- Per-media workflows (02/02B/02C) will use `onError: continueErrorOutput` and route only failed media to dead-letter so healthy media can continue.

## Media operational states

`READY -> PROCESSING -> SUCCESS | RETRY | DEAD_LETTER`

`DEAD_LETTER` requires explicit replay/review in v1.

## Why ingestion is different

Ingestion and storage rotation establish what currently exists in the source tree. Continuing after a terminal read failure could falsely mark media or projects OFFLINE. For this reason Workflow 01 retries transient failures but stops on terminal failure.

## n8n implementation reference

Use node-level:

- `retryOnFail: true`
- `maxTries: 3`
- `waitBetweenTries: 5000`

For per-media fallible nodes in later workflows:

- `onError: "continueErrorOutput"`
- output 0 -> success path
- output 1 -> dead-letter handler
