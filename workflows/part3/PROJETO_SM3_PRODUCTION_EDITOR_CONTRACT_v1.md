# Projeto SM3 — Production / Editor Contract v1

## Objective
Production no longer outputs a single destructive render. It creates editable AI variants, lets the user select or modify a proposal, then renders a final artifact only after that review.

## Canonical flow

Editorial Gate -> Routing -> Production Variant Planning -> Variant Review -> Manual/AI Revision -> Final Render -> QA -> Final Human Approval -> Publish

## Human control

`APROVADO` means the content idea may enter production.
`REVISAR` means the content enters the editor/review workspace. Notes are optional.
`DESCARTADO` closes the content.

A revision note is required only when the user explicitly chooses `AI_REVISION` and expects the AI to change the recipe according to natural-language instructions.

## Revision modes

- UNDECIDED
- VARIANT_SELECTION
- AI_REVISION
- MANUAL_EDITOR
- REGENERATE_VARIANTS

## Non-destructive model

Original media is never overwritten.

The worker creates:

- immutable AI variant set
- selected variant id
- versioned edit session
- immutable recipe revisions
- final render only after the edit/review stage

## Spreadsheet control columns

Added to `04_CONTEUDOS` after BT:

- PRODUCTION_SESSION_ID
- VARIANT_SET_ID
- VARIANT_COUNT
- VARIANT_REVIEW_STATUS
- SELECTED_VARIANT_ID
- REVISION_MODE
- EDIT_SESSION_ID
- EDIT_SESSION_STATUS
- EDIT_RECIPE_VERSION
- FINAL_RENDER_ID
- FINAL_RENDER_STATUS
- PRODUCTION_CONTRACT_VERSION

The spreadsheet stores control/state only. Detailed timelines and edit recipes live in worker persistent storage.

## Worker persistence

`/data/media/production_state/variant_sets/...`

`/data/media/production_state/edit_sessions/...`

## Worker API foundation

- POST `/production/plan-variants`
- GET `/production/variant-set/{project_id}/{content_id}/{variant_set_id}`
- POST `/production/edit-session/start`
- POST `/production/edit-session/save`
- GET `/production/edit-session/{project_id}/{content_id}/{edit_session_id}`

## Edit recipe scope

Recipes are designed to grow without breaking the contract. They already model:

- media order
- timeline segments
- framing strategy
- focus point
- zoom intent
- text overlays
- identity density
- logo/stamp/texture/frame intent
- safe margins
- color treatment
- transition style
- audio strategy
- manual-edit intent

Future editor UI can manipulate the same recipe rather than inventing a second state model.

## Safety invariants

- structural/anatomical metadata constrains framing
- preserve_subject must remain true
- blind center-crop is not accepted as a universal strategy
- tattoo/body geometry must remain visually faithful
- final approval remains human-only
- publishing is impossible from an AI variant alone
