# Projeto SM3 — Media Worker 2.4.0

Esta versão implementa o contrato estrutural do 07D: o Editor Workspace é uma projeção verificada da sessão persistida, não um segundo estado concorrente.

## Contrato novo

- `GET /production/editor-workspace/{project_id}/{content_id}/{edit_session_id}` retorna `SM3_EDITOR_WORKSPACE_V1`.
- `GET .../base-preview` entrega somente o preview vinculado à sessão; não aceita caminho arbitrário.
- `GET /production/editor/{project_id}/{content_id}/{edit_session_id}` abre a primeira tela do editor, ainda somente leitura.
- Antes de responder, o Worker relê `current.json`, o conjunto imutável de variantes e o manifesto de previews.
- O SHA-256 real do preview precisa coincidir com o manifesto e com `selection_evidence` da sessão.
- `state_etag` é determinístico para a revisão atual e será o token de concorrência otimista do save manual no 07E.
- O workspace falha fechado diante de estado parcial, contrato divergente, receita incompleta, arquivo ausente ou preview adulterado.

## Limite deliberado desta etapa

O 07D não grava alterações. Ele estabelece a leitura canônica, a entrega segura do asset e a tela-base. O 07E adicionará os controles manuais e o save idempotente de revisões imutáveis sobre o mesmo `SM3_EDIT_RECIPE_V1`.

## Indicadores em `/health`

```json
{
  "version": "2.4.0",
  "editor_workspace": true,
  "editor_workspace_read_only": true,
  "editor_workspace_asset_verified": true,
  "editor_workspace_contract": "SM3_EDITOR_WORKSPACE_V1"
}
```

## Teste de contrato

Dentro do contêiner, ou em um ambiente com as dependências do Worker:

```bash
python diagnostics/verify_editor_workspace.py
```

Saída esperada:

```text
SM3_EDITOR_WORKSPACE_2_4_0_PASS
```

O teste confirma estabilidade do `state_etag`, entrega vinculada do asset e recusa fail-closed após adulteração do preview.
