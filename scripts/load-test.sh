#!/usr/bin/env bash
# Drive CPU on every web instance through SSM Run Command (no SSH), then watch
# the Auto Scaling group react. Usage: ./scripts/load-test.sh [minutes]
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

MINUTES="${1:-12}"
ASG="$(output AutoScalingGroupName)"

echo "Starting a ${MINUTES}-minute CPU burn on the instances in $ASG"
PARAMS=$(python3 - "$MINUTES" <<'PY'
import json, sys
seconds = int(sys.argv[1]) * 60
burn = f"timeout {seconds} bash -c 'for c in $(seq $(nproc)); do (while :; do :; done) & done; wait' || true"
print(json.dumps({"commands": [burn], "executionTimeout": [str(seconds + 120)]}))
PY
)
aws ssm send-command --region "$REGION" \
  --document-name AWS-RunShellScript \
  --targets "Key=tag:aws:autoscaling:groupName,Values=$ASG" \
  --comment "load test" \
  --parameters "$PARAMS" \
  --query "Command.CommandId" --output text

echo "Watching the group (Ctrl+C to stop). Target tracking needs about 3-5 minutes of high CPU."
while true; do
  aws autoscaling describe-auto-scaling-groups --region "$REGION" \
    --auto-scaling-group-names "$ASG" \
    --query "AutoScalingGroups[0].[DesiredCapacity, length(Instances[?LifecycleState=='InService'])]" \
    --output text | awk -v t="$(date -u +%H:%M:%S)" '{print t"  desired="$1"  in-service="$2}'
  sleep 30
done
