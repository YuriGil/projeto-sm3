# Projeto SM3 — 09A.3 — Reference Media Acquisition

Esta etapa cria a ponte segura entre `REFERENCE_ITEM_ID` e os bytes reais do vídeo.

## Princípio

O projeto não depende de scraping do Instagram. Um URL é proveniência; análise de vídeo exige um arquivo real disponível ao Worker.

A aquisição é feita em duas etapas:

1. arquivo entra em `/data/media/reference_inbox`;
2. Worker valida com ffprobe, calcula SHA-256, copia para armazenamento canônico imutável em `reference_sources/...`, grava manifesto `SM3_REFERENCE_MEDIA_ACQUISITION_V1` e devolve `LOCAL_MEDIA_REF`.

## Instalação

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09A3_INSTALL_WORKER_2_16_1.ps1"
```

Esperado: `SM3_09A3_REFERENCE_MEDIA_ACQUISITION_INSTALL_PASS`.

Depois:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09A3_VERIFICAR_AQUISICAO_MIDIA.ps1"
```

Enquanto `item_count=0`, `media_acquisition_count=0` é o estado correto.

## Quando existir um RI_...

Importe um vídeo local assim:

```powershell
.\SM3_09A3_IMPORTAR_VIDEO_REFERENCIA.ps1 `
  -ReferenceItemId RI_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx `
  -SourceFile "D:\Downloads\reel.mp4" `
  -CleanupInbox
```

O script usa `docker cp` apenas como transporte até o volume compartilhado. O Worker é quem valida, hasheia e cria a cópia canônica.

Depois importe/execute o workflow `PROJETO_SM3_09A3_REFERENCE_MEDIA_ACQUISITION_SYNC_v1.json` para preencher `LOCAL_MEDIA_REF` na aba 32. A partir daí o 09B consegue analisar o vídeo.
