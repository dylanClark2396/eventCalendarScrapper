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

Valid `calendar_id` values: `javits`, `gicc`, `signature_boston`, `dallas_cc`, `lacc`, `nashville_mcc`, `occc`, `phoenix_cc`, `san_diego_cc`, `vegas_lvcva`

---

## Scrapers

### Sites That Could Not Be Scraped

**GWCCA — Georgia World Congress Authority**
- URL: https://www.gwcca.org/event-calendar
- Problem: Returns 403 Forbidden — server blocks non-browser requests
- Workaround: Try rotating User-Agent strings or adding browser-like headers (Accept, Referer, etc.). If still blocked, use Playwright/Selenium to render in a real browser. Last resort: contact GWCCA for a data feed.

**Miami Beach Convention Center**
- URL: https://www.miamibeachconvention.com/events
- Problem: Returns 403 Forbidden — server blocks non-browser requests
- Workaround: Same as GWCCA — try more realistic headers first, then Playwright if needed.

**Orange County Convention Center (OCCC)**
- ✅ Resolved — uses public RSS feed at `https://events.occc.net/event/rss/`

**Vegas Means Business**
- ✅ Resolved — uses public RSS feed at `https://www.vegasmeansbusiness.com/event/rss/`, filtered to convention events only (`/conventions_` in link URL)

### Adding Playwright/Selenium Support
If a headless browser approach is needed, Lambda does not support Chromium out of the box.
Options:
- Use a Lambda Layer with a pre-built Chromium binary (e.g., `chrome-aws-lambda` or `playwright-aws-lambda`)
- Run the JS-dependent scrapers in a separate Lambda with a larger memory/timeout allocation
- Use AWS Fargate for scrapers that need a full browser

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
