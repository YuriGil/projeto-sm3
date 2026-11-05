# SM3 09C.1 — Provider Abstraction + Meta Primary + Scraper Foundation

## Novo desenho

A coleta deixa de depender de um fornecedor específico. Todos os coletores escrevem o mesmo contrato:

`SM3_REFERENCE_OBSERVATION_V1`

Providers registrados:
- HUMAN_SHARE — prioridade 5 / confiança 1.00
- META_GRAPH — prioridade 10 / confiança 0.95
- METRICOOL_MCP — prioridade 20 / confiança 0.85 / opcional e desabilitado por padrão
- SCRAPER_PUBLIC — prioridade 30 / confiança 0.60
- MANUAL — prioridade 40 / confiança 0.75

O Worker preserva todas as observações imutáveis e cria uma visão de consenso por conteúdo. Conflitos entre providers não são apagados: entram em `CONFLICT_FIELDS`.

## Redundância implementada

- Circuit breaker por provider.
- Cooldown progressivo para falhas e rate limit.
- Persistência de estado de provider.
- Dedupe e idempotência das observações.
- Proveniência por provider.
- Consenso sem apagar divergências.
- Provider agnostic harvester: o scorer consome observações normalizadas, não Metricool.
- Dead-letter existente do Worker continua preservado.
- Workflows antigos podem continuar como fallback/manual.

## Meta Graph

Workflow: `PROJETO_SM3_09C1_META_REFERENCE_COLLECTOR_v1.json`

A API oficial Meta é o provider primário para contas Instagram profissionais Business/Creator. O workflow usa Business Discovery e Graph API v26.0.

Configuração única no n8n:
1. No node `CONFIG — META GRAPH (EDIT ONCE)`, informe o seu `ig_user_id`.
2. No node `META GRAPH — BUSINESS DISCOVERY`, configure Header Auth com `Authorization: Bearer <PAGE_ACCESS_TOKEN>`.
3. Não salve tokens na planilha.

## Scraper público — fundação

Workflow: `PROJETO_SM3_09C1_PUBLIC_SCRAPER_FALLBACK_v1.json`

Contrato: `SM3_REFERENCE_PUBLIC_SCRAPER_V1`

Esta versão já implementa:
- allowlist de host;
- HTTPS obrigatório;
- máximo de 2 MB de HTML;
- redirects revalidados;
- rate-limit/circuit breaker;
- snapshots SHA-256;
- extração OpenGraph/meta;
- fila auditável em `41_REFERENCE_SCRAPER_QUEUE`.

Deliberadamente NÃO implementa:
- automação de login;
- cookies privados;
- CAPTCHA bypass;
- evasão de anti-bot;
- stealth fingerprinting.

O contrato fica estável para no futuro trocar o backend estático por browser/Playwright, sem alterar o restante do SM3.

## Planilha

`31_REFERENCE_PROFILES` ganhou:
- PROVIDER_MODE
- ALLOW_PUBLIC_SCRAPING
- META_ELIGIBILITY
- PROVIDER_LAST_USED
- PROVIDER_STATUS
- PROVIDER_LAST_SUCCESS_AT
- PROVIDER_LAST_ERROR_AT
- PROVIDER_LAST_ERROR

Novas abas:
- `39_REFERENCE_PROVIDER_STATE`
- `40_REFERENCE_OBSERVATIONS`
- `41_REFERENCE_SCRAPER_QUEUE`

## Instalação

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09C1_INSTALL_WORKER_2_18_0.ps1"
```

Depois:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09C1_VERIFICAR_PROVIDER_ABSTRACTION.ps1"
```

Esperado: `SM3_09C1_PROVIDER_ABSTRACTION_VERIFY_PASS`.
