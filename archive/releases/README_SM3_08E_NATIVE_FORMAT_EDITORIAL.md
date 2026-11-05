# PROJETO SM3 — 08E — Native Format Editorial V1

## Objetivo

O 08E corrige o erro conceitual revelado pelo preview 08D: **preview técnico não é artefato publicável**.

Para `CARROSSEL_0004`, o produto editorial nativo passa a ser um conjunto de 3 imagens 4:5 independentes (1080×1350), e não um MP4 curto simulando uma timeline.

O 08E preserva integralmente:
- REV4;
- `state_etag`;
- preview canônico do Worker 2.8.0;
- preview experimental 08D;
- registros de geometria 08C;
- aprendizado FOUNDATION e perfis 08B.

Nenhuma REV5 é criada.

## Versões e contratos

- Worker: `2.13.0`
- Canonical edit renderer: `2.8.0` (preservado)
- Geometry-aware preview renderer: `2.12.0` (preservado)
- Editorial intent: `SM3_EDITORIAL_INTENT_V1`
- Planner: `SM3_NATIVE_FORMAT_PLANNER_V1`
- Publication artifact: `SM3_PUBLICATION_ARTIFACT_V1`
- Native artifact renderer: `2.13.0`

## Decisões editoriais desta versão

Para CARROSSEL:
- artefato nativo: `CAROUSEL_IMAGE_SET`;
- 3 arquivos JPG independentes;
- 1080×1350;
- sem timeline;
- sem duração fixa;
- sem áudio;
- sem rodapé genérico;
- sem rótulos "Stencil / Linework / Em desenvolvimento";
- sem repetição obrigatória de carimbo/logo;
- identidade solicitada continua verificada por hash, mas pode ser suprimida se não houver aplicação contextual comprovadamente segura;
- tattoo/fotografia continua protagonista;
- revisão humana continua obrigatória antes de publicação.

### Estratégia esperada no fixture

- `M0083`: crop orientado pela região protegida quando possível;
- `M0085`: frame representativo do vídeo + `SAFE_CONTAIN_ADAPTIVE_MATTE`, porque a geometria temporal não autoriza crop fixo agressivo;
- `M0086`: crop orientado pela região protegida quando possível.

O frame representativo do vídeo é derivado dos dados de sampling existentes; ele não é escolhido com um tempo hardcoded de 2,2 s.

## Separação: publicação x review

Os três JPGs são candidatos de publicação.

Também é gerada uma contact sheet separada **apenas para review humano**. Rótulos técnicos na contact sheet não fazem parte dos pixels publicáveis.

## Persistência operacional

O Worker é a fonte canônica do plano e do artefato.

O workflow espelha os registros nas abas:
- `27_EDITORIAL_PLANS`
- `28_PUBLICATION_ARTIFACTS`

## Instalação

Extraia todos os arquivos do pacote em:

```text
D:\MOLOTOV_SOCIAL_OS_RC7
```

Execute:

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
.\SM3_08E_INSTALL_WORKER_2_13_0.ps1
```

Resultado esperado:

```text
SM3_08E_NATIVE_FORMAT_EDITORIAL_INSTALL_PASS
```

O instalador faz backup do Worker atual antes da substituição e reconstrói apenas o `media-worker`.

## n8n

Importe:

```text
PROJETO_SM3_08E_NATIVE_FORMAT_EDITORIAL_v1.json
```

Nome esperado:

```text
PROJETO SM3 — 08E — NATIVE FORMAT EDITORIAL — v1
```

Execute uma vez.

Resultado final esperado:

```text
SM3_08E_NATIVE_FORMAT_EDITORIAL_COMMITTED
```

Não altere a REV4 antes desta execução.

## Verificação e download

Defina `SM3_08E_EDIT_SESSION_ID` no ambiente local antes de executar o verificador. Não grave o ID da sessão no repositório.

```powershell
.\SM3_08E_VERIFICAR_E_BAIXAR_ARTEFATO.ps1
```

Esperado:

```text
SM3_08E_NATIVE_FORMAT_ARTIFACT_VERIFY_PASS
```

Os arquivos serão baixados para:

```text
D:\MOLOTOV_SOCIAL_OS_RC7\
SM3_PUBLICATION_CANDIDATES\
CARROSSEL_0004_REV4_08E_NATIVE\
```

Arquivos esperados:
- `CARROSSEL_0004_SLIDE_01_M0083.jpg`
- `CARROSSEL_0004_SLIDE_02_M0085.jpg`
- `CARROSSEL_0004_SLIDE_03_M0086.jpg`
- `CARROSSEL_0004_REVIEW_CONTACT_SHEET.jpg`

O verifier também confirma que os dois baselines continuam intactos:
- canonical REV4 SHA-256:
  `d4fc6f76cff6ca32cf531e3067c12d0359a8cddc71ccf08c29500265e2e539bd`
- 08D geometry-aware SHA-256:
  `bd9f5885a7c8a856c0c5b3a1223f2e5c5ac5b5e2182e39dc1ce7848de225cd3d`

## O que o 08E NÃO tenta resolver

O 08E não é o editor temporal definitivo.

Para `REEL_0006`, o Worker 2.13.0 deliberadamente retorna que é necessário um editor temporal em vez de falsificar um Reel com duração arbitrária.

Isso será tratado na fase seguinte:
- seleção real de trechos;
- tracking temporal;
- ritmo dirigido pelo Direction Profile;
- áudio;
- cortes/transições;
- sinais provenientes das métricas sociais.

## Aprendizado social

A arquitetura já possui as tabelas:
- `23_SOCIAL_PUBLICATIONS`
- `24_SOCIAL_METRIC_SNAPSHOTS`
- `25_SOCIAL_EXPERIMENTS`
- `26_LEARNING_PRIORS`

Os dados de rede serão evidência de otimização, nunca permissão para violar a FOUNDATION.

A regra permanece:
**métrica pode ajustar tática; não pode sobrescrever proteção da tattoo, identidade, direção artística ou feedback humano explícito.**
