# SM3 09A.2 — v1.1 Quota + Sheet Fix

## Problema observado

O v1 parou em `READ — 32_REFERENCE_ITEMS` com:

`The service is receiving too many requests from you`

Além disso, uma auditoria preventiva encontrou mappings de escrita no node
`UPDATE — 32 REFERENCE ITEM BY URL` no formato incorreto `={ ... }`.
Eles ainda não chegaram a causar dano porque o fluxo falhou antes da escrita.

## Correções

1. `32_REFERENCE_ITEMS` é lida PRIMEIRO.
2. Se não houver itens novos, o workflow termina sem sequer consultar a aba 31.
3. Só quando existem itens pendentes ele consulta `31_REFERENCE_PROFILES`.
4. Ambos os reads usam `readRowsUntil = firstEmptyRow`, em vez de atravessar
   milhares de linhas pré-formatadas vazias.
5. Ambos os reads têm retry automático: 6 tentativas com 10 s entre tentativas.
6. O update da aba 32 também ganhou retry.
7. Todos os mappings de escrita foram corrigidos para expressões n8n válidas:
   `={{ $json.currentRow.FIELD }}`.
8. Worker 2.15.1 permanece inalterado.

## Estado atual

Com `32_REFERENCE_ITEMS` vazio, o resultado esperado é:

`SM3_09A2_NO_NEW_REFERENCE_ITEMS`

Não é necessário cadastrar um Reel apenas para testar a arquitetura.

## Verificador

O script `.ps1` não estava na raiz porque ele fica dentro do ZIP 09A.2.
Um arquivo standalone é incluído novamente no pacote v1.1.
