#!/usr/bin/env bash
# Create or update the stack, then upload the static assets to S3.
#   ALERT_EMAIL=you@example.com ./scripts/deploy.sh
#   ./scripts/deploy.sh NatGatewayMode=per-az MaxSize=8     (extra parameter overrides)
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

python3 scripts/embed_app.py

echo "Deploying stack $STACK to $REGION (first run takes 20-30 minutes: RDS Multi-AZ and CloudFront)"
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK" \
  --template-file infrastructure/main.yaml \
  --capabilities CAPABILITY_IAM \
  --tags Project="$STACK" Environment=demo \
  --parameter-overrides ProjectName="$STACK" AlertEmail="${ALERT_EMAIL:-}" "$@"

BUCKET="$(output StaticBucketName)"
aws s3 sync app/static "s3://$BUCKET/static/" --delete --region "$REGION" \
  --cache-control "public, max-age=86400"

aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table
echo
echo "Open: $(output ApplicationUrl)"
[ -n "${ALERT_EMAIL:-}" ] && echo "Confirm the SNS subscription email sent to $ALERT_EMAIL."
exit 0
