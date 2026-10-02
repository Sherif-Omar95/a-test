# Test plan and evidence

Run the tests in this order after `deploy.sh` finishes. Each test lists what to capture for the project submission; save screenshots in `docs/screenshots/` with the file names given.

## 1. Application and load balancing

```bash
./scripts/verify.sh
```

Expected output: every line `PASS`.

| Check | Why it matters |
| --- | --- |
| Health check through CloudFront returns 200 | The full path CloudFront, WAF, ALB, EC2 works |
| Load is spread across instances | The ALB distributes requests across both AZs |
| Static asset served from CloudFront cache | `/static/*` comes from S3 and is cached at the edge |
| Direct request to the ALB is blocked | Origin lockdown: the ALB only accepts traffic from CloudFront |
| `/admin` rejected by the listener rule | Layer 7 routing at the ALB |
| SQL injection blocked | WAF managed rule set |
| HTTP redirected to HTTPS | Viewer protocol policy on CloudFront |
| Web tier reaches the database | Security group chain, Secrets Manager access, TLS to RDS |

Capture:

- `01-app-az-a.png`, `02-app-az-b.png`: the application page showing two different instances in two different zones
- `03-verify-output.png`: terminal output of `verify.sh`
- `04-target-group-healthy.png`: EC2, Target groups, Targets tab with both targets healthy in different AZs

## 2. Scaling out and in

```bash
./scripts/load-test.sh 12
```

The script starts a 12-minute CPU burn on every instance through SSM Run Command, then prints the desired and in-service capacity every 30 seconds.

Expected timeline (approximate):

| Time | Event |
| --- | --- |
| 0 min | CPU on both instances near 100% |
| 3–4 min | Target tracking alarm `TargetTracking-...-AlarmHigh` goes to ALARM |
| 4–5 min | Desired capacity rises from 2. Target tracking calculates the capacity needed to reach 50%, so it can jump 2 to 4 in one step |
| 6–7 min | New instances signal healthy and join the target group |
| 12 min | Load stops |
| ~15 min later | Scale-in alarm fires and capacity returns to 2 |

Note that new instances are not part of the burn, so average CPU falls as they join. That is target tracking working as intended.

Capture:

- `05-asg-activity.png`: Auto Scaling group, Activity tab, showing launches and terminations with their causes
- `06-dashboard-scaling.png`: CloudWatch dashboard `<project>-overview` with the CPU spike and instance count in the same widget
- `07-alarm-email.png` (if `AlertEmail` was set): the `web-cpu-high` alarm notification

## 3. Self-healing

1. EC2, Instances, select one web instance, Instance state, Terminate.
2. Keep refreshing the application URL. It stays available because the other AZ keeps serving.
3. Watch the target group: the terminated target drains (30 seconds), the group launches a replacement in the same AZ, and the new target becomes healthy.

A second variant shows why the group uses ELB health checks: connect with Session Manager and run `sudo systemctl stop webapp`. The instance is still running and passes EC2 status checks, but it fails `/health`, so the group replaces it.

Capture:

- `08-instance-replaced.png`: Activity tab showing the replacement and its reason

## 4. Database failover

```bash
./scripts/failover-test.sh
```

The script records the database server hostname, forces a Multi-AZ failover with `reboot-db-instance --force-failover`, and polls the application every 5 seconds until a different database server answers.

Expected: a short period of `DB-DOWN` (the web tier stays up and returns a clear error), then recovery on a different server, typically within 60 to 120 seconds. The primary and secondary AZs printed before and after are swapped. The endpoint DNS name does not change, so the application needed no reconfiguration.

Capture:

- `09-failover-terminal.png`: script output with the timing
- `10-rds-events.png`: RDS, Databases, the instance, Logs and events, showing failover started and completed

## 5. Security configuration

Capture:

- `11-security-groups.png`: the three security groups and their inbound rules referencing each other
- `12-waf-sampled.png`: WAF, Web ACLs, `<project>-alb-acl`, sampled requests showing blocked requests from tests 1
- `13-session-manager.png`: a Session Manager shell on an instance (no key pair, no port 22)
- `14-route-tables.png`: the data route table with only the local route

## 6. Clean up

```bash
./scripts/destroy.sh
```

Then confirm in Cost Explorer the next day that charges stopped.
