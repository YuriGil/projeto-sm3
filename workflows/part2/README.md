# Projeto SM3 — Hardening Pre-07 v1

Este pacote corrige a base ANTES de continuar o Workflow 07.

## O que foi endurecido

- nome canônico do sistema separado da marca: Projeto SM3 / marca MOLOTOV;
- state machine v2;
- gate editorial separado de aprovação final;
- scoring configurável via `14_OS_SCORING`;
- Structural Vision consumida por Curation e Content Plan;
- format viability usada como restrição operacional;
- worker v1.8:
  - Structural Vision downstream;
  - metadados técnicos;
  - SHA-256 persistível;
  - EXIF/container capture time;
  - contact sheet adaptativa por duração;
- preparação de recipes/capabilities em `16_RENDER_RECIPES`;
- metadata backfill sem IA;
- preparação para render versionado + QA + Final Approval.

## Ordem segura de instalação/teste

1. Atualizar o media-worker para v1.8.0.
2. Conferir `GET /health`.
3. Importar e executar `02C METADATA BACKFILL`.
4. Importar `02 TRIAGE v7` como candidato; ainda não apagar o PROD anterior.
5. Importar `03 CURATION v6`.
6. Importar `04 CONTENT PLAN v3`.
7. Importar `05 EDITORIAL GATE v3`.
8. Importar `06 EDITORIAL ROUTING v3`.
9. Testar cada workflow manualmente.
10. Só depois promover candidatos a PROD.

## Health esperado

```json
{
  "ok": true,
  "service": "sm3-media-worker",
  "version": "1.8.0",
  "structural_downstream": true,
  "contact_sheet_sampling": "ADAPTIVE_UNIFORM_V1",
  "metadata_contract": "SM3_MEDIA_METADATA_V2"
}
```

## Mudança semântica crítica

Workflow 05 NÃO é mais autorização para publicar.

Agora:

`AI_PLANNED -> EDITORIAL GATE -> PRODUCTION -> QA -> FINAL APPROVAL -> SCHEDULING/PUBLISH`

`APROVADO` no Editorial Gate significa apenas: **pode produzir**.

A publicação futura exigirá `FINAL_APPROVED`.

## Compatibilidade/migração

Os campos antigos de approval/routing foram preservados por compatibilidade, mas os workflows novos usam:

- `EDITORIAL_APPROVAL_STATUS`
- `EDITORIAL_COMMITTED_STATUS`
- `EDITORIAL_DECIDED_AT`
- `FINAL_APPROVAL_STATUS`
- `FINAL_COMMITTED_STATUS`
- `PIPELINE_STATE`
- `STATE_VERSION`

## Itens ainda propositalmente NÃO considerados prontos

Não avançar para um Workflow 07 definitivo antes de resolver/implementar:

1. ingestão recursiva real (substituir L0-L4);
2. retry/dead-letter por mídia;
3. scene-aware sampling (v1.8 melhora quantidade de frames, mas ainda é uniform sampling);
4. renderer recipe resolver + render IDs imutáveis;
5. QA técnico/visual;
6. Final Human Approval;
7. privacy/consent gate antes do publisher;
8. migração Postgres 16 -> 17;
9. perceptual fingerprint para duplicatas recomprimidas.

Isso é intencional: estes itens estão registrados para não voltarem a “passar despercebidos”.
