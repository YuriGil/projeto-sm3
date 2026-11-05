# Projeto SM3 — Canonical Test Fixture v1

## Fixture
- Project: `TATTOO_0002`
- Reset contract: `SM3_TEST_FIXTURE_RESET_V1`
- Main reset mode: `FULL_PIPELINE`
- Snapshot sheet: `18_TEST_FIXTURE_SNAPSHOTS`

## Safety model
The reset is manual-only and hard-blocked to `TATTOO_0002`.
Every commit first appends a snapshot of all affected rows before changing state.
No Drive file is deleted, moved, renamed, or modified.
No spreadsheet row is deleted.

## Preserved media identity
The reset does not intentionally touch:
- ID_MIDIA
- ID_PROJETO
- ARQUIVO
- LINK_DRIVE
- TIPO
- SESSÃO
- DRIVE_FILE_ID
- PROJECT_FOLDER_ID
- PARENT_FOLDER_ID
- RELATIVE_PATH
- INGESTION_KEY
- STORAGE_STATUS
- FIRST_SEEN_AT
- LAST_SEEN_AT
- OFFLINE_AT
- TREE_DEPTH
- DISCOVERY_VERSION

## FULL_PIPELINE semantics
Media derived state is returned to:
- TRIAGEM = PENDENTE
- ANALYSIS_STATUS = QUEUED
- PROCESS_STATUS = READY

Analysis, structural vision, deterministic metadata, sampling, curation, and reliability outcome fields are cleared so Workflow 02 v9 can rebuild them.

Project curation and content-plan state is cleared.

Existing 04_CONTEUDOS rows for TATTOO_0002 are not deleted. They are archived with:
- PLAN_STATUS = TEST_ARCHIVED
- PIPELINE_STATE = TEST_ARCHIVED
- approval/routing state made non-current

This makes the next Content Plan create a fresh generation without destroying historical test evidence.

## Expected regression sequence
1. 00T-A dry run
2. 00T commit
3. 02 Triage v9
4. 03 Curation v6
5. 04 Content Plan v3
6. Human editorial decisions in Sheet
7. 05 Editorial Gate v3
8. 06 Editorial Routing v3
9. 07 Production only after pre-07 foundation is accepted

## Restore
00T-R restores the latest snapshot group for TATTOO_0002 and only the fields that 00T modifies.
