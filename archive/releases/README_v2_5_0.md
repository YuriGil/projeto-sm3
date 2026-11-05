# Projeto SM3 — Media Worker 2.5.0 / 07E

Esta versão disponibiliza edição manual da receita canônica no navegador e salva revisões imutáveis. O estado do 07C e as verificações do 07D são preservados.

## Contrato novo

- `GET /production/editor-workspace/{project_id}/{content_id}/{edit_session_id}` retorna `SM3_EDITOR_WORKSPACE_V1`.
- `GET .../base-preview` entrega somente o preview vinculado à sessão; não aceita caminho arbitrário.
- `GET /production/editor/{project_id}/{content_id}/{edit_session_id}` abre controles para timeline, ordem, enquadramento, foco, textos, identidade, cor, transições e áudio.
- `POST /production/edit-session/save` exige `SM3_EDIT_SAVE_V1`: revisão esperada, `state_etag`, chave de idempotência, receita inteira e descrição da alteração.
- Saves repetidos com a mesma chave retornam a revisão já gravada. Alterações concorrentes retornam 409.
- Cada save valida `preserve_subject=true`, fontes originais, campos permitidos e intervalos numéricos; escreve `revision_NNNN.json` uma única vez; substitui `current.json` de forma durável; relê ambos antes de confirmar.
- Se o processo parar entre a revisão e `current.json`, repetir a mesma requisição recupera o commit. Outra edição fica bloqueada até a situação ser resolvida.
- Antes de responder, o Worker relê `current.json`, o conjunto imutável de variantes e o manifesto de previews.
- O SHA-256 real do preview precisa coincidir com o manifesto e com `selection_evidence` da sessão.
- `state_etag` é determinístico para a revisão atual e participa do controle de concorrência do save.
- O workspace falha fechado diante de estado parcial, contrato divergente, receita incompleta, arquivo ausente ou preview adulterado.

## Limite da etapa

A tela mostra o preview imutável da variante escolhida e permite alterar sua receita. O save guarda a revisão, mas a prévia da receita alterada será renderizada em uma etapa posterior. Publicação continua dependendo de render final, QA e aprovação humana.

## Indicadores em `/health`

```json
{
  "version": "2.5.0",
  "editor_workspace": true,
  "editor_workspace_read_only": false,
  "editor_workspace_asset_verified": true,
  "editor_workspace_contract": "SM3_EDITOR_WORKSPACE_V1",
  "edit_session_save_safe": true,
  "edit_session_save_contract": "SM3_EDIT_SAVE_V1"
}
```

## Teste de contrato

Dentro do contêiner, ou em um ambiente com as dependências do Worker:

```bash
python diagnostics/verify_editor_workspace.py
```

Saída esperada:

```text
SM3_MANUAL_EDITOR_2_5_0_PASS
```

O teste confirma estabilidade do `state_etag`, entrega vinculada do asset, commit persistido, idempotência, conflitos e recusa após adulteração do preview.
