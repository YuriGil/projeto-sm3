# Projeto SM3 — Recursive Discovery Contract v1

A v18 remove dois tetos ocultos: descoberta de **projetos** agora atravessa containers recursivamente dentro de `00_BRUTOS`, e descoberta de **mídias** atravessa qualquer profundidade dentro de cada projeto.

## Configuração canônica

`11_OS_CONFIG`:
- `ingestion.root_folder_id`
- `ingestion.project_folder_regex`
- `ingestion.recursive.enabled`
- `ingestion.recursive.batch_folders`
- `ingestion.recursive.max_folders_per_run`
- `ingestion.recursive.max_files_per_run`
- `ingestion.recursive.max_queue_size`
- `ingestion.recursive.max_depth_guard`
- `ingestion.recursive.shortcut_policy`
- `ingestion.recursive.partial_write_policy`

O `max_depth_guard` é proteção patológica, não limite funcional. Qualquer guarda atingida envia a execução a um BLOCK explícito e **nenhuma escrita parcial acontece**.

## Segurança

- `known_folder_ids` impede ciclos/re-enfileiramento.
- `visited_folder_ids` registra pastas realmente consultadas.
- atalhos são `SKIP_AUDIT` até existir resolução de target segura.
- descoberta truncada nunca alcança idempotência, ingestão ou storage rotation.
- zero projetos ou zero mídias usa parada conservadora: não faz mass-OFFLINE automaticamente.

## Persistência

`03_MIDIAS` agora recebe `TREE_DEPTH` e `DISCOVERY_VERSION`. Profundidade é informativa.

## Teste

Importe primeiro `PROJETO_SM3_01A_RECURSIVE_DISCOVERY_v18_DRY_RUN.json`. O último nó deve ser `ASSERT — RECURSIVE DISCOVERY` com `status=RECURSIVE_DISCOVERY_PASS`. Só depois teste o workflow completo.
