# Project Notes

## Testing

### Testing the Orchestrator Lambda
In the AWS Lambda console, open `event-calendar-scraper-orchestrator`, go to **Test**, and use:

```json
{ "test_mode": true }
```

This runs all scrapers, diffs against snapshots, and sends the results email only to `dylanclark2396@gmail.com` instead of the full recipient list.

To target specific scrapers only:
```json
{ "test_mode": true, "calendar_ids": ["javits", "occc"] }
```

To target specific scrapers and force all their events into the email:
```json
{ "test_mode": true, "force_all": true, "calendar_ids": ["javits", "occc"] }
```

To force all scraped events into the email (useful for verifying scrapers are working, ignores snapshot diff):
```json
{ "test_mode": true, "force_all": true }
```

To do a full production-style test (sends to all recipients):
```json
{}
```

---

### Testing the Snapshot Diff Lambda
In the AWS Lambda console, open `event-calendar-scraper-snapshot-diff`, go to **Test**.

**Diff the two most recent snapshots for a calendar:**
```json
{ "calendar_id": "javits" }
```

**Diff two specific versions** (use version IDs from the `available_versions` field in a previous response):
```json
{
  "calendar_id": "javits",
  "version_id_old": "abc123...",
  "version_id_new": "def456..."
}
```

The response includes `added`, `removed`, and `available_versions` — the full list of S3 version IDs with timestamps so you can pick any two to compare.

Valid `calendar_id` values: `javits`, `gicc`, `gwcca`, `signature_boston`, `dallas_cc`, `lacc`, `miami_beach_cc`, `nashville_mcc`, `occc`, `phoenix_cc`, `san_diego_cc`, `vegas_lvcva`

---

## Scrapers

### Headless Scrapers (Playwright)
Three scrapers use Playwright with a Chromium Lambda Layer because their sites are JS-rendered or block direct requests from AWS IPs:
- **GWCCA** (`gwcca.org/event-calendar`) — Vue.js SSR; site blocks non-browser fetches (403). Captures `page.content()` for HTML parsing.
- **OCCC** (`events.occc.net`) — Vue.js + Ungerboeck; intercepts REST API response. Token is runtime-computed, direct API returns 403.
- **Vegas** (`vegasmeansbusiness.com/destination-calendar`) — Simpleview widget; intercepts API response. Direct API confirmed working from browser but **times out from Lambda** (AWS IPs blocked).

The Chromium binary comes from the `sparticuz/chromium` Lambda Layer. Worker Lambda is **2048MB / 300s timeout** (Chromium needs ~700MB just to start).

#### Setting Up the Playwright Lambda Layer
1. Go to https://github.com/Sparticuz/chromium/releases
2. Download the latest `chromium-vXX.X.X-layer.zip`
3. In AWS Console → Lambda → Layers → Create layer, upload the zip (compatible runtime: python3.12, arch: x86_64)
4. Copy the Layer ARN
5. Add it as a GitHub Actions secret: `PLAYWRIGHT_LAYER_ARN`
6. Redeploy bootstrap stack (added `lambda:GetLayerVersion` permission), then push to main

#### Chromium on Lambda — Key Findings

Lambda's seccomp policy blocks Linux namespace/credential syscalls. The fix requires a specific set of flags — do not change these without good reason:

```python
LAUNCH_ARGS = [
    "--headless=old",      # old headless = no GPU compositing needed
    "--no-sandbox",
    "--no-zygote",         # skip zygote; it calls credentials.cc which Lambda blocks
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",       # no GPU subprocess; combined with headless=old this works
    ...
]
# IMPORTANT: launch with headless=False so Playwright doesn't prepend --headless (new mode)
browser = p.chromium.launch(executable_path=chromium_path, headless=False, args=LAUNCH_ARGS)
```

**Flags that BREAK things on Lambda (do not add):**
- `--single-process` — unstable in Chromium 110+, causes TargetClosedError
- `--use-gl=angle --use-angle=swiftshader` — requires GPU process which Lambda blocks
- `--disable-gpu` alone with `--use-gl=angle` — GPU process disabled but ANGLE still needs it

