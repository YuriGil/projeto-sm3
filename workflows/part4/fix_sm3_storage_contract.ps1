$ErrorActionPreference = "Stop"

$composePath = "deployment\docker-compose.worker.yml"
$backupPath = "deployment\docker-compose.worker.yml.bak"

if (Test-Path $composePath) {
    Copy-Item $composePath $backupPath -Force
    Write-Host "Backup criado em $backupPath"
}

@'
services:
  media-init:
    image: alpine:3.20
    restart: "no"
    user: "0:0"
    command: >
      sh -c "mkdir -p
      /data/media/inbox
      /data/media/inbox/n8n_temp
      /data/media/proxies
      /data/media/contact_sheets
      /data/media/curation
      /data/media/renders
      /data/media/system/dead_letter
      /data/media/production_state/variant_sets
      /data/media/production_state/variant_previews
      /data/media/production_state/edit_sessions
      && chown -R 1000:1000 /data/media"
    volumes:
      - molotov_media:/data/media

  n8n:
    environment:
      N8N_DEFAULT_BINARY_DATA_MODE: filesystem
      N8N_RESTRICT_FILE_ACCESS_TO: "/data/media;/home/node/.n8n-files"
    volumes:
      - molotov_media:/data/media
    depends_on:
      media-init:
        condition: service_completed_successfully

  media-worker:
    build:
      context: ..
      dockerfile: deployment/media-worker.Dockerfile
    restart: unless-stopped
    user: "1000:1000"
    environment:
      MEDIA_ROOT: /data/media
      VISION_PROVIDER: ${VISION_PROVIDER:-openai}
      VISION_MODEL: ${VISION_MODEL:-gpt-5.6-luna}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      OPENAI_BASE_URL: ${OPENAI_BASE_URL:-https://api.openai.com/v1}
      VISION_TIMEOUT_SECONDS: ${VISION_TIMEOUT_SECONDS:-180}
    ports:
      - "8090:8090"
    volumes:
      - molotov_media:/data/media
    depends_on:
      media-init:
        condition: service_completed_successfully

volumes:
  molotov_media:
'@ | Set-Content -Path $composePath -Encoding UTF8

Write-Host ""
Write-Host "1) Verificando arquivo..."
$local = Select-String -Path $composePath -Pattern "n8n_temp"
if (-not $local) { throw "ERRO: n8n_temp não foi gravado em $composePath" }
$local | ForEach-Object { Write-Host $_.Line }

Write-Host ""
Write-Host "2) Verificando compose efetivo..."
$resolved = docker compose -f deployment\docker-compose.yml -f deployment\docker-compose.worker.yml config
if ($LASTEXITCODE -ne 0) { throw "ERRO: docker compose config falhou" }
if (-not ($resolved | Select-String "n8n_temp")) {
    throw "ERRO: o compose efetivo ainda não contém n8n_temp. NÃO prossiga."
}
$resolved | Select-String "n8n_temp|variant_sets|variant_previews|edit_sessions" | ForEach-Object { Write-Host $_.Line }

Write-Host ""
Write-Host "3) Recriando stack SEM apagar volumes..."
docker compose -f deployment\docker-compose.yml -f deployment\docker-compose.worker.yml down
if ($LASTEXITCODE -ne 0) { throw "ERRO no docker compose down" }

docker compose -f deployment\docker-compose.yml -f deployment\docker-compose.worker.yml up -d --build --force-recreate
if ($LASTEXITCODE -ne 0) { throw "ERRO no docker compose up" }

Write-Host ""
Write-Host "4) Testando escrita no n8n..."
docker compose -f deployment\docker-compose.yml -f deployment\docker-compose.worker.yml exec n8n sh -lc "ls -ld /data/media/inbox/n8n_temp && touch /data/media/inbox/n8n_temp/_write_test && rm /data/media/inbox/n8n_temp/_write_test && echo N8N_WRITE_OK"
if ($LASTEXITCODE -ne 0) { throw "ERRO: n8n ainda não consegue escrever em n8n_temp" }

Write-Host ""
Write-Host "5) Testando escrita no worker..."
docker compose -f deployment\docker-compose.yml -f deployment\docker-compose.worker.yml exec media-worker sh -lc "ls -ld /data/media/inbox/n8n_temp && touch /data/media/inbox/n8n_temp/_worker_test && rm /data/media/inbox/n8n_temp/_worker_test && echo WORKER_WRITE_OK"
if ($LASTEXITCODE -ne 0) { throw "ERRO: worker ainda não consegue escrever em n8n_temp" }

Write-Host ""
Write-Host "SM3_STORAGE_CONTRACT_FIX_PASS"
