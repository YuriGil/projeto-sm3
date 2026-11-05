# MOLOTOV MEDIA WORKER v1

Este pacote adiciona um worker local read-only para mídia.

## Copiar para o projeto

Copie:
- `worker/worker_service.py`
- `worker/requirements-worker.txt`
- `deployment/media-worker.Dockerfile`
- `deployment/docker-compose.worker.yml`

para as mesmas pastas do projeto `D:\MOLOTOV_SOCIAL_OS_RC7`.

## Subir o worker junto do n8n

No PowerShell, dentro de `D:\MOLOTOV_SOCIAL_OS_RC7`:

```powershell
docker compose -f deployment\docker-compose.yml -f deployment\docker-compose.worker.yml up -d --build
```

## Testar

Abra:
http://localhost:8090/health

Esperado:
- `"ok": true`
- `"ffmpeg": true`
- `"ffprobe": true`

## Segurança

- O original do Google Drive nunca é sobrescrito.
- O n8n baixa uma cópia temporária para `/data/media/inbox`.
- O worker cria proxies em `/data/media/proxies`.
- Vídeos também recebem contact sheet em `/data/media/contact_sheets`.
- A cópia temporária é apagada após processamento bem-sucedido.
