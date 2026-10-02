#!/usr/bin/env bash
# Delete everything. The bucket is emptied first because CloudFormation cannot
# delete a bucket that still has objects in it.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

BUCKET="$(output StaticBucketName 2>/dev/null || true)"
if [ -n "$BUCKET" ] && [ "$BUCKET" != "None" ]; then
  aws s3 rm "s3://$BUCKET" --recursive --region "$REGION"
fi
aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK"
echo "Deleting $STACK (CloudFront and RDS take 10-20 minutes)..."
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK"
echo "Deleted."
