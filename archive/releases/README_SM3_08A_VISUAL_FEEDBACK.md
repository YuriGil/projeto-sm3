# Projeto SM3 — 08A Visual Feedback / Teaching Contract

## Objetivo

Esta etapa não tenta "embelezar" o renderer. Ela cria o mecanismo que transforma crítica humana em evidência persistente e verificável.

O Worker 2.9.0 adiciona:

- `SM3_VISUAL_FEEDBACK_V1`
- `SM3_VISUAL_ISSUES_V1`
- feedback imutável ligado à revisão, `state_etag` e `preview_sha256` exatos
- idempotência
- detecção de adulteração por SHA-256
- taxonomia controlada de problemas visuais
- histórico por revisão
- painel "Ensinar o SM3" dentro do editor
- preservação do renderer de preview em `2.8.0`

Importante: o serviço passa a ser Worker `2.9.0`, mas o renderer continua deliberadamente identificado como `2.8.0`. Isso evita invalidar ou conflitar com o preview REV4 já renderizado, porque a lógica de render não foi alterada nesta etapa.

## Estado da REV4 usado como primeiro exemplo negativo

- Projeto: `TATTOO_0002`
- Conteúdo: `CARROSSEL_0004`
- Sessão: definida localmente em `SM3_08A_EDIT_SESSION_ID`
- Revisão: `4`
- `state_etag`: `22f05816c38651d2126f0f9519b6f11f8c5d7368fa93331b0ee73bd152683d09`
- `preview_sha256`: `d4fc6f76cff6ca32cf531e3067c12d0359a8cddc71ccf08c29500265e2e539bd`

O script de bootstrap falha fechado se qualquer um desses valores não corresponder ao estado atual.

## Instalação

Extraia o pacote na raiz:

`D:\MOLOTOV_SOCIAL_OS_RC7`

Execute:

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
.\SM3_08A_INSTALL_WORKER_2_9_0.ps1
```

Resultado esperado:

`SM3_08A_VISUAL_FEEDBACK_INSTALL_PASS`

O instalador:
- cria backup do Worker atual
- valida o compose sem imprimir as variáveis resolvidas
- compila com saída ao vivo
- recria apenas `media-worker`
- não apaga volumes
- verifica health, contratos e taxonomia

## Registrar o primeiro exemplo negativo

Depois da instalação:

```powershell
.\SM3_08A_REGISTRAR_REV4_FEEDBACK_NEGATIVO.ps1
```

Resultado esperado:

`SM3_08A_REV4_NEGATIVE_BASELINE_REGISTERED`

O registro inclui os problemas observados no REV4, entre eles:
- moldura invadindo o assunto
- crop/enquadramento ruim
- orientação ruim
- suavidade/foco insuficiente
- composição desequilibrada
- tattoo deixando de ser protagonista
- aplicação de identidade sem contexto
- aparência de template
- posicionamento incoerente
- desalinhamento com a identidade
- repetição mecânica
- qualidade insuficiente do preview

## Verificar persistência

Defina `SM3_08A_EDIT_SESSION_ID` no ambiente local antes de executar o verificador. O script falha se a variável não estiver configurada; não grave IDs de sessão no repositório.

```powershell
.\SM3_08A_VERIFICAR_FEEDBACK.ps1
```

Resultado esperado:

`SM3_08A_VISUAL_FEEDBACK_VERIFY_PASS`

## Editor

O mesmo endereço do editor continua válido:

`http://localhost:8090/production/editor/TATTOO_0002/CARROSSEL_0004/<EDIT_SESSION_ID>`

Agora existe uma seção chamada **Ensinar o SM3**.

Ela permite:
- APROVADO / PRECISA DE REVISÃO / REJEITADO
- crítica geral
- intenção de correção
- o que deve ser preservado
- classificação dos problemas pela taxonomia
- severidade

Registrar feedback não cria nova revisão e não altera a receita.

## Persistência

Fonte de verdade:

`/data/media/production_state/visual_feedback/...`

Cada feedback é um JSON imutável e auto-verificável. O registro contém:
- IDs e revisão
- estado exato
- hash do preview
- hash do manifesto
- hash da receita
- hashes das fontes e identidade
- renderer usado
- crítica estruturada
- SHA-256 do próprio registro

## Google Sheets

A aba `19_VISUAL_FEEDBACK` já foi criada em `CONTROLE_MOLOTOV` com o schema do espelho operacional.

Nesta subetapa, o Worker local continua sendo a autoridade. A sincronização automática do histórico imutável para essa aba será ligada na evolução seguinte; não usaremos a planilha como fonte autoritativa do feedback.

## Compatibilidade 07F

O pacote inclui:
- `PROJETO_SM3_07F_EDIT_PREVIEWS_v3_1_WORKER_2_9_COMPAT.json`
- `SM3_07F_VERIFICAR_E_BAIXAR_PREVIEW_V5.ps1`

Eles mantêm `SM3_EDIT_PREVIEW_V3` e exigem renderer `2.8.0`, mas reconhecem o Worker de serviço `2.9.0`.

## Testes executados antes da entrega

- Python compile: PASS
- criação do feedback: PASS
- idempotência: PASS
- leitura do histórico: PASS
- hash de preview incorreto: bloqueado
- registro adulterado: bloqueado
- health contract: PASS
- JavaScript do editor: PASS
- Code Nodes do workflow 07F v3.1: PASS
- conexões do workflow: PASS

Consulte `SM3_08A_TEST_REPORT.txt`.
