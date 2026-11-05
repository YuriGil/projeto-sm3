[CmdletBinding()]
param(
    [string]$OutputRoot = (Join-Path $env:USERPROFILE "Downloads\SM3_07B_PREVIEWS_VERIFIED"),
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ComposeFiles = @(
    "deployment\docker-compose.yml",
    "deployment\docker-compose.worker.yml"
)

foreach ($ComposeFile in $ComposeFiles) {
    if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) {
        throw "COMPOSE_FILE_NOT_FOUND: $ComposeFile. Execute este script na raiz do Projeto SM3."
    }
}

$ComposeArgs = @()
foreach ($ComposeFile in $ComposeFiles) {
    $ComposeArgs += @("-f", $ComposeFile)
}

$Targets = @(
    [pscustomobject]@{
        ProjectId   = "TATTOO_0002"
        ContentId   = "CARROSSEL_0004"
        VariantSetId = "VS_8d19d76f4e454cd196a53077feac00f0"
    },
    [pscustomobject]@{
        ProjectId   = "TATTOO_0002"
        ContentId   = "REEL_0006"
        VariantSetId = "VS_01cc54abc5fe4bf2af2b64694e3f8aac"
    }
)

function Invoke-DockerCompose {
    param([Parameter(Mandatory)][string[]]$Arguments)

    $PreviousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5 converts any native stderr output into a
        # NativeCommandError when ErrorActionPreference is Stop. Docker writes
        # harmless progress messages to stderr, so trust its exit code instead.
        $ErrorActionPreference = "Continue"
        $Result = & docker compose @ComposeArgs @Arguments 2>&1
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }

    if ($ExitCode -ne 0) {
        throw "DOCKER_COMPOSE_FAILED: docker compose $($Arguments -join ' ')`n$($Result -join "`n")"
    }
    return $Result
}

function Read-ContainerJson {
    param(
        [Parameter(Mandatory)][string]$RemotePath
    )

    $Raw = Invoke-DockerCompose -Arguments @(
        "exec", "-T", "media-worker",
        "sh", "-lc", "test -f '$RemotePath' && cat '$RemotePath'"
    )
    try {
        return (($Raw -join "`n") | ConvertFrom-Json)
    }
    catch {
        throw "REMOTE_JSON_INVALID: $RemotePath`n$($_.Exception.Message)"
    }
}

function Copy-ContainerFile {
    param(
        [Parameter(Mandatory)][string]$RemotePath,
        [Parameter(Mandatory)][string]$LocalPath
    )

    $Parent = Split-Path -Parent $LocalPath
    New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    $null = Invoke-DockerCompose -Arguments @(
        "cp", "media-worker:$RemotePath", $LocalPath
    )
    if (-not (Test-Path -LiteralPath $LocalPath -PathType Leaf)) {
        throw "DOCKER_COPY_FAILED: $RemotePath -> $LocalPath"
    }
}

function Assert-Equal {
    param(
        [Parameter(Mandatory)]$Actual,
        [Parameter(Mandatory)]$Expected,
        [Parameter(Mandatory)][string]$Code
    )
    if ([string]$Actual -cne [string]$Expected) {
        throw "${Code}: actual='$Actual' expected='$Expected'"
    }
}

function ConvertTo-HtmlText {
    param([AllowNull()][object]$Value)
    return [System.Net.WebUtility]::HtmlEncode([string]$Value)
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "DOCKER_COMMAND_NOT_FOUND"
}

$WorkerProbe = Invoke-DockerCompose -Arguments @(
    "exec", "-T", "media-worker",
    "sh", "-lc", "test -d /data/media && printf SM3_WORKER_EXEC_OK"
)
if (($WorkerProbe -join "").Trim() -ne "SM3_WORKER_EXEC_OK") {
    throw "MEDIA_WORKER_SERVICE_UNAVAILABLE"
}

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$Summary = [System.Collections.Generic.List[object]]::new()
$VerifiedManifests = [System.Collections.Generic.List[object]]::new()

