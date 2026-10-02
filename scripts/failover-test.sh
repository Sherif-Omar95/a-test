#!/usr/bin/env bash
# Force an RDS Multi-AZ failover and measure how long the application is
# without a database. The endpoint name never changes; DNS moves to the standby.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/common.sh

URL="$(output ApplicationUrl)"
DB="$(output DatabaseIdentifier)"
probe() { curl -s --max-time 8 "$URL/api/info" | python3 -c 'import sys,json
try:
    d=json.load(sys.stdin); print(d["db_host"] if d["ok"] else "DB-DOWN")
except Exception: print("NO-RESPONSE")'; }

before="$(probe)"
echo "Database server before failover: $before"
aws rds describe-db-instances --region "$REGION" --db-instance-identifier "$DB" \
  --query "DBInstances[0].[AvailabilityZone,SecondaryAvailabilityZone]" --output text
aws rds reboot-db-instance --region "$REGION" --db-instance-identifier "$DB" --force-failover >/dev/null
start=$(date +%s)
echo "Failover requested at $(date -u +%H:%M:%S)"

while true; do
  now="$(probe)"
  echo "$(date -u +%H:%M:%S)  +$(( $(date +%s) - start ))s  $now"
  if [ "$now" != "DB-DOWN" ] && [ "$now" != "NO-RESPONSE" ] && [ "$now" != "$before" ]; then break; fi
  sleep 5
done
echo "Recovered on a different server after $(( $(date +%s) - start )) seconds."
aws rds describe-db-instances --region "$REGION" --db-instance-identifier "$DB" \
  --query "DBInstances[0].[AvailabilityZone,SecondaryAvailabilityZone]" --output text
