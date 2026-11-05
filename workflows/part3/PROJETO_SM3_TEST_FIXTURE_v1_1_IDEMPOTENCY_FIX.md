# SM3 Test Fixture v1.1 — Idempotency + Restore Safety

## Why v1.1 exists

A repeated execution of the v1 reset created a second snapshot after the fixture was already at baseline.
That did not corrupt the fixture, but it exposed two issues:

1. repeated reset should be a no-op;
2. restore must not choose a redundant baseline snapshot.

## v1.1 rules

### Reset
If all fixture media are already:
- TRIAGEM = PENDENTE
- ANALYSIS_STATUS = QUEUED
- PROCESS_STATUS = READY

and project curation/content-plan state is empty, and all old fixture contents are TEST_ARCHIVED,
the workflow returns:

SM3_TEST_FIXTURE_ALREADY_RESET

No new snapshot and no sheet write is performed.

### Restore
Restore ignores snapshot groups marked REDUNDANT_BASELINE and independently verifies that a snapshot is meaningful.
A meaningful snapshot contains actual derived state before reset.

This protects rollback even after accidental repeated clicks.
