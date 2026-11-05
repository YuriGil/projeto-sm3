$ErrorActionPreference = "Stop"

$root = "D:\MOLOTOV_SOCIAL_OS_RC7"
$target = Join-Path $root "worker\worker_service.py"
$container = "deployment-media-worker-1"

function Fail([string]$Message) {
    throw $Message
}

function Count-Occurrences {
    param(
        [string]$Text,
        [string]$Needle
    )
    if ([string]::IsNullOrEmpty($Needle)) { return 0 }
    $count = 0
    $pos = 0
    while (($pos = $Text.IndexOf($Needle, $pos, [System.StringComparison]::Ordinal)) -ge 0) {
        $count++
        $pos += $Needle.Length
    }
    return $count
}

function Replace-Once {
    param(
        [string]$Old,
        [string]$New,
        [string]$Label
    )

    $count = Count-Occurrences -Text $script:code -Needle $Old
    if ($count -ne 1) {
        Fail "PATCH_ANCHOR_${Label}_COUNT_$count"
    }

    $script:code = $script:code.Replace($Old, $New)
}

if (-not (Test-Path $target)) {
    Fail "WORKER_NOT_FOUND:$target"
}

$code = [System.IO.File]::ReadAllText($target)

$alreadyComplete = (
    $code.Contains('WORKER_VERSION = "2.19.0"') -and
    $code.Contains('REFERENCE_CONTENT_DISCOVERY_CONTRACT_VERSION = "SM3_REFERENCE_CONTENT_DISCOVERY_V1"') -and
    $code.Contains('class ReferenceContentDiscoveryRequest(BaseModel):') -and
    $code.Contains('/production/reference-corpus/content-discovery/ingest') -and
    $code.Contains('"BROWSER_SESSION"') -and
    $code.Contains('"reference_content_discovery": True')
)

if ($alreadyComplete) {
    Write-Host "`nSM3 09C3 SOURCE ALREADY INSTALLED" -ForegroundColor Green
    Write-Host "Worker source : 2.19.0"
    Write-Host "No changes made."
    exit 0
}

if ($code.Contains('WORKER_VERSION = "2.19.0"')) {
    Fail "PARTIAL_2_19_STATE_DETECTED_DO_NOT_CONTINUE"
}

if (-not $code.Contains('WORKER_VERSION = "2.18.0"')) {
    Fail "EXPECTED_WORKER_2_18_0_NOT_FOUND"
}

if ($code.Contains('SM3_REFERENCE_CONTENT_DISCOVERY_V1')) {
    Fail "PARTIAL_DISCOVERY_STATE_DETECTED_DO_NOT_CONTINUE"
}

Write-Host "`n==> BACKUP" -ForegroundColor Cyan

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $root "sm3_backups\worker_2_18_0_pre_09C3_$stamp"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$backupFile = Join-Path $backupDir "worker_service.py"
Copy-Item $target $backupFile -Force
Write-Host "Backup: $backupDir" -ForegroundColor Green

