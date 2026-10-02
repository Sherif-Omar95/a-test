#!/usr/bin/env bash
# Functional checks against the deployed stack. Each line prints PASS or FAIL.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
source scripts/common.sh

URL="$(output ApplicationUrl)"
ALB="$(output AlbDnsName)"
fails=0
check() { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $3, got $2)"; fails=$((fails+1)); fi; }
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

check "health check through CloudFront returns 200" "$(status "$URL/health")" 200

instances=$(for _ in $(seq 1 20); do
  curl -s -D - -o /dev/null "$URL/" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-served-by"{print $2}'
done | sort -u)
count=$(echo "$instances" | grep -c '^i-' || true)
echo "      20 requests were answered by $count instance(s): $(echo "$instances" | tr '\n' ' ')"
if [ "$count" -ge 2 ]; then echo "PASS  load is spread across instances"; else echo "FAIL  only one instance answered"; fails=$((fails+1)); fi

curl -s -o /dev/null "$URL/static/style.css"
cache=$(curl -s -D - -o /dev/null "$URL/static/style.css" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-cache"{print $2}')
check "static asset served from CloudFront cache" "$cache" "Hit from cloudfront"

check "direct request to the ALB is blocked by WAF" "$(status "http://$ALB/")" 403
check "/admin is rejected by the ALB listener rule" "$(status "$URL/admin")" 403
check "SQL injection attempt is blocked by WAF" "$(status "$URL/?id=1%27%20OR%20%271%27=%271")" 403
check "HTTP is redirected to HTTPS" "$(status "http://${URL#https://}/")" 301

info=$(curl -s "$URL/api/info")
check "web tier reaches the database" "$(echo "$info" | python3 -c 'import sys,json;print(json.load(sys.stdin)["ok"])')" True
echo "      database server: $(echo "$info" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("db_host"), "TLS", d.get("tls_cipher"))')"

echo
[ "$fails" -eq 0 ] && echo "All checks passed." || echo "$fails check(s) failed."
exit "$fails"
