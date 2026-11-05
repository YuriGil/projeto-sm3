# SM3 08C - Diagnose HTTP 502 at semantic-geometry provider boundary
# Read-only with respect to SM3 state: no revisions, geometry records, or Sheets are written.
# It performs provider probes from inside the media-worker container.

[CmdletBinding()]
param(
    [string]$ProjectRoot = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$ComposeBase = Join-Path $ProjectRoot 'deployment\docker-compose.yml'
$ComposeWorker = Join-Path $ProjectRoot 'deployment\docker-compose.worker.yml'

foreach ($p in @($ComposeBase,$ComposeWorker)) {
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
        throw "SM3_08C_DIAG_REQUIRED_FILE_NOT_FOUND: $p"
    }
}

$compose = @('-f',$ComposeBase,'-f',$ComposeWorker)

Write-Host "== SM3 08C / DIAGNOSTICO 502 =="
Write-Host "This does NOT create a new revision and does NOT persist semantic geometry."
Write-Host ""

$health = Invoke-RestMethod -Uri 'http://localhost:8090/health' -TimeoutSec 15
Write-Host ("worker_version              : " + [string]$health.version)
Write-Host ("semantic_geometry_contract  : " + [string]$health.semantic_geometry_contract)
Write-Host ("vision_provider             : " + [string]$health.vision_provider)
Write-Host ("vision_model                : " + [string]$health.vision_model)
Write-Host ""

$probe = @'
import json, os, sys, traceback
from pathlib import Path
import httpx

def out(label, value):
    print(f"{label}: {value}", flush=True)

def body_snip(resp, n=5000):
    try:
        text = resp.text
    except Exception:
        return "<unreadable>"
    # API errors should not contain the Authorization secret, but redact common accidental forms anyway.
    key = os.environ.get("OPENAI_API_KEY","")
    if key:
        text = text.replace(key, "<REDACTED_API_KEY>")
    return text[-n:]

key = os.environ.get("OPENAI_API_KEY","")
base = os.environ.get("OPENAI_BASE_URL","https://api.openai.com/v1").rstrip("/")
model = os.environ.get("VISION_MODEL","")
timeout = float(os.environ.get("VISION_TIMEOUT_SECONDS","180"))

out("OPENAI_API_KEY_CONFIGURED", bool(key))
out("OPENAI_BASE_URL", base)
out("VISION_MODEL", model)
out("VISION_TIMEOUT_SECONDS", timeout)

if not key:
    print("SM3_08C_DIAG_RESULT=API_KEY_MISSING")
    sys.exit(20)

headers = {
    "Authorization": "Bearer " + key,
    "Content-Type": "application/json",
    "X-Client-Request-Id": "sm3-08c-diagnostic-provider-probe",
}

# Probe A: auth/network only.
try:
    with httpx.Client(timeout=30) as c:
        r = c.get(base + "/models", headers={"Authorization":"Bearer " + key, "X-Client-Request-Id":"sm3-08c-diag-auth"})
    out("PROBE_A_MODELS_STATUS", r.status_code)
    out("PROBE_A_REQUEST_ID", r.headers.get("x-request-id",""))
    if r.status_code >= 400:
        out("PROBE_A_BODY", body_snip(r))
        print("SM3_08C_DIAG_RESULT=AUTH_OR_PROVIDER_ACCESS_FAILED")
        sys.exit(21)
except Exception as e:
    out("PROBE_A_EXCEPTION", f"{type(e).__name__}:{e}")
    print("SM3_08C_DIAG_RESULT=NETWORK_FAILED")
    sys.exit(22)

# Probe B: model + Responses API, text only.
simple_payload = {
    "model": model,
    "input": "Return exactly the word OK.",
    "max_output_tokens": 32,
}
try:
    with httpx.Client(timeout=60) as c:
        r = c.post(base + "/responses", headers=headers, json=simple_payload)
    out("PROBE_B_RESPONSES_STATUS", r.status_code)
    out("PROBE_B_REQUEST_ID", r.headers.get("x-request-id",""))
    if r.status_code >= 400:
        out("PROBE_B_BODY", body_snip(r))
        print("SM3_08C_DIAG_RESULT=MODEL_OR_RESPONSES_FAILED")
        sys.exit(23)
except Exception as e:
    out("PROBE_B_EXCEPTION", f"{type(e).__name__}:{e}")
    print("SM3_08C_DIAG_RESULT=RESPONSES_NETWORK_FAILED")
    sys.exit(24)

# Locate/import live worker code. uvicorn must already be importing this module.
try:
    import worker_service as w
except Exception as e:
    out("WORKER_IMPORT_EXCEPTION", f"{type(e).__name__}:{e}")
    print("SM3_08C_DIAG_RESULT=LIVE_WORKER_IMPORT_FAILED")
    sys.exit(25)

