# Projeto SM3 — 08F — Art Direction Grammar + Variant Lab V1

## Objetivo

O 08F não publica nada e não cria REV5. Ele usa a mesma REV4, as geometrias 08C, o plano editorial 08E, os ativos reais de identidade e o aprendizado humano para gerar **três hipóteses visuais comparáveis**.

A mudança central é: o SM3 para de produzir uma única solução e fingir que ela é boa. Ele passa a propor alternativas e aprender com comparação humana.

## Estratégias iniciais

- `PHOTO_DOMINANT`: fotografia domina; sem texto; identidade mínima; crop protegido quando seguro; fallback neutro deliberado.
- `EDITORIAL_MOLOTOV`: composição assimétrica; textura verificada somente em margem externa; carimbo somente no fechamento; nada sobre a tattoo.
- `RAW_ARCHIVE`: campo de papel documental, foto inset, assinatura discreta no fechamento; sem texto redundante.

Essas estratégias não são templates fixos. São hipóteses da gramática de direção de arte e poderão ser ajustadas pelo aprendizado.

## Novo aprendizado misto

O Worker 2.14.0 adiciona `SM3_ART_DIRECTION_REVIEW_V1`. Isso permite dizer simultaneamente:

- compreensão semântica: boa;
- escolha de formato: boa;
- composição: ruim;
- direção de arte: ruim;
- identidade: ruim.

Assim, uma crítica estética não apaga o fato de que o SM3 reconheceu corretamente stencil → início do preto → desenvolvimento.

## Persistência

- `29_ART_DIRECTION_VARIANTS`: espelho dos sets de variantes.
- `30_ART_DIRECTION_REVIEWS`: reservado para avaliações estruturadas de variantes e baselines.
- Worker continua sendo a fonte canônica.

## Instalação

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08F_INSTALL_WORKER_2_14_0.ps1"
```

Esperado: `SM3_08F_ART_DIRECTION_VARIANT_LAB_INSTALL_PASS`.

## Registrar o feedback que acabou de ser dado ao 08E

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08F_REGISTRAR_FEEDBACK_08E.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08F_VERIFICAR_FEEDBACK_08E.ps1"
```

Esperado:
- `SM3_08F_08E_MIXED_FEEDBACK_REGISTERED`
- `SM3_08F_08E_MIXED_FEEDBACK_VERIFY_PASS`

## n8n

Importe `PROJETO_SM3_08F_ART_DIRECTION_VARIANT_LAB_v1.json` e execute uma vez.

Resultado esperado: `SM3_08F_ART_DIRECTION_VARIANT_LAB_COMMITTED`.

## Verificação / download

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08F_VERIFICAR_E_BAIXAR_VARIANTES.ps1"
```

Esperado: `SM3_08F_ART_DIRECTION_VARIANT_VERIFY_PASS`.

Serão baixadas 9 imagens (3 estratégias × 3 slides) e uma contact sheet comparativa em `SM3_ART_DIRECTION_VARIANTS\AV_...`.

## Regra de segurança editorial

Todas as variantes são `human_review_required=true` e `auto_publish_allowed=false`. Métricas sociais poderão influenciar tática no futuro, mas não podem sobrescrever a FOUNDATION.