try {
    Write-Host "`n==> PATCH VERSION" -ForegroundColor Cyan
    Replace-Once `
        'WORKER_VERSION = "2.18.0"' `
        'WORKER_VERSION = "2.19.0"' `
        "WORKER_VERSION"

    Write-Host "`n==> PATCH CONTRACT" -ForegroundColor Cyan
    Replace-Once `
        'REFERENCE_PUBLIC_SCRAPER_CONTRACT_VERSION = "SM3_REFERENCE_PUBLIC_SCRAPER_V1"' `
        @'
REFERENCE_PUBLIC_SCRAPER_CONTRACT_VERSION = "SM3_REFERENCE_PUBLIC_SCRAPER_V1"
REFERENCE_CONTENT_DISCOVERY_CONTRACT_VERSION = "SM3_REFERENCE_CONTENT_DISCOVERY_V1"
'@ `
        "DISCOVERY_CONTRACT"

    Write-Host "`n==> PATCH REFERENCE ITEM SOURCE" -ForegroundColor Cyan
    Replace-Once `
        'source: Literal["METRICOOL", "MANUAL_URL", "DRIVE_UPLOAD", "CHATGPT"] = "MANUAL_URL"' `
        'source: Literal["METRICOOL", "MANUAL_URL", "DRIVE_UPLOAD", "CHATGPT", "BROWSER_SESSION"] = "MANUAL_URL"' `
        "REFERENCE_ITEM_SOURCE"

    Write-Host "`n==> PATCH OBSERVATION PROVIDER" -ForegroundColor Cyan
    $obsOld = @'
class ReferenceObservationRequest(BaseModel):
    reference_profile_id: str
    network: Literal["instagram", "tiktok"] = "instagram"
    handle: str
    content_type: Literal["PROFILE", "REEL","POST", "CAROUSEL", "STORY", "VIDEO"] = "PROFILE"
    platform_item_id: Optional[str] = None
    url: str
    provider: Literal["META_GRAPH", "METRICOOL_MCP", "SCRAPER_PUBLIC", "HUMAN_SHARE", "MANUAL"]
'@
    $obsNew = @'
class ReferenceObservationRequest(BaseModel):
    reference_profile_id: str
    network: Literal["instagram", "tiktok"] = "instagram"
    handle: str
    content_type: Literal["PROFILE", "REEL","POST", "CAROUSEL", "STORY", "VIDEO"] = "PROFILE"
    platform_item_id: Optional[str] = None
    url: str
    provider: Literal["META_GRAPH", "METRICOOL_MCP", "SCRAPER_PUBLIC", "BROWSER_SESSION", "HUMAN_SHARE", "MANUAL"]
'@
    Replace-Once $obsOld $obsNew "OBSERVATION_PROVIDER"

    Write-Host "`n==> PATCH PROVIDER EVENT" -ForegroundColor Cyan
    $eventOld = @'
class ReferenceProviderEventRequest(BaseModel):
    provider: Literal["META_GRAPH", "METRICOOL_MCP", "SCRAPER_PUBLIC", "HUMAN_SHARE", "MANUAL"]
'@
    $eventNew = @'
class ReferenceProviderEventRequest(BaseModel):
    provider: Literal["META_GRAPH", "METRICOOL_MCP", "SCRAPER_PUBLIC", "BROWSER_SESSION", "HUMAN_SHARE", "MANUAL"]
'@
    Replace-Once $eventOld $eventNew "PROVIDER_EVENT_PROVIDER"

    Write-Host "`n==> ADD DISCOVERY MODELS" -ForegroundColor Cyan
    $oldModels = @'
class ReferenceScrapePublicRequest(BaseModel):
    reference_profile_id: str
    profile_url: str
    allow_public_scraping: bool = False
    notes: str = ""
'@

    $newModels = @'
class ReferenceScrapePublicRequest(BaseModel):
    reference_profile_id: str
    profile_url: str
    allow_public_scraping: bool = False
    notes: str = ""


class ReferenceContentDiscoveryItem(BaseModel):
    content_type: Literal["REEL", "POST", "CAROUSEL", "STORY", "VIDEO"] = "REEL"
    url: str
    platform_item_id: Optional[str] = None
    caption: str = ""
    published_at: Optional[str] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    views: Optional[int] = None
    interactions: Optional[int] = None
    engagement: Optional[float] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ReferenceContentDiscoveryRequest(BaseModel):
    reference_profile_id: str
    provider: Literal["BROWSER_SESSION", "HUMAN_SHARE", "MANUAL"] = "BROWSER_SESSION"
    discovered_at: Optional[str] = None
    items: list[ReferenceContentDiscoveryItem] = Field(default_factory=list)
    create_reference_items: bool = True
    dry_run: bool = False
    notes: str = ""
'@

    Replace-Once $oldModels $newModels "DISCOVERY_MODELS"

    Write-Host "`n==> ADD BROWSER SESSION PROVIDER" -ForegroundColor Cyan
    $oldProvider = @'
    "SCRAPER_PUBLIC": {"priority": 30, "trust_weight": 0.60, "enabled": True,
                       "capabilities": ["PUBLIC_HTML", "OPEN_GRAPH", "PUBLIC_META"]},
'@

    $newProvider = @'
    "BROWSER_SESSION": {"priority": 25, "trust_weight": 0.90, "enabled": True,
                        "capabilities": ["PUBLIC_CONTENT_DISCOVERY", "PUBLIC_UI_METADATA", "URL", "NO_SECRET_PERSISTENCE"]},
    "SCRAPER_PUBLIC": {"priority": 30, "trust_weight": 0.60, "enabled": True,
                       "capabilities": ["PUBLIC_HTML", "OPEN_GRAPH", "PUBLIC_META"]},
'@

    Replace-Once $oldProvider $newProvider "BROWSER_PROVIDER"

    $readyOld = '{"HUMAN_SHARE","MANUAL","SCRAPER_PUBLIC"}'
    $readyNew = '{"HUMAN_SHARE","MANUAL","SCRAPER_PUBLIC","BROWSER_SESSION"}'
    Replace-Once $readyOld $readyNew "PROVIDER_READY_SET"

    Write-Host "`n==> ADD CONTENT DISCOVERY ENDPOINT" -ForegroundColor Cyan

    $endpointAnchor = 'def _scraper_job_path(job_id: str) -> Path:'

    $endpointCode = @'
def _reference_content_discovery_normalize_url(
    network: str,
    content_type: str,
    value: str,
    explicit_platform_item_id: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    from urllib.parse import urlparse

    raw_url = str(value or "").strip()
    parsed = urlparse(raw_url)

    if parsed.scheme != "https":
        raise HTTPException(422, "REFERENCE_CONTENT_DISCOVERY_HTTPS_REQUIRED")

    host = (parsed.hostname or "").lower()

    if network != "instagram":
        raise HTTPException(422, "REFERENCE_CONTENT_DISCOVERY_NETWORK_UNSUPPORTED")

    if host not in {"instagram.com", "www.instagram.com"}:
        raise HTTPException(422, f"REFERENCE_CONTENT_DISCOVERY_HOST_FORBIDDEN:{host}")

    path = re.sub(r"/+", "/", parsed.path or "/")
    derived_id: Optional[str] = None

    if content_type == "REEL":
        m = re.fullmatch(r"/(?:reel|reels)/([^/]+)/?", path, re.I)
        if not m:
            raise HTTPException(422, "REFERENCE_CONTENT_DISCOVERY_REEL_URL_INVALID")
        derived_id = m.group(1)

    elif content_type in {"POST", "CAROUSEL"}:
        m = re.fullmatch(r"/p/([^/]+)/?", path, re.I)
        if not m:
            raise HTTPException(422, "REFERENCE_CONTENT_DISCOVERY_POST_URL_INVALID")
        derived_id = m.group(1)

    elif content_type == "STORY":
        m = re.fullmatch(r"/stories/[^/]+/([^/]+)/?", path, re.I)
        if not m:
            raise HTTPException(422, "REFERENCE_CONTENT_DISCOVERY_STORY_URL_INVALID")
        derived_id = m.group(1)

    elif content_type == "VIDEO":
        m = re.fullmatch(r"/(?:reel|reels|tv|p)/([^/]+)/?", path, re.I)
        if m:
            derived_id = m.group(1)

    explicit_id = str(explicit_platform_item_id or "").strip() or None

    if explicit_id and derived_id and explicit_id != derived_id:
        raise HTTPException(409, "REFERENCE_CONTENT_DISCOVERY_PLATFORM_ID_MISMATCH")

    platform_item_id = explicit_id or derived_id

    if content_type == "REEL" and not platform_item_id:
        raise HTTPException(422, "REFERENCE_CONTENT_DISCOVERY_REEL_ID_REQUIRED")

    canonical_url = "https://www.instagram.com" + path
    return canonical_url, platform_item_id


@app.post("/production/reference-corpus/content-discovery/ingest")
def production_reference_content_discovery(req: ReferenceContentDiscoveryRequest):
    profile = _load_reference_profile(req.reference_profile_id)
    network = str(profile.get("network") or "")

    if network != "instagram":
        raise HTTPException(422, "REFERENCE_CONTENT_DISCOVERY_NETWORK_UNSUPPORTED")

    if not req.items:
        raise HTTPException(422, "REFERENCE_CONTENT_DISCOVERY_ITEMS_REQUIRED")

    if len(req.items) > 100:
        raise HTTPException(422, "REFERENCE_CONTENT_DISCOVERY_TOO_MANY_ITEMS")

    if not _provider_available(req.provider):
        raise HTTPException(
            503,
            f"REFERENCE_CONTENT_DISCOVERY_PROVIDER_UNAVAILABLE:{req.provider}",
        )

    handle = _reference_harvest_norm_handle(profile.get("handle"))
    discovered_at = (
        str(req.discovered_at or "").strip()
        or datetime.now(timezone.utc).isoformat()
    )

    results = []
    seen: set[tuple[str, str]] = set()
    skipped_duplicates = 0

    for candidate in req.items:
        canonical_url, platform_item_id = _reference_content_discovery_normalize_url(
            network,
            candidate.content_type,
            candidate.url,
            candidate.platform_item_id,
        )

        dedupe_key = (
            candidate.content_type,
            platform_item_id or canonical_url,
        )

        if dedupe_key in seen:
            skipped_duplicates += 1
            continue

        seen.add(dedupe_key)

        raw = dict(candidate.raw or {})
        raw.update({
            "caption": str(candidate.caption or ""),
            "discovery_contract": REFERENCE_CONTENT_DISCOVERY_CONTRACT_VERSION,
            "discovery_provider": req.provider,
            "discovered_at": discovered_at,
            "canonical_url": canonical_url,
            "session_secret_persisted_by_worker": False,
            "captcha_bypass_used_by_worker": False,
            "anti_bot_evasion_used_by_worker": False,
            "remote_media_download_attempted": False,
        })

        obs_request = ReferenceObservationRequest(
            reference_profile_id=req.reference_profile_id,
            network=network,
            handle=handle,
            content_type=candidate.content_type,
            platform_item_id=platform_item_id,
            url=canonical_url,
            provider=req.provider,
            fetched_at=discovered_at,
            published_at=candidate.published_at,
            likes=candidate.likes,
            comments=candidate.comments,
            views=candidate.views,
            interactions=candidate.interactions,
            engagement=candidate.engagement,
            raw=raw,
            notes=(str(req.notes or "") + " | CONTENT_DISCOVERY").strip(" |"),
        )

        normalized_observation = _normalize_observation(obs_request)

        if req.dry_run:
            observation = {
                **normalized_observation,
                "reused_existing": False,
                "dry_run": True,
            }
        else:
            observation = _persist_observation(normalized_observation)

        reference_item = None

        if req.create_reference_items:
            item_identity = {
                "reference_profile_id": req.reference_profile_id,
                "network": network,
                "item_type": candidate.content_type,
                "platform_item_id": platform_item_id,
                "url": canonical_url,
            }

            reference_item_id = "RI_" + _canonical_sha256(item_identity)[:32]

            if req.dry_run:
                reference_item = {
                    "reference_item_id": reference_item_id,
                    "contract_version": REFERENCE_ITEM_CONTRACT_VERSION,
                    **item_identity,
                    "reused_existing": False,
                    "dry_run": True,
                }
            else:
                item_path = _reference_item_path(
                    req.reference_profile_id,
                    reference_item_id,
                )

                if item_path.exists():
                    reference_item = {
                        **_load_reference_item(reference_item_id),
                        "reused_existing": True,
                    }
                else:
                    item_source = (
                        "BROWSER_SESSION"
                        if req.provider == "BROWSER_SESSION"
                        else "MANUAL_URL"
                    )

                    reference_item = production_reference_item(
                        ReferenceItemRequest(
                            reference_profile_id=req.reference_profile_id,
                            network=network,
                            item_type=candidate.content_type,
                            platform_item_id=platform_item_id,
                            url=canonical_url,
                            caption=candidate.caption,
                            published_at=candidate.published_at,
                            source=item_source,
                            notes="REFERENCE_CONTENT_DISCOVERY_V1",
                        )
                    )

        results.append({
            "content_type": candidate.content_type,
            "canonical_url": canonical_url,
            "platform_item_id": platform_item_id,
            "observation": observation,
            "reference_item": reference_item,
        })

    if not req.dry_run:
        production_reference_provider_event(
            ReferenceProviderEventRequest(
                provider=req.provider,
                event="SUCCESS",
                notes="REFERENCE_CONTENT_DISCOVERY_INGEST",
            )
        )

    return {
        "ok": True,
        "contract_version": REFERENCE_CONTENT_DISCOVERY_CONTRACT_VERSION,
        "reference_profile_id": req.reference_profile_id,
        "network": network,
        "handle": handle,
        "provider": req.provider,
        "dry_run": req.dry_run,
        "count": len(results),
        "skipped_duplicates": skipped_duplicates,
        "results": results,
        "reference_items_created_or_reused": req.create_reference_items,
        "remote_media_download_attempted": False,
        "session_secret_persisted_by_worker": False,
        "captcha_bypass_used_by_worker": False,
        "anti_bot_evasion_used_by_worker": False,
    }


def _scraper_job_path(job_id: str) -> Path:
'@

    Replace-Once $endpointAnchor $endpointCode "DISCOVERY_ENDPOINT"

    Write-Host "`n==> PATCH HEALTH" -ForegroundColor Cyan

    $oldHealth = @'
        "reference_public_scraper_anti_bot_evasion": False,
'@

    $newHealth = @'
        "reference_public_scraper_anti_bot_evasion": False,
        "reference_content_discovery": True,
        "reference_content_discovery_contract": REFERENCE_CONTENT_DISCOVERY_CONTRACT_VERSION,
        "reference_content_discovery_browser_session_provider": True,
        "reference_content_discovery_browser_collector_bundled": False,
        "reference_content_discovery_creates_reference_items": True,
        "reference_content_discovery_remote_media_download": False,
        "reference_content_discovery_session_secret_persisted": False,
        "reference_content_discovery_captcha_bypass": False,
        "reference_content_discovery_anti_bot_evasion": False,
'@

    Replace-Once $oldHealth $newHealth "HEALTH_DISCOVERY"

    Write-Host "`n==> WRITE PATCHED WORKER" -ForegroundColor Cyan

    [System.IO.File]::WriteAllText(
        $target,
        $code,
        [System.Text.UTF8Encoding]::new($false)
    )

    $release = Join-Path $root "SM3_worker_service_2_19_0.py"
    Copy-Item $target $release -Force

    Write-Host "`n==> VERIFY REQUIRED MARKERS" -ForegroundColor Cyan

    $verify = [System.IO.File]::ReadAllText($target)
    $required = @(
        'WORKER_VERSION = "2.19.0"',
        'SM3_REFERENCE_CONTENT_DISCOVERY_V1',
        'class ReferenceContentDiscoveryRequest',
        '"/production/reference-corpus/content-discovery/ingest"',
        '"BROWSER_SESSION"',
        '"reference_content_discovery": True'
    )

    foreach ($marker in $required) {
        if (-not $verify.Contains($marker)) {
            Fail "VERIFY_MARKER_MISSING:$marker"
        }
        Write-Host "OK: $marker" -ForegroundColor Green
    }

    Write-Host "`n==> PYTHON SYNTAX CHECK USING CURRENT CONTAINER" -ForegroundColor Cyan

    $tempContainerFile = "/tmp/SM3_worker_service_2_19_0.py"

    & docker cp $target "${container}:$tempContainerFile"
    if ($LASTEXITCODE -ne 0) {
        Fail "DOCKER_CP_FOR_SYNTAX_CHECK_FAILED"
    }

    & docker exec $container python -m py_compile $tempContainerFile
    $compileExit = $LASTEXITCODE

    & docker exec $container rm -f $tempContainerFile | Out-Null

    if ($compileExit -ne 0) {
        Fail "PYTHON_SYNTAX_CHECK_FAILED"
    }

    Write-Host "`n============================================" -ForegroundColor Green
    Write-Host " SM3 09C3 SOURCE INSTALL PASS" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "Worker source : 2.19.0"
    Write-Host "Contract      : SM3_REFERENCE_CONTENT_DISCOVERY_V1"
    Write-Host "Backup        : $backupDir"
    Write-Host "Release copy  : $release"
    Write-Host "Syntax        : PASS"
    Write-Host ""
    Write-Host "NOT BUILT YET - running container remains 2.18.0" -ForegroundColor Yellow
}
catch {
    Write-Host "`n==> INSTALL FAILED - ROLLING BACK SOURCE" -ForegroundColor Red

    if (Test-Path $backupFile) {
        Copy-Item $backupFile $target -Force
    }

    $release = Join-Path $root "SM3_worker_service_2_19_0.py"
    Remove-Item $release -Force -ErrorAction SilentlyContinue

    Write-Host "Rollback source: DONE" -ForegroundColor Yellow
    throw
}
