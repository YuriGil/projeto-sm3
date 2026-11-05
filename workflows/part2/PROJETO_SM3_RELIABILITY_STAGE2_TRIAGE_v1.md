# Projeto SM3 — Reliability Stage 2: Per-media isolation

## Validated prerequisites
- media-worker 1.9.0
- SM3_RELIABILITY_V1 local JSONL dead-letter
- Workflow 01 v19 fail-closed ingestion

## Workflow 02 policy
Queue-level Google Sheets read remains fail-closed.

Once the queue exists, each media item becomes an independent failure domain.

Fallible stages:
1. Drive download: 3 attempts, 5 s wait.
2. Local temp write: 2 attempts, 1 s wait.
3. Media-worker process: 2 attempts, 3 s wait.
4. Vision analysis: 3 attempts, 5 s wait.
5. Vision response audit: 1 attempt; deterministic validation is not retried.
6. Analysis contract build: 1 attempt; deterministic validation is not retried.
7. Google Sheets analysis write: 3 attempts, 5 s wait.

Terminal item failures:
- do not stop healthy sibling media;
- emit a common SM3_RELIABILITY_V1 event;
- try LOCAL_JSONL and 17_OS_FAILURES in parallel;
- mark the media PROCESS_STATUS=DEAD_LETTER and ANALYSIS_STATUS=DEAD_LETTER if Sheets is available;
- require explicit replay in v1.

A Sheets outage during the failure-status write cannot erase the local dead-letter record. A media-worker outage can still be mirrored to 17_OS_FAILURES when Google is available. n8n execution history is the tertiary fallback when both external sinks are unavailable.
