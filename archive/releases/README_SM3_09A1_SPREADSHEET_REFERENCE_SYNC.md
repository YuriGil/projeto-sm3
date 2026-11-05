# Projeto SM3 — 09A.1 — Spreadsheet-Driven Reference Profile Sync

## Objetivo

Transformar `31_REFERENCE_PROFILES` na interface humana principal para administrar os perfis que ensinam o SM3.

Você pode alterar suas preferências com o tempo sem apagar o passado. O sistema mantém:

- **estado atual mutável** em `31_REFERENCE_PROFILES` + Worker;
- **histórico imutável** em `36_REFERENCE_PROFILE_HISTORY` + Worker;
- `PREFERENCE_VERSION` crescente;
- SHA-256 por estado/snapshot;
- `ACTIVE` para ligar/desligar influência sem excluir conhecimento;
- `HUMAN_PRIORITY` de 0 a 100.

## Campos que você edita em 31_REFERENCE_PROFILES

- NETWORK
- HANDLE
- PROFILE_URL
- LABEL
- USER_INTEREST
- STYLE_NOTES
- DISLIKE_NOTES
- SOURCE (opcional; vazio = HUMAN)
- ACTIVE
- NOTES
- HUMAN_PRIORITY

Os campos técnicos são mantidos pelo SM3.

A planilha já recebeu validações, notas de cabeçalho e diferenciação visual: áreas humanas em tom claro e áreas técnicas em cinza.

## Worker 2.15.1

Novos contratos:

- `SM3_REFERENCE_PROFILE_SYNC_V1`
- `SM3_REFERENCE_PROFILE_HISTORY_V1`

O perfil corrente pode mudar. O histórico não é sobrescrito.

Exemplo:

```text
@criador_x / versão 1
Gosto: ritmo e cor
Prioridade: 90

@criador_x / versão 2
Gosto: enquadramento; ritmo recente não me interessa
Prioridade: 60
```

As duas versões continuam auditáveis.

## Instalação

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09A1_INSTALL_WORKER_2_15_1.ps1"
```

Esperado:

`SM3_09A1_SPREADSHEET_REFERENCE_SYNC_INSTALL_PASS`

Depois:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09A1_VERIFICAR_SYNC.ps1"
```

Esperado:

`SM3_09A1_SPREADSHEET_REFERENCE_SYNC_VERIFY_PASS`

## n8n

Importe:

`PROJETO_SM3_09A1_SPREADSHEET_REFERENCE_PROFILE_SYNC_v1.json`

Nome:

`PROJETO SM3 — 09A.1 — SPREADSHEET REFERENCE PROFILE SYNC — v1`

Durante a curadoria, você pode preencher várias linhas. Quando quiser sincronizar, execute o workflow uma vez.

### ACTIVE

O checkbox `ACTIVE` é deliberado: enquanto você ainda está apenas coletando nomes, pode deixá-lo desmarcado. O perfil será preservado, mas não deve influenciar priors ativos até você marcá-lo.

### Mudanças futuras

Se editar um perfil já sincronizado, o workflow:

1. lê a versão corrente;
2. envia a nova preferência com `expected_preference_version`;
3. o Worker rejeita concorrência/stale version;
4. se mudou, incrementa `PREFERENCE_VERSION`;
5. cria snapshot imutável no histórico;
6. atualiza os campos técnicos na linha atual.

Se nada mudou, retorna `UNCHANGED` e não cria histórico duplicado.

## Por que o workflow é manual nesta versão

Primeiro vamos validar o ciclo com seus primeiros perfis reais. Depois podemos ativar um Schedule Trigger (por exemplo 15 min) sem alterar o contrato. Isso evita automação silenciosa antes de termos dados reais de curadoria.

## Próximo passo

Assim que existirem alguns perfis sincronizados, o 09B poderá coletar itens e analisar Reels reais. O corpus continuará aceitando alterações de gosto e evolução dos próprios criadores.
