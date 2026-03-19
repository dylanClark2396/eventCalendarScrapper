# Project Notes

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
