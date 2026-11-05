# Projeto SM3 — 08B Direction Profiles + Learning Router

## Por que esta fase existe

O mesmo sistema precisa poder produzir direções diferentes (por exemplo, **Lento / Melódico** e **Rápido / Agitado**) sem misturar feedbacks de ritmo e estilo. Ao mesmo tempo, todos os perfis precisam aprender com a mesma base central.

A solução implementada é **herança + escopo de aprendizado**, não memórias separadas.

### Camadas

1. **FOUNDATION** — princípios universais e compartilhados por todos os perfis.
   - tattoo/arte é o assunto principal;
   - nunca encobrir o assunto;
   - não deformar ativos;
   - identidade é embalagem, não conteúdo;
   - não decorar sem função.

2. **PROFILE** — preferências de execução que pertencem a um perfil e são herdadas pelos descendentes.
   - duração de planos;
   - energia;
   - ritmo;
   - densidade de transições;
   - intensidade de movimento;
   - relação com música;
   - densidade de texto/identidade.

3. **CONTENT** — correção específica daquele conteúdo, mantendo o contexto do perfil.

Todos os registros continuam no **mesmo corpus imutável de feedback**. `SM3_LEARNING_ROUTER_V1` decide quais exemplos são aplicáveis ao perfil atual. Feedback de outro perfil não entra por acidente.

## Perfis iniciais

- `DP_BASE_MOLOTOV` — base compartilhada.
- `DP_SLOW_MELODIC` — contemplativo, pausado, melódico.
- `DP_FAST_ENERGETIC` — rápido, energético, cortes curtos.
- `DP_PROCESS_DOCUMENTAL` — processo e narrativa visual.

Estes perfis são **intenções versionadas**. Nesta fase o renderer continua sendo `2.8.0`; os perfis ainda não mudam magicamente o vídeo. Eles criam a estrutura correta para os próximos motores de geometria, composição, timing e crítica consumirem a direção escolhida.

## Compatibilidade com o aprendizado já criado

O feedback negativo da REV4 (`SM3_VISUAL_FEEDBACK_V1`) não é alterado. O Worker 2.10.0 continua lendo V1 e o roteia como `FOUNDATION`, porque ele foi registrado antes da existência de perfis.

Novos feedbacks usam `SM3_VISUAL_FEEDBACK_V2` e exigem escopo explícito.

## Mudança de perfil

Trocar um perfil é uma decisão de edição. Portanto **cria nova revisão** e muda o `state_etag`.

Não altera o recipe base silenciosamente e não reescreve revisões antigas.

O editor passa a mostrar um seletor de perfil. O helper `SM3_08B_BIND_DIRECTION_PROFILE.ps1` existe para automação/teste, mas não deve ser usado sem intenção de criar uma revisão nova.

## Planilha

`CONTROLE_MOLOTOV` recebeu:
- `20_DIRECTION_PROFILES`
- colunas de perfil/roteamento em `19_VISUAL_FEEDBACK`

A planilha é espelho operacional. A autoridade do runtime permanece nos contratos e registros imutáveis do Worker.

## Ordem recomendada

1. `SM3_08B_INSTALL_WORKER_2_10_0.ps1`
2. `SM3_08B_VERIFICAR_PERFIS_E_APRENDIZADO.ps1`
3. **Não vincular perfil ainda**, a menos que queira criar REV5.
4. Próxima fase: Semantic Geometry, consumindo a base compartilhada + perfil ativo.
