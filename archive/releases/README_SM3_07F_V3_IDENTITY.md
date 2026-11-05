# Projeto SM3 — 07F v3 / Worker 2.8.0 — Identity Asset Bindings

Este pacote adiciona binding verificável de ativos de identidade ao preview de revisão salva.

## Estado preservado
- Projeto: TATTOO_0002
- Conteúdo: CARROSSEL_0004
- Sessão: definida localmente por `SM3_07F_PREVIEW_V4_EDIT_SESSION_ID`
- Revisão atual: 4
- A revisão 4 não precisa ser recriada.
- O fluxo continua fail-closed e o preview continua LOW_RES_REVIEW / proibido para publicação.

## Contratos novos
- Worker: 2.8.0
- Preview: SM3_EDIT_PREVIEW_V3
- Identity binding: SM3_IDENTITY_ASSET_BINDING_V1

## Semântica de identity_application
- Os flags logo/stamp/texture/frame são pedidos explícitos.
- density=NONE significa: não acrescentar identidade automática além dos flags explícitos.
- density LOW/MEDIUM/HIGH continua bloqueado até existir um planejador automático verificável.

## Binding da REV4
O workflow procura exatamente um BINDING_STATUS=DEFAULT para cada role explicitamente ativa.
Para a REV4 atual são exigidos: logo, stamp, texture e frame.
Cada binding tem ID_ATIVO, ID_DRIVE, CONTENT_HASH SHA-256, MIME_TYPE, BINDING_ROLE e BINDING_STATUS.

A aba 07_ATIVOS_IDENTIDADE foi normalizada para A:R. Além dos 4 bindings DEFAULT da REV4, as outras 5 texturas existentes em 05_PADROES_TEXTURAS foram catalogadas como ALTERNATE para seleção futura.

## Ordem de instalação
1. Extraia os arquivos na raiz D:\MOLOTOV_SOCIAL_OS_RC7.
2. Não salve uma nova revisão no editor.
3. Execute no PowerShell:
   .\SM3_07F_INSTALL_WORKER_2_8_0.ps1
4. Confirme a saída:
   SM3_WORKER_2_8_0_IDENTITY_BINDINGS_INSTALL_PASS
5. Importe no n8n:
   PROJETO_SM3_07F_EDIT_PREVIEWS_v3_VERIFIED_IDENTITY_RENDER.json
6. Execute o workflow "PROJETO SM3 — 07F — EDIT PREVIEWS — v3 VERIFIED IDENTITY RENDER" uma vez.
7. Defina `SM3_07F_PREVIEW_V4_EDIT_SESSION_ID` no ambiente local e, se o workflow terminar verde, execute:
   .\SM3_07F_VERIFICAR_E_BAIXAR_PREVIEW_V4.ps1
8. Resultado esperado:
   SM3_07F_V4_CURRENT_PREVIEW_BYTES_VERIFIED

## O que o renderer faz
- mídia continua protagonista e usa CONTAIN;
- EXIF transpose é preservado;
- texto permanece na faixa inferior, fora da foto;
- texture é aplicada somente na faixa inferior em baixa opacidade;
- logo fica na faixa inferior à esquerda;
- carimbo fica na faixa inferior à direita;
- moldura é redimensionada proporcionalmente e aplicada à área de mídia sem stretch;
- safe_margin_percent da receita é respeitado;
- hashes das mídias e dos ativos são verificados antes e depois do render;
- os hashes e placements usados ficam persistidos no manifest.json.

## Validações do pacote
- Python py_compile: PASS
- teste unitário de binding/contrato: PASS
- render real de segmento com FFmpeg e quatro roles: PASS
- composição dos quatro ativos reais (logo, carimbo, textura e moldura): PASS
- sintaxe JavaScript dos Code nodes do workflow n8n: PASS
- integridade do ZIP: PASS

## Arquivos
- SM3_worker_service_2_8_0.py
- SM3_07F_INSTALL_WORKER_2_8_0.ps1
- PROJETO_SM3_07F_EDIT_PREVIEWS_v3_VERIFIED_IDENTITY_RENDER.json
- SM3_07F_VERIFICAR_E_BAIXAR_PREVIEW_V4.ps1

Não execute o workflow v2 depois de instalar o Worker 2.8.0; ele exige o contrato antigo V2 e deve falhar por design.
