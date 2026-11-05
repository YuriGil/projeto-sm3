# Projeto SM3 — 07C Variant Selection + Editor Session v1

## Resultado arquitetural

O 07C não escolhe uma variante no lugar do usuário. Ele consome somente uma decisão humana explícita em `04_CONTEUDOS`, cria ou reutiliza uma sessão de edição persistente e só confirma a mudança na planilha depois de reler o estado do Worker.

## Pré-requisito

Instalar o Media Worker 2.3.0 incluído neste pacote. O workflow interrompe a execução antes de qualquer gravação se `/health` não confirmar:

- `version = 2.3.0`
- `production_edit_contract = SM3_PRODUCTION_EDIT_V1`
- `edit_session_start_idempotent = true`
- `edit_session_contract = SM3_EDIT_SESSION_V1`

## Como registrar a escolha humana

Para cada conteúdo escolhido em `04_CONTEUDOS`, alterar somente:

| Coluna | Valor |
|---|---|
| `SELECTED_VARIANT_ID` | `V01`, `V02` ou `V03` |
| `VARIANT_REVIEW_STATUS` | `SELECTED` |

Manter `EDIT_SESSION_ID` vazio e `EDIT_SESSION_STATUS` como `NOT_STARTED`. O 07C aceita `REVISION_MODE` vazio, `UNDECIDED` ou `VARIANT_SELECTION` e normaliza o valor persistido para `VARIANT_SELECTION`.

## Commit verificado

Para cada seleção válida, o workflow executa:

1. valida o contrato do Worker;
2. valida o estado de revisão da planilha sem aceitar seleção parcial;
3. chama `POST /production/edit-session/start` com `force_new=false`;
4. relê a sessão com `GET /production/edit-session/...`;
5. compara IDs, contratos, revisão e hash do preview;
6. atualiza `04_CONTEUDOS`;
7. relê a planilha e compara todos os campos gravados.

Estado final esperado:

| Campo | Valor |
|---|---|
| `VARIANT_REVIEW_STATUS` | `OPEN_EDITOR` |
| `REVISION_MODE` | `VARIANT_SELECTION` |
| `EDIT_SESSION_STATUS` | `OPEN` (ou o estado persistido reutilizado) |
| `EDIT_RECIPE_VERSION` | `SM3_EDIT_RECIPE_V1` |
| `PIPELINE_STATE` | `EDIT_SESSION_READY` |
| `STATE_VERSION` | `SM3_STATE_V5` |

Uma nova execução com a mesma seleção reutiliza o mesmo `EDIT_SESSION_ID`. Preview ausente, contrato divergente, hash adulterado ou estado parcial bloqueiam o lote antes do commit.

