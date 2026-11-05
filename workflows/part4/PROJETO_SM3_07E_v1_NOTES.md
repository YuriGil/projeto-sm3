# Projeto SM3 — 07E — Edição manual e save versionado

O 07D foi verificado para `CARROSSEL_0004` e `REEL_0006`. Seus IDs de sessão e previews permanecem válidos.

## O que muda

- Worker 2.5.0 ativa controles manuais no mesmo endereço de editor do 07D.
- Save `SM3_EDIT_SAVE_V1` requer revisão esperada, hash do estado, chave de idempotência e descrição da alteração.
- `revision_0002.json`, `revision_0003.json` etc. são imutáveis; o Worker confirma a gravação relendo o estado e a revisão.
- A receita conserva a variante base, as mídias originais e a obrigação de preservar a tattoo no enquadramento.
- A porta 8090 fica ligada ao `127.0.0.1` do Windows. O n8n continua acessando `media-worker:8090` pela rede interna do Docker.
- Workflow 07E reconcilia o controle em `04_CONTEUDOS`: após um save, marca `EDIT_SESSION_STATUS=SAVED` e `REVISION_MODE=MANUAL_EDIT`, relê a planilha e exige confirmação.

## Instalação

Extraia o ZIP na raiz `D:\MOLOTOV_SOCIAL_OS_RC7` (a pasta criada deve se chamar `PROJETO_SM3_07E_v1_PACKAGE`). Execute no PowerShell:

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& .\PROJETO_SM3_07E_v1_PACKAGE\PROJETO_SM3_07E_INSTALL_WORKER_2_5_0.ps1
```

Resultado esperado: `SM3_MEDIA_WORKER_2_5_0_INSTALL_PASS`. O instalador salva cópias anteriores de `worker_service.py` e `docker-compose.worker.yml` em `sm3_backups`.

Confirme que os dois workspaces antigos continuam acessíveis e com preview íntegro:

```powershell
$env:SM3_EDIT_SESSION_CARROSSEL_0004 = "<ID da sessão CARROSSEL_0004>"
$env:SM3_EDIT_SESSION_REEL_0006 = "<ID da sessão REEL_0006>"
& .\PROJETO_SM3_07E_v1_PACKAGE\PROJETO_SM3_07E_VERIFY_WORKSPACES.ps1
```

Resultado esperado: `SM3_07E_EDITOR_WORKSPACES_PASS`.

## Teste de edição real

Abra uma das URLs `editor_url` que o verificador imprime. Ajuste um campo simples, como foco X ou texto, preencha **Descrição da edição** e clique **Salvar revisão**. A tela deve mostrar `Revisão 2 salva e relida do disco` para a primeira edição.

O vídeo na tela é o preview imutável da variante V01. As alterações da receita só aparecerão em vídeo quando o renderizador de revisões for implementado. Não use o preview como publicação final.

## Reconciliação na planilha

Importe `PROJETO_SM3_07E_MANUAL_EDIT_STATE_v1_VERIFIED_COMMIT.json` no n8n e execute depois de salvar uma edição. O node `ASSERT — MANUAL EDIT COMMITTED` deve retornar `MANUAL_EDIT_CONTROL_COMMITTED` e `committed_count` igual ao número de conteúdos recém-salvos. Execute de novo: o fluxo deve reconhecer `ALREADY_RECONCILED` sem criar uma segunda revisão.

O workflow 07D fixava a versão 2.4.0 na verificação inicial, por isso seu registro de execução anterior é a evidência da etapa 07D. Para o Worker 2.5.0, use o workflow 07E.

## Próxima etapa

Renderização de preview da receita editada, revisão por IA com pedido textual explícito, QA, render final e aprovação humana.
