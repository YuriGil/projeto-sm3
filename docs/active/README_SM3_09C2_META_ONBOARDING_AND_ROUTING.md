# SM3 09C.2 — Meta onboarding + automatic fallback

**No Worker rebuild is required.** This stage uses Worker 2.18.0.

## Purpose

09C.1 created provider abstraction, immutable observations, consensus,
circuit breakers, and the public scraper foundation.

09C.2 makes the first real Meta Graph probe and routes unsupported profiles
automatically to SCRAPER_PUBLIC.

## Official Meta path used

Graph API version: `v26.0`

The Meta Instagram API with Facebook Login is intended for Instagram Professional
accounts and requires a Facebook Page linked to a professional Instagram account.
Business Discovery is used to get basic public metadata/media for other
professional accounts.

## Diagnostic first

Run:

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\SM3_09C2_META_ONBOARDING_DIAGNOSTICO.ps1"
```

The script asks for a Meta USER access token as SecureString and never persists it.

It:
- calls `/me/accounts`;
- discovers Pages with linked Instagram professional accounts;
- keeps the Page Access Token only in memory;
- tests Business Discovery on `gogoo.ink` by default;
- prints only safe IDs and counts.

To probe a different reference:

```powershell
.\SM3_09C2_META_ONBOARDING_DIAGNOSTICO.ps1 -ProbeHandle "brandochiesa"
```

## n8n

Import:

`workflows/active/PROJETO_SM3_09C2_META_ELIGIBILITY_FALLBACK_ROUTER_v1.json`

Then:

1. Open `CONFIG — META 09C.2`.
2. Set `preferred_page_id` to the Page ID returned by the diagnostic.
3. Leave `profile_probe_limit = 5` for the first test.
4. On `META — DISCOVER LINKED PAGE`, create/select an HTTP Header Auth credential:
   - Header: `Authorization`
   - Value: `Bearer <USER ACCESS TOKEN>`

Never put the token in Sheets, JSON, Set nodes or notes.

The workflow is configured not to save execution data because `/me/accounts`
returns a Page Access Token transiently.

## Automatic route

If Meta Business Discovery works:

- `META_ELIGIBILITY = ELIGIBLE`
- PROFILE + REEL data becomes `SM3_REFERENCE_OBSERVATION_V1`
- the canonical Worker stores it
- 40_REFERENCE_OBSERVATIONS is mirrored
- REEL observations may be auto-harvested by the existing 09C scorer

If Meta is unavailable for a profile:

- `META_ELIGIBILITY = UNAVAILABLE`
- `PROVIDER_STATUS = SCRAPER_FALLBACK`
- Worker invokes the existing `SCRAPER_PUBLIC` foundation
- 41_REFERENCE_SCRAPER_QUEUE records the attempt

The public scraper remains public-only:
no login automation, private cookies, CAPTCHA bypass or anti-bot evasion.

## Watchdog

Import:

`workflows/active/PROJETO_SM3_09C2_PROVIDER_WATCHDOG_v1.json`

It mirrors current provider/circuit-breaker state into 39_REFERENCE_PROVIDER_STATE.

## First test

Do not enable a schedule yet.

Run the Meta router manually with `profile_probe_limit = 5`.
Then inspect:
- 31_REFERENCE_PROFILES
- 40_REFERENCE_OBSERVATIONS
- 41_REFERENCE_SCRAPER_QUEUE
- 39_REFERENCE_PROVIDER_STATE

After that, increase to 23 profiles.
