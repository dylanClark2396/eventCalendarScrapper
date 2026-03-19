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
Three scrapers use Playwright with a Chromium Lambda Layer because their sites are JS-rendered:
- **GWCCA** (`gwcca.org/event-calendar`) — Vue.js rendered, direct site
- **OCCC** (`events.occc.net`) — Vue.js + Ungerboeck, intercepts REST API response
- **Vegas** (`vegasmeansbusiness.com/destination-calendar`) — Simpleview widget, intercepts API response

The Chromium binary comes from the `sparticuz/chromium` Lambda Layer. Worker Lambda is 1024MB / 180s timeout.

#### Setting Up the Playwright Lambda Layer
1. Go to https://github.com/Sparticuz/chromium/releases
2. Download the latest `chromium-vXX.X.X-layer.zip`
3. In AWS Console → Lambda → Layers → Create layer, upload the zip (compatible runtime: python3.12, arch: x86_64)
4. Copy the Layer ARN
5. Add it as a GitHub Actions secret: `PLAYWRIGHT_LAYER_ARN`
6. Redeploy bootstrap stack (added `lambda:GetLayerVersion` permission), then push to main

#### Selector Maintenance
GWCCA's scraper uses CSS selectors against the rendered DOM — if the site redesigns, selectors in `scrapers/gwcca.py` may need updating. OCCC and Vegas use API response interception which is more stable.

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
