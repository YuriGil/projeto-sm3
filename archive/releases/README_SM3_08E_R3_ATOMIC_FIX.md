# SM3 08E R3 — Atomic publication artifact fix

## Causa do erro

O Worker 2.13.0 renderizava corretamente os JPGs dentro de um diretório temporário `.stage_<uuid>`.
Depois fazia o commit atômico renomeando a pasta inteira para `revision_0004`.

O manifesto, porém, havia sido construído **antes do rename** e guardava os caminhos absolutos temporários.
Após o rename os bytes estavam no lugar correto, mas o verificador procurava nos caminhos `.stage_*`, que já não existiam.

Resultado: o node `WORKER — RENDER NATIVE ARTIFACT` falhava no pós-commit.

## Correção 2.13.1

- o manifesto passa a registrar os caminhos FINAIS antes do commit;
- o diretório temporário continua sendo usado para renderização;
- o rename continua atômico;
- somente depois do rename o manifesto é verificado;
- o Worker reconhece exclusivamente o failed-commit conhecido do renderer 2.13.0;
- valida bytes/hashes do failed-commit;
- move esse diretório antigo para quarentena;
- rerenderiza de forma determinística;
- corrupção desconhecida continua fail-closed.

Nenhuma REV5 é criada.
REV4, 08C e 08D permanecem preservados.

## Instalação

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08E_INSTALL_WORKER_2_13_1_R3.ps1"
```

Esperado:

```text
SM3_08E_NATIVE_FORMAT_EDITORIAL_INSTALL_PASS
worker_version                : 2.13.1
publication_artifact_renderer : 2.13.1
```

Depois importe o workflow:

```text
PROJETO_SM3_08E_NATIVE_FORMAT_EDITORIAL_v1_1_ATOMIC_FIX.json
```

Execute uma vez.

Depois:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_08E_VERIFICAR_E_BAIXAR_ARTEFATO_R3.ps1"
```

Esperado:

```text
SM3_08E_NATIVE_FORMAT_ARTIFACT_VERIFY_PASS
```