**Root crash causes we diagnosed:**
1. `FATAL:credentials.cc: Check failed: Operation not permitted` → zygote trying to set up GPU process sandbox; fixed by `--no-zygote --disable-gpu`
2. `TargetClosedError: Browser.new_page` → browser exits immediately; caused by conflicting flags (e.g. `--disable-gpu` + `--use-gl=angle`)
3. `Page crashed` during Vue.js rendering → renderer subprocess hits same seccomp restrictions; fix is resource blocking (`page.route`) and/or switching to API interception instead of DOM scraping

**Resource blocking** (reduces renderer crash risk on heavy JS pages):
```python
page.route("**/*.{png,jpg,jpeg,gif,svg,webp,ico,woff,woff2,ttf,mp4,mp3}", lambda r: r.abort())
page.route("**/*.css", lambda r: r.abort())
```
Use on OCCC and GWCCA. Do NOT use on Vegas (causes crashes there).

**Per-scraper wait strategy:**
- **OCCC**: `wait_until="domcontentloaded"` + resource blocking + try/except. The widget's API call fires before the renderer crash; domcontentloaded fires early enough to catch it.
- **GWCCA**: `wait_until="domcontentloaded"` + resource blocking. Captures `page.content()` immediately after goto (before Vue hydration can crash the renderer), then parses SSR HTML via JSON-LD → embedded window state → DOM heuristics. API interception is also attempted but has returned 0 results (likely pure SSR, no XHR).
- **Vegas**: `wait_until="load"` + NO resource blocking + 8s wait + 5 scroll iterations + try/except. Direct API calls **time out from Lambda** (AWS egress IPs are blocked by the site) — do not attempt direct `requests` calls for Vegas.

**Layer setup:** sparticuz/chromium layer is a Node.js npm package at `/opt/nodejs/node_modules/@sparticuz/chromium/bin/`. The `prepare_chromium()` function in `scrapers/_playwright.py` handles decompression of `chromium.br`, `al2023.tar.br` (NSS/NSPR libs → `/tmp/lib/`), `swiftshader.tar.br` (→ `/tmp/`), and `fonts.tar.br`. It also sets `HOME=/tmp`, `VK_ICD_FILENAMES=/tmp/vk_swiftshader_icd.json`, and `LD_LIBRARY_PATH`.

#### Selector Maintenance
OCCC uses API response interception (intercepts `plugins_events_events_by_date/find`). Vegas uses API interception with scroll pagination. GWCCA uses `page.content()` HTML parsing — if 0 events are returned, CloudWatch logs will dump the first 2000 chars of page HTML; use that to identify the current element structure.

### Other Scrapers

**Miami Beach Convention Center**
- ✅ Uses cloudscraper directly against `https://www.miamibeachconvention.com/events` (static HTML, Cloudflare bypassed)

## Infrastructure

### IAM / Permissions
When adding new AWS resources (Lambda functions, IAM roles, S3 buckets, EventBridge rules, etc.),
always check `infra/bootstrap.yml` to see if the GitHub deploy role's resource ARNs need to be
updated. The deploy role uses explicit ARNs or patterns — new resource names outside those patterns
will cause `AccessDenied` errors during CloudFormation deployment.

Checklist when adding a new resource:
- Does it create a new IAM role? → update `IAMLambdaRole` and `PassLambdaRole` resource ARNs
- Does it create a new Lambda function? → update `LambdaFunction` resource ARNs
- Does it create a new S3 bucket? → update `S3SnapshotBucket` resource ARNs
- Does it create a new EventBridge rule? → update `EventBridgeSchedule` resource ARNs

After updating `bootstrap.yml`, the bootstrap stack must be redeployed before the app stack:
```bash
aws cloudformation deploy \
  --stack-name event-calendar-scraper-bootstrap \
  --template-file infra/bootstrap.yml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides GitHubOrg=<your-org> OIDCProviderArn=<oidc-arn>
```
