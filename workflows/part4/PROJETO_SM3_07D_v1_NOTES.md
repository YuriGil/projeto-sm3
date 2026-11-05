# Projeto SM3 — 07D — Editor Workspace Bootstrap v1

## Objetivo

Transformar cada `EDIT_SESSION_READY` validada no 07C em um workspace de editor verificável, sem criar um segundo estado e sem alterar a planilha.

O estado canônico continua sendo:

`/data/media/production_state/edit_sessions/{project}/{content}/{edit_session}/current.json`

## Entregas

- Media Worker `2.4.0`.
- Contrato `SM3_EDITOR_WORKSPACE_V1`.
- Endpoint JSON do workspace.
- Endpoint seguro do preview vinculado à sessão.
- Tela-base do editor, ainda somente leitura.
- `state_etag` determinístico para concorrência otimista no 07E.
- Workflow `07D v1 VERIFIED STATE` com leitura do Sheets, verificação no Worker e segunda leitura real de `current.json`.
- Verificador PowerShell que baixa novamente os dois previews e recalcula o SHA-256 no Windows.

## Ordem de execução

Execute no PowerShell em `D:\MOLOTOV_SOCIAL_OS_RC7`:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\PROJETO_SM3_07D_v1_PACKAGE\PROJETO_SM3_07D_INSTALL_WORKER_2_4_0.ps1
```

O final esperado é:

```text
SM3_MEDIA_WORKER_2_4_0_INSTALL_PASS
```

Depois execute:

```powershell
$env:SM3_EDIT_SESSION_CARROSSEL_0004 = "<ID da sessão CARROSSEL_0004>"
$env:SM3_EDIT_SESSION_REEL_0006 = "<ID da sessão REEL_0006>"
.\PROJETO_SM3_07D_v1_PACKAGE\PROJETO_SM3_07D_VERIFY_WORKSPACES.ps1
```

O final esperado é:

```text
SM3_07D_EDITOR_WORKSPACES_PASS
```

O comando imprime `editor_url` para `CARROSSEL_0004` e `REEL_0006`. Abra as duas URLs no navegador para conferir a tela-base e os previews reais.

Por último:

1. Importe `PROJETO_SM3_07D_EDITOR_WORKSPACE_BOOTSTRAP_v1_VERIFIED_STATE.json` no n8n.
2. Abra o workflow importado.
3. Clique em **Execute workflow** uma vez.
4. Confirme `Workflow executed successfully`.
5. Abra o node `AUDIT — EDITOR WORKSPACES`; o esperado é `EDITOR_WORKSPACE_BOOTSTRAP_VERIFIED` e `verified_count: 2`.

## O que esta etapa não faz

- Não reseta nem recria as sessões do 07C.
- Não altera `04_CONTEUDOS`.
- Não sobrescreve originais, variantes ou previews.
- Não publica conteúdo.
- Não grava edição manual ainda.

O próximo contrato é o 07E: controles manuais e save idempotente de uma nova revisão imutável, exigindo `expected_revision`, `state_etag` e chave de idempotência.