foreach ($Target in $Targets) {
    $PreviewRoot = "/data/media/production_state/variant_previews/$($Target.ProjectId)/$($Target.ContentId)/$($Target.VariantSetId)"
    $ManifestPath = "$PreviewRoot/manifest.json"
    $VariantSetPath = "/data/media/production_state/variant_sets/$($Target.ProjectId)/$($Target.ContentId)/$($Target.VariantSetId).json"

    Write-Host "Lendo $ManifestPath"
    $Manifest = Read-ContainerJson -RemotePath $ManifestPath
    $VariantSet = Read-ContainerJson -RemotePath $VariantSetPath

    Assert-Equal $Manifest.ok $true "MANIFEST_NOT_OK"
    Assert-Equal $Manifest.version "2.2.1" "WORKER_VERSION_MISMATCH"
    Assert-Equal $Manifest.production_contract_version "SM3_PRODUCTION_EDIT_V1" "PRODUCTION_CONTRACT_MISMATCH"
    Assert-Equal $Manifest.preview_contract_version "SM3_VARIANT_PREVIEW_V1" "PREVIEW_CONTRACT_MISMATCH"
    Assert-Equal $Manifest.project_id $Target.ProjectId "PROJECT_ID_MISMATCH"
    Assert-Equal $Manifest.content_id $Target.ContentId "CONTENT_ID_MISMATCH"
    Assert-Equal $Manifest.variant_set_id $Target.VariantSetId "VARIANT_SET_ID_MISMATCH"
    Assert-Equal $Manifest.variant_count 3 "VARIANT_COUNT_MISMATCH"
    Assert-Equal @($Manifest.previews).Count 3 "PREVIEW_ARRAY_COUNT_MISMATCH"
    Assert-Equal @($VariantSet.variants).Count 3 "VARIANT_RECIPE_COUNT_MISMATCH"

    $ActualVariantIds = @($Manifest.previews | ForEach-Object { [string]$_.variant_id } | Sort-Object)
    $ExpectedVariantIds = @("V01", "V02", "V03")
    Assert-Equal ($ActualVariantIds -join ",") ($ExpectedVariantIds -join ",") "VARIANT_IDS_MISMATCH"

    $ContentDirectory = Join-Path $OutputRoot $Target.ContentId
    New-Item -ItemType Directory -Path $ContentDirectory -Force | Out-Null

    $LocalManifest = Join-Path $ContentDirectory "manifest.json"
    $LocalVariantSet = Join-Path $ContentDirectory "variant_set.json"
    Copy-ContainerFile -RemotePath $ManifestPath -LocalPath $LocalManifest
    Copy-ContainerFile -RemotePath $VariantSetPath -LocalPath $LocalVariantSet

    foreach ($Preview in ($Manifest.previews | Sort-Object variant_id)) {
        $VariantId = [string]$Preview.variant_id
        $ExpectedPrefix = "$PreviewRoot/$VariantId/"
        $RemotePreview = [string]$Preview.preview_path
        $RemoteCover = [string]$Preview.cover_path

        if (-not $RemotePreview.StartsWith($ExpectedPrefix, [System.StringComparison]::Ordinal) -or
            -not $RemoteCover.StartsWith($ExpectedPrefix, [System.StringComparison]::Ordinal)) {
            throw "PREVIEW_PATH_ESCAPES_VARIANT_ROOT: $($Target.ContentId)/$VariantId"
        }

        $VariantDirectory = Join-Path $ContentDirectory $VariantId
        $LocalPreview = Join-Path $VariantDirectory "preview.mp4"
        $LocalCover = Join-Path $VariantDirectory "cover.jpg"
        Copy-ContainerFile -RemotePath $RemotePreview -LocalPath $LocalPreview
        Copy-ContainerFile -RemotePath $RemoteCover -LocalPath $LocalCover

        $ActualHash = (Get-FileHash -LiteralPath $LocalPreview -Algorithm SHA256).Hash.ToLowerInvariant()
        $ExpectedHash = ([string]$Preview.preview_sha256).ToLowerInvariant()
        Assert-Equal $ActualHash $ExpectedHash "PREVIEW_SHA256_MISMATCH:$($Target.ContentId):$VariantId"

        $ActualBytes = (Get-Item -LiteralPath $LocalPreview).Length
        Assert-Equal $ActualBytes $Preview.preview_bytes "PREVIEW_SIZE_MISMATCH:$($Target.ContentId):$VariantId"

        $Recipe = @($VariantSet.variants | Where-Object { [string]$_.variant_id -ceq $VariantId })
        Assert-Equal $Recipe.Count 1 "VARIANT_RECIPE_NOT_UNIQUE:$($Target.ContentId):$VariantId"

        $Summary.Add([pscustomobject]@{
            content_id        = $Target.ContentId
            variant_set_id    = $Target.VariantSetId
            variant_id        = $VariantId
            label             = [string]$Preview.label
            strategy          = [string]$Preview.strategy
            rationale         = [string]$Preview.rationale
            manual_edit_intent = [string]$Preview.manual_edit_intent
            duration_seconds  = $Preview.duration_seconds
            target            = "$($Preview.target_width)x$($Preview.target_height)"
            preview_bytes     = $ActualBytes
            preview_sha256    = $ActualHash
            remote_preview    = $RemotePreview
            local_preview     = $LocalPreview
        })
    }

    $VerifiedManifests.Add([pscustomobject]@{
        content_id = $Target.ContentId
        variant_set_id = $Target.VariantSetId
        manifest_path = $ManifestPath
        local_manifest = $LocalManifest
        verified_at = (Get-Date).ToUniversalTime().ToString("o")
    })
}

