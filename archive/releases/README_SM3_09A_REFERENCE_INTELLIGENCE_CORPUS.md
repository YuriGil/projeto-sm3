# Projeto SM3 — 09A — Reference Intelligence Corpus

## O que muda

O SM3 agora ganha um corpus canônico para aprender com perfis externos sem misturar isso com a FOUNDATION.

A arquitetura separa:

1. **Preferência humana** — o que Yuri diz que gosta/não gosta.
2. **Referências externas** — linguagem visual/temporal observada em criadores.
3. **Métricas das referências** — evidência de desempenho dentro do contexto de cada perfil.
4. **Métricas próprias** — resultado real do @y.molotov.
5. **FOUNDATION** — regras duras que nenhuma referência ou métrica pode sobrescrever.

Perfis externos ensinam atributos abstratos. Eles não autorizam copiar identidade, pixels, layouts específicos ou marca de terceiros.

## Worker 2.15.0

Novos contratos:

- `SM3_REFERENCE_PROFILE_V1`
- `SM3_REFERENCE_ITEM_V1`
- `SM3_REFERENCE_METRIC_SNAPSHOT_V1`
- `SM3_REFERENCE_FEATURES_V1`
- `SM3_REFERENCE_CORPUS_POLICY_V1`

O renderer visual continua 2.14.0. Nenhum pixel mudou nesta fase.

## CONTROLE_MOLOTOV

Foram criadas:

- `31_REFERENCE_PROFILES`
- `32_REFERENCE_ITEMS`
- `33_REFERENCE_FEATURES`
- `34_REFERENCE_PRIORS`
- `35_REFERENCE_METRIC_SNAPSHOTS`

As regras humanas novas também foram incorporadas em `08_REGRAS_IDENTIDADE` (R018–R023), incluindo:
- enquadramento editorial obrigatório;
- overlays de identidade dentro da imagem;
- bordas texturizadas externas proibidas por padrão;
- filtros globais fixos proibidos;
- prioridade de desenvolvimento em vídeo;
- referências externas como evidência, nunca como autoridade sobre a FOUNDATION.

## Instalação

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09A_INSTALL_WORKER_2_15_0.ps1"
```

Esperado:

`SM3_09A_REFERENCE_CORPUS_INSTALL_PASS`

Depois:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09A_VERIFICAR_CORPUS.ps1"
```

Esperado:

`SM3_09A_REFERENCE_CORPUS_VERIFY_PASS`

## Quando Yuri enviar perfis

Exemplo:

```powershell
.\SM3_09A_REGISTRAR_PERFIL_REFERENCIA.ps1 `
  -Network instagram `
  -Handle "@perfil" `
  -ProfileUrl "https://www.instagram.com/perfil/" `
  -UserInterest @("RITMO","ENQUADRAMENTO","COR") `
  -StyleNotes "Gosto principalmente dos Reels e da maneira de mostrar tattoo."
```

O retorno cria `RP_<hash>`.

Cada Reel/post analisado entra como `RI_<hash>` pelo script `SM3_09A_REGISTRAR_ITEM_REFERENCIA.ps1`.

Métricas de competitor obtidas via Metricool entram como snapshots imutáveis pelo script `SM3_09A_REGISTRAR_METRICA_REFERENCIA.ps1`.

## Metricool

A integração atual expõe, para Instagram competitors:

**Reels:** perfil, reel ID, URL, texto, data, likes, comentários, interações e engagement.

**Posts:** perfil, post ID, imagem/URL, texto, data, likes, comentários, interações e engagement.

O conector disponível lê competitors já configurados no Metricool. Caso um novo perfil ainda não esteja cadastrado como competitor, essa etapa inicial poderá precisar ser feita no Metricool.

## Próxima fase — 09B

09B será o **Video Style Feature Extractor**.

Ele vai trabalhar sobre mídia real de referência e extrair:
- duração;
- hook;
- detecção de shots;
- cortes/10s;
- duração mediana dos planos;
- movimento;
- subject scale;
- texto;
- transições;
- speed ramp;
- beat sync;
- tratamento de cor;
- grain/sharpness;
- uso de identidade;
- forma de mostrar tattoo;
- estrutura narrativa.

09A guarda a fonte e a proveniência. 09B extrai a linguagem. 09C transforma múltiplos exemplos em priors.