asset = Path("/data/media/proxies/TATTOO_0002/M0083.jpg")
if not asset.exists():
    out("M0083_ANALYSIS_ASSET", "MISSING:" + str(asset))
    print("SM3_08C_DIAG_RESULT=ANALYSIS_ASSET_MISSING")
    sys.exit(26)

out("M0083_ANALYSIS_ASSET", str(asset))
out("M0083_ANALYSIS_ASSET_BYTES", asset.stat().st_size)

# Probe C: exact semantic schema + real M0083 proxy, but NO SM3 persistence.
payload = {
    "model": w.VISION_MODEL,
    "input": [{
        "role": "user",
        "content": [
            {
                "type": "input_text",
                "text": (
                    "Analyze this tattoo image conservatively for semantic geometry. "
                    "Use normalized 0..1 coordinates. The tattoo is the protected subject. "
                    "Return strictly the requested schema. If no overlay-safe region exists, "
                    "return an empty overlay_candidate_regions array."
                )
            },
            {
                "type": "input_image",
                "image_url": w._image_data_url(asset),
                "detail": "high",
            },
        ],
    }],
    "text": {
        "format": {
            "type": "json_schema",
            "name": "sm3_semantic_geometry_diag",
            "description": "Diagnostic execution of the live SM3 semantic geometry schema.",
            "schema": w.SEMANTIC_GEOMETRY_SCHEMA,
            "strict": True,
        }
    },
    "max_output_tokens": 5000,
}

try:
    with httpx.Client(timeout=timeout) as c:
        r = c.post(
            w.OPENAI_BASE_URL.rstrip("/") + "/responses",
            headers={
                "Authorization": "Bearer " + w.OPENAI_API_KEY,
                "Content-Type": "application/json",
                "X-Client-Request-Id": "sm3-08c-diag-full-semantic-schema",
            },
            json=payload,
        )
    out("PROBE_C_FULL_SCHEMA_STATUS", r.status_code)
    out("PROBE_C_REQUEST_ID", r.headers.get("x-request-id",""))
    if r.status_code >= 400:
        out("PROBE_C_BODY", body_snip(r))
        if r.status_code == 400:
            print("SM3_08C_DIAG_RESULT=FULL_SCHEMA_PROVIDER_400")
        elif r.status_code == 401:
            print("SM3_08C_DIAG_RESULT=PROVIDER_401")
        elif r.status_code == 403:
            print("SM3_08C_DIAG_RESULT=PROVIDER_403")
        elif r.status_code == 429:
            print("SM3_08C_DIAG_RESULT=PROVIDER_429")
        elif r.status_code >= 500:
            print("SM3_08C_DIAG_RESULT=PROVIDER_5XX")
        else:
            print("SM3_08C_DIAG_RESULT=FULL_SCHEMA_PROVIDER_ERROR")
        sys.exit(27)

    data = r.json()
    text = w._extract_response_text(data)
    out("PROBE_C_RESPONSE_ID", data.get("id",""))
    out("PROBE_C_OUTPUT_CHARS", len(text))
    try:
        raw = json.loads(text)
        compiled = w._compile_semantic_geometry(raw, {
            "tattoo_bbox_norm": {"x":0.13,"y":0.13,"w":0.67,"h":0.84,"reliability":87},
            "structural_confidence": 89,
        })
        out("PROBE_C_JSON_PARSE", "PASS")
        out("PROBE_C_COMPILE", "PASS")
        out("PROBE_C_COMPILED_STATUS", compiled.get("status"))
        out("PROBE_C_COMPILED_CONFIDENCE", compiled.get("geometry_confidence"))
    except Exception as e:
        out("PROBE_C_LOCAL_COMPILE_EXCEPTION", f"{type(e).__name__}:{e}")
        out("PROBE_C_OUTPUT", text[:4000])
        print("SM3_08C_DIAG_RESULT=PROVIDER_OK_LOCAL_COMPILE_FAILED")
        sys.exit(28)

except Exception as e:
    out("PROBE_C_EXCEPTION", f"{type(e).__name__}:{e}")
    traceback.print_exc()
    print("SM3_08C_DIAG_RESULT=FULL_SCHEMA_NETWORK_OR_TIMEOUT")
    sys.exit(29)

print("SM3_08C_DIAG_RESULT=ALL_PROVIDER_PROBES_PASS")
'@

Push-Location $ProjectRoot
try {
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $probe | & docker compose @compose exec -T media-worker python -
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
}
finally {
    Pop-Location
}

Write-Host ""
if ($code -eq 0) {
    Write-Host "SM3_08C_DIAGNOSTIC_PASS"
    Write-Host "The provider boundary and full semantic schema work. The original 502 was likely transient or request-specific."
}
else {
    Write-Host ("SM3_08C_DIAGNOSTIC_CLASSIFIED_FAILURE exit_code=" + $code)
    Write-Host "Copy the diagnostic output above exactly; it contains the provider's real error without printing the API key."
    exit $code
}
