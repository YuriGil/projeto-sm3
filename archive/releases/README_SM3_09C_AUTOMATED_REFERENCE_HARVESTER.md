# Projeto SM3 — 09C Automated Reference Harvester

## Objetivo

Remover o cadastro manual de Reel por Reel do fluxo de produção. O usuário controla os perfis/professores em `31_REFERENCE_PROFILES`; o 09C consulta competitors do Metricool, coleta Reels/métricas, calcula desempenho **dentro do próprio criador** e promove apenas candidatos de alto sinal.

## Novos controles em 31_REFERENCE_PROFILES

- `AUTO_HARVEST`
- `HARVEST_LOOKBACK_DAYS` (padrão 30)
- `HARVEST_PROMOTE_PERCENTILE` (padrão 85)
- `HARVEST_MAX_ITEMS_PER_RUN` (padrão 5)
- `HARVEST_STATUS`
- `LAST_HARVEST_AT`

`ACTIVE` permanece separado: um perfil pode ser coletado enquanto ainda está em curadoria, mas não influencia priors enquanto estiver inativo.

## Novas abas

- `37_REFERENCE_HARVEST_CANDIDATES`: métricas, percentis, score, classificação e promoção por Reel.
- `38_REFERENCE_HARVEST_RUNS`: auditoria de cada execução.

## Scoring

Percentis são calculados por criador, não entre contas de tamanhos diferentes. Pesos: engagement 40%, interactions 35%, comments 15%, likes 10%. Classificação: HIGH_VALUE >= 90; CANDIDATE >= 70; NORMAL >= 35; LOW_SIGNAL < 35.

## Metricool MCP / n8n

Nos dois nodes `METRICOOL MCP`, selecione/crie uma credencial Header Auth com `X-Mc-Auth` e a chave Metricool. Endpoint: `https://ai.metricool.com/mcp`. Tools usadas: `get_network_competitors` e `get_network_competitors_posts`.

Perfis não configurados como competitors no Metricool ficam `WAITING_METRICOOL_COMPETITOR`; isso não quebra o run.

## Instalação

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09C_INSTALL_WORKER_2_17_0.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09C_VERIFICAR_HARVESTER.ps1"
```

Importe `PROJETO_SM3_09C_AUTOMATED_REFERENCE_HARVESTER_v1.json`, configure a credencial Metricool uma vez, teste manualmente e só depois publique. O schedule diário é 08:15 America/Sao_Paulo.

O pacote também inclui versões CONTRACT_COMPAT de 09A.2, 09A.4 e 09B para evitar que workflows válidos rejeitem Workers novos apenas pelo número exato da versão.
