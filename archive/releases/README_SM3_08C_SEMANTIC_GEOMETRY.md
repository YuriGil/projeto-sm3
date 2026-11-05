# Projeto SM3 — 08C Semantic Geometry V1

## Objetivo

08C cria a camada factual de geometria visual que fica **abaixo** dos perfis de direção.
Perfis como `DP_SLOW_MELODIC` e `DP_FAST_ENERGETIC` podem tomar decisões editoriais diferentes,
mas não podem discordar sobre onde está a tatuagem, qual área é protegida, qual é o eixo do assunto
ou onde um overlay é proibido.

Essa separação evita contaminar o aprendizado: estilo é contextual; geometria do material é foundation.

## Contratos

- Worker: `2.11.0`
- Renderer: `2.8.0` (inalterado)
- Semantic Geometry: `SM3_SEMANTIC_GEOMETRY_V1`
- Analyzer: `SM3_GEOMETRY_ANALYZER_V1`
- Direction Profile: `SM3_DIRECTION_PROFILE_V1`
- Learning Router: `SM3_LEARNING_ROUTER_V1`

## O que a geometria produz

Para cada mídia, vinculado ao `CONTENT_HASH` original:

- bbox da tatuagem;
- região protegida com halo determinístico;
- ponto focal;
- eixo anatômico;
- eixo visual da tatuagem;
- sugestão conservadora de correção de rotação (máx. ±12°);
- espaços negativos;
- regiões candidatas para overlays;
- regiões de overlay realmente aceitas após verificação do Worker;
- crop policy por 9:16, 4:5 e 1:1;
- sinalização de vídeo que exige tracking/pan-scan;
- cross-check contra `SM3_STRUCTURAL_V2` já existente;
- `VERIFIED` ou `REVIEW_REQUIRED`;
- hash imutável do registro.

## Regra central

`direction_profile_may_not_override_protected_regions = true`

Ou seja: um perfil rápido pode aumentar a frequência de cortes e movimento, mas não ganha permissão
para cortar ou cobrir a tatuagem. Um perfil lento pode preservar mais espaço negativo, mas usa a mesma
geometria factual.

## Persistência

Os registros ficam em:

`/data/media/production_state/semantic_geometry/<project>/<media>/<source_hash>/SM3_GEOMETRY_ANALYZER_V1.json`

O registro é imutável, hasheado e idempotente. Se o mesmo `source_content_hash` for apresentado com um
asset de análise diferente sob a mesma versão do analyzer, o Worker bloqueia em vez de substituir silenciosamente.

## CONTROLE_MOLOTOV

Foi criada a aba `21_SEMANTIC_GEOMETRY` como espelho operacional. A autoridade continua sendo o registro
imutável do Worker.

## Fixture 08C

O workflow incluído analisa somente a fixture canônica atual:

- `CARROSSEL_0004`
- `M0083`
- `M0085`
- `M0086`

Ele usa os proxies/contact sheets já persistidos (`PROXY_STATUS=LOCAL_READY`) e não baixa novamente os originais.
Isso mantém o teste rápido e não altera os arquivos-fonte.

## Ordem de execução

1. `SM3_08C_INSTALL_WORKER_2_11_0.ps1`
2. Importar `PROJETO_SM3_08C_SEMANTIC_GEOMETRY_v1_CURRENT_FIXTURE.json` no n8n.
3. Executar o workflow uma vez.
4. `SM3_08C_VERIFICAR_GEOMETRIA.ps1`

08C não cria REV5 e não altera o perfil ativo. REV4 continua sendo o baseline visual negativo.

## Próxima etapa

08D deverá consumir somente geometria `consumable=true` para implementar composição/crop real:
Smart Crop, rotação conservadora, proteção de assunto e posicionamento de identidade por espaço negativo.
