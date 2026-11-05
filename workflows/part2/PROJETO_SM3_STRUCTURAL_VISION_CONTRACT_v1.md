# Projeto SM3 — Structural Vision Contract v1

## Objetivo

Esta camada faz o SM3 entender **onde a tattoo está no corpo**, **como ela está orientada**, **qual é o assunto/estilo visual** e **quais formatos/crops são realmente adequados** antes de editar.

Ela não substitui a curadoria. Ela adiciona geometria e contexto editorial à mídia.

## Coordenadas

Todas as coordenadas usam valores normalizados `0..1`, com origem no canto superior esquerdo:

- `x=0, y=0` = canto superior esquerdo
- `x=1, y=1` = canto inferior direito
- `w` e `h` também são frações do frame

Para foto:
- `GEOMETRY_MODE = IMAGE_EXACT`
- coordenadas referem-se à imagem após correção EXIF.

Para vídeo:
- `GEOMETRY_MODE = VIDEO_CONTACT_SHEET_ESTIMATE`
- o modelo vê vários frames com timestamps e estima uma geometria recorrente do frame original.
- baixa estabilidade de câmera deve reduzir `rect_reliability`.

## Novas colunas em 03_MIDIAS

- `STRUCTURAL_ANALYSIS_VERSION`
- `GEOMETRY_MODE`
- `BODY_REGION`
- `BODY_SUBREGION`
- `VIEW_ANGLE`
- `BODY_POSE`
- `TATTOO_ORIENTATION`
- `TATTOO_STYLE_TAGS`
- `TATTOO_SUBJECT_PRIMARY`
- `TATTOO_SUBJECT_TAGS`
- `TATTOO_STAGE_STRUCTURAL`
- `TATTOO_COVERAGE`
- `COMPOSITION_SHAPE`
- `FOCAL_DESCRIPTION`
- `FOCUS_POINT_NORM`
- `TATTOO_BBOX_NORM`
- `CROP_GUIDANCE_JSON`
- `FORMAT_FIT_JSON`
- `BEST_FORMATS`
- `STRUCTURAL_CONFIDENCE`
- `STRUCTURAL_NOTES`

## Colunas JSON

`FOCUS_POINT_NORM`
```json
{"x":0.50,"y":0.46}
```

`TATTOO_BBOX_NORM`
```json
{"x":0.22,"y":0.08,"w":0.56,"h":0.82,"reliability":92}
```

`CROP_GUIDANCE_JSON`
```json
{
  "reel_9x16": {
    "viability_score": 95,
    "strategy": "USE_FULL_FRAME",
    "anchor": "CENTER",
    "rect_norm": {"x":0.0,"y":0.0,"w":1.0,"h":1.0},
    "rect_reliability": 96,
    "rationale": "Composição vertical acompanha o fluxo anatômico."
  },
  "square_1x1": {
    "viability_score": 68,
    "strategy": "PAN_SCAN",
    "anchor": "DYNAMIC",
    "rect_norm": {"x":0.17,"y":0.18,"w":0.66,"h":0.66},
    "rect_reliability": 72,
    "rationale": "Um crop fixo quadrado perderia parte do desenho; movimento interno é preferível."
  }
}
```

`FORMAT_FIT_JSON` é uma versão compacta para decisão editorial:
```json
{
  "reel_9x16": {
    "viability_score": 95,
    "strategy": "USE_FULL_FRAME",
    "anchor": "CENTER",
    "rect_reliability": 96,
    "rationale": "..."
  }
}
```

## Estratégias de crop

- `USE_FULL_FRAME`: o enquadramento já funciona.
- `SMART_CROP`: recorte estático seguro.
- `CONTAIN_BLUR`: preservar o frame inteiro e completar canvas.
- `PAN_SCAN`: usar movimento interno em vez de mutilar composição.
- `TRACK_SUBJECT`: vídeo exige acompanhamento dinâmico.
- `NOT_RECOMMENDED`: não forçar esse formato.

## Arquivos deste pacote

1. `PROJETO_SM3_STRUCTURAL_VISION_SCHEMA_v1.json`
   - contrato JSON exato.

2. `PROJETO_SM3_MEDIA_WORKER_v1_7_STRUCTURAL_VISION_PATCH.zip`
   - expande `/analyze-path` sem criar uma segunda chamada de IA para mídias novas.
   - versão esperada no `/health`: `1.7.0`.

3. `PROJETO_SM3_02_TRIAGE_v6_STRUCTURAL_VISION_REAL_WRITE.json`
   - substituto futuro do Workflow 02 PROD.
   - mídias novas já recebem triagem + anatomia + tema + geometria + recomendações de formato numa única análise.

4. `PROJETO_SM3_02B_STRUCTURAL_BACKFILL_v1_PRODUCTION_READY.json`
   - backfill controlado.
   - procura apenas mídias usadas por conteúdo atualmente `APROVADO + PRODUCTION READY`.
   - no estado atual deve mirar o material do `REEL_0005`, sem reanalisar o acervo inteiro.

## Ordem recomendada de teste

1. Atualizar worker para v1.7.
2. Confirmar `/health`.
3. Importar e executar **02B STRUCTURAL BACKFILL**.
4. Conferir as novas colunas de `M0085`.
5. Só depois substituir o Workflow 02 atual pelo **v6 STRUCTURAL VISION**.
6. Em seguida atualizar Workflow 07 para escolher receita de render a partir de `CROP_GUIDANCE_JSON` / `FORMAT_FIT_JSON`.

## Regra arquitetural

O renderizador não deve decidir sozinho que todo material é 9:16.

A decisão futura será:

`anatomia + tattoo + geometria + formato pedido + viabilidade -> receita de render`

e não:

`formato pedido -> crop central`.
