# Projeto SM3 — Reliability for 02B/02C backfills

## Purpose
Apply the validated SM3_RELIABILITY_V1 pattern to the manual backfills without redesigning their business logic.

## Important semantic rule
Backfill success does **not** blindly set the global PROCESS_STATUS to SUCCESS.
A backfill must not erase a dead-letter created by another processing stage.

Terminal backfill failure:
- retries the fallible node according to policy;
- isolates the failing media item;
- emits one canonical event;
- writes to LOCAL_JSONL and, best effort, 17_OS_FAILURES;
- marks PROCESS_STATUS=DEAD_LETTER in 03_MIDIAS if Sheets is available;
- requires explicit replay/review before automatic processing resumes.

## 02B Structural Backfill
- Drive download: 3 tries
- local temp write: 2 tries
- worker process: 2 tries
- Structural Vision: 3 tries
- deterministic structural audit/build: 1 try
- Sheets write: 3 tries

## 02C Metadata Backfill
- Drive download: 3 tries
- local temp write: 2 tries
- worker process: 2 tries
- deterministic metadata contract build: 1 try
- Sheets write: 3 tries

## Queue protection
Both queues skip media whose PROCESS_STATUS is already DEAD_LETTER.
Replay will be explicit in a later workflow.
