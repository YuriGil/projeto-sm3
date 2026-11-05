# Projeto SM3 — 08D Geometry-Aware Composition V1

## O que esta etapa muda

08C provou que o sistema consegue dizer **onde está a tatuagem**. 08D é a primeira etapa que usa essa compreensão para **mudar a edição**.

Ela não substitui a REV4 e não cria REV5. O preview ruim original continua como baseline negativo e o novo resultado é gravado em uma área paralela, com outro contrato.

### Arquitetura

- Worker: `2.12.0`
- Renderer canônico antigo: `2.8.0` — preservado
- Semantic Geometry: `SM3_SEMANTIC_GEOMETRY_V1`
- Composition Plan: `SM3_COMPOSITION_PLAN_V1`
- Planner: `SM3_GEOMETRY_AWARE_COMPOSITOR_V1`
- Preview experimental: `SM3_GEOMETRY_PREVIEW_V1`
- Renderer experimental: `2.12.0`
- Learning Router: `SM3_LEARNING_ROUTER_V1`

O 08D produz primeiro um **plano de composição imutável** e só depois renderiza. Isso permite responder exatamente por que cada mídia recebeu um crop, contain, supressão de identidade ou assinatura.

## Decisão esperada para o fixture atual

Os três registros de `21_SEMANTIC_GEOMETRY` estão VERIFIED:

- `M0083` — crop 4:5 seguro -> `SEMANTIC_CROP`
- `M0085` — vídeo dinâmico e crop 4:5 inseguro -> `CONTAIN_SOLID`
- `M0086` — crop 4:5 seguro -> `SEMANTIC_CROP`

O sistema **não usa mais blur para preencher o fundo**.

O aprendizado negativo da REV4 também é consumido:

- `FRAME_OBSCURES_SUBJECT` -> moldura suprimida
- `IDENTITY_APPLICATION_CONTEXTLESS` / `TATTOO_NOT_PROTAGONIST` -> textura suprimida e identidade reduzida
- carimbo -> mantido como assinatura pequena **fora da área de mídia**
- logo -> suprimida quando o carimbo já cumpre a função de assinatura, evitando duas marcas competindo

Importante: todos os quatro arquivos solicitados pela receita continuam sendo baixados e verificados por SHA-256. “Suprimir visualmente” não significa relaxar a proveniência.

## Qualidade do preview

O preview 08D sobe de `544x680` para **1080x1350** para o carrossel. Ele continua sendo um preview de revisão e não deve ser publicado.

O footer cai de aproximadamente 23% para cerca de 7%. O crop semântico nunca recebe um segundo crop destrutivo apenas para preencher esse footer: pixels residuais usam matte sólido neutro.

## Planilha

Foi criada a aba:

`22_COMPOSITION_PLANS`

Ela é um espelho operacional dos planos/renderizações. A autoridade continua sendo o Worker e seus manifests hasheados.

## Instalação

Extraia o pacote na raiz do projeto:

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
.\SM3_08D_INSTALL_WORKER_2_12_0.ps1
```

Esperado:

```text
SM3_08D_GEOMETRY_AWARE_COMPOSITION_INSTALL_PASS
```

O instalador confirma antes/depois:

- REV4 continua sendo 4
- `state_etag` continua o mesmo
- perfil continua `DP_BASE_MOLOTOV`
- M0083/M0085/M0086 continuam com geometria VERIFIED
- baseline de aprendizado continua presente

## Workflow n8n

Importe:

`PROJETO_SM3_08D_GEOMETRY_AWARE_COMPOSITION_v1.json`

Execute uma vez. Ele:

1. verifica Worker 2.12.0 e contratos;
2. lê 04_CONTEUDOS, 03_MIDIAS, 07_ATIVOS_IDENTIDADE e 21_SEMANTIC_GEOMETRY;
3. exige geometria VERIFIED para todas as mídias;
4. baixa originais e ativos de identidade já conhecidos;
5. verifica hashes;
6. constrói o plano de composição dentro do Worker;
7. renderiza o preview experimental;
8. relê o manifest persistido;
9. grava `22_COMPOSITION_PLANS`;
10. relê a planilha e confirma persistência.

O último node deve retornar:

```text
SM3_08D_GEOMETRY_AWARE_COMPOSITION_COMMITTED
```

## Verificação e download

Defina `SM3_08D_EDIT_SESSION_ID` no ambiente local antes de executar o verificador. Não grave o ID da sessão no repositório.

```powershell
.\SM3_08D_VERIFICAR_E_BAIXAR_PREVIEW.ps1
```

Esperado:

```text
SM3_08D_GEOMETRY_AWARE_PREVIEW_VERIFY_PASS
```

O script também verifica que o preview canônico ruim da REV4 ainda possui exatamente o SHA-256 anterior. Assim sabemos que o 08D não reescreveu a evidência negativa.

O novo arquivo será salvo em:

```text
SM3_PREVIEWS\GEOMETRY_AWARE\REV4\CARROSSEL_0004_REV4_08D_GEOMETRY_AWARE.mp4
```

## Limite proposital do 08D V1

`M0085` ainda não tem tracking temporal. Como a geometria marcou `dynamic_required=true`, o compositor **se recusa a inventar um crop fixo** e usa `CONTAIN_SOLID`.

Isso não é o resultado final desejado. É o fallback correto até construirmos tracking/pan-scan real. Quando chegarmos nessa camada, o mesmo plano poderá mudar para `TRACK_SUBJECT` sem destruir a fonte comum de aprendizado.