Assert-Equal $Summary.Count 6 "TOTAL_PREVIEW_COUNT_MISMATCH"

$CsvPath = Join-Path $OutputRoot "SM3_07B_preview_comparison.csv"
$Summary | Export-Csv -LiteralPath $CsvPath -NoTypeInformation -Encoding UTF8

$VerificationPath = Join-Path $OutputRoot "SM3_07B_verified_manifests.json"
$VerifiedManifests | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $VerificationPath -Encoding UTF8

$Sections = foreach ($ContentId in @("CARROSSEL_0004", "REEL_0006")) {
    $Cards = foreach ($Item in ($Summary | Where-Object content_id -ceq $ContentId | Sort-Object variant_id)) {
        $RelativeVideo = "$ContentId/$($Item.variant_id)/preview.mp4"
        $RelativeCover = "$ContentId/$($Item.variant_id)/cover.jpg"
        @"
        <article class="card">
          <h3>$(ConvertTo-HtmlText $Item.variant_id) — $(ConvertTo-HtmlText $Item.label)</h3>
          <video controls preload="metadata" poster="$(ConvertTo-HtmlText $RelativeCover)">
            <source src="$(ConvertTo-HtmlText $RelativeVideo)" type="video/mp4">
          </video>
          <dl>
            <dt>Estratégia</dt><dd>$(ConvertTo-HtmlText $Item.strategy)</dd>
            <dt>Racional</dt><dd>$(ConvertTo-HtmlText $Item.rationale)</dd>
            <dt>Ajustes manuais previstos</dt><dd>$(ConvertTo-HtmlText $Item.manual_edit_intent)</dd>
            <dt>Duração / quadro</dt><dd>$(ConvertTo-HtmlText $Item.duration_seconds)s · $(ConvertTo-HtmlText $Item.target)</dd>
            <dt>SHA-256</dt><dd class="hash">$(ConvertTo-HtmlText $Item.preview_sha256)</dd>
          </dl>
        </article>
"@
    }
    @"
    <section>
      <h2>$(ConvertTo-HtmlText $ContentId)</h2>
      <div class="grid">$($Cards -join "`n")</div>
    </section>
"@
}

$HtmlPath = Join-Path $OutputRoot "COMPARAR_V01_V02_V03.html"
$Html = @"
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>SM3 — comparação de variantes 07B</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, Segoe UI, sans-serif; }
    body { margin: 0; background: #101312; color: #f5efe4; }
    main { max-width: 1680px; margin: 0 auto; padding: 28px; }
    h1 { margin: 0 0 8px; }
    .status { color: #c49a4b; margin: 0 0 34px; }
    section { margin: 0 0 42px; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
    .card { background: #1b211f; border: 1px solid #385447; border-radius: 14px; padding: 16px; }
    video { width: 100%; max-height: 70vh; background: #000; border-radius: 9px; }
    dl { display: grid; grid-template-columns: 145px 1fr; gap: 8px 12px; }
    dt { color: #d94b2b; font-weight: 700; }
    dd { margin: 0; line-height: 1.4; }
    .hash { overflow-wrap: anywhere; font-family: Consolas, monospace; font-size: 11px; color: #aebbb5; }
    @media (max-width: 1050px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <h1>Projeto SM3 — V01 × V02 × V03</h1>
    <p class="status">6 previews reais · hashes verificados · SM3_VARIANT_PREVIEW_V1</p>
    $($Sections -join "`n")
  </main>
</body>
</html>
"@
$Html | Set-Content -LiteralPath $HtmlPath -Encoding UTF8

Write-Host ""
Write-Host "SM3_07B_PREVIEW_EXPORT_PASS"
Write-Host "Serviço: media-worker"
Write-Host "Previews verificados: $($Summary.Count)"
Write-Host "Pasta: $OutputRoot"
Write-Host "Comparação: $HtmlPath"
Write-Host "CSV: $CsvPath"
Write-Host ""
$VerifiedManifests | Format-Table content_id, variant_set_id, manifest_path -AutoSize

if (-not $NoOpen) {
    Start-Process $HtmlPath
}
