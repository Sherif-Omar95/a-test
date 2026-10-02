# Deployment guide

## Before you start

1. Use an IAM user or role with permission to create VPC, EC2, Auto Scaling, ELB, RDS, S3, CloudFront, WAF, IAM roles, CloudWatch, SNS and SSM resources. `AdministratorAccess` is simplest in a personal lab account.
2. Create a budget alert: Billing and Cost Management, Budgets, Create budget, Monthly cost budget, for example 20 USD.
3. Pick a region. Any region with at least two Availability Zones works. The examples use `us-east-1`.

## Option A: command line

```bash
aws configure                           # or use an SSO profile
export AWS_REGION=us-east-1
export STACK=scalable-web               # also used as the ProjectName prefix
ALERT_EMAIL=you@example.com ./scripts/deploy.sh
```

`deploy.sh` does three things:

1. Runs `scripts/embed_app.py`, which copies `app/app.py` into the launch template user data.
2. Runs `aws cloudformation deploy`, which creates the stack or applies a change set to it.
3. Uploads `app/static/` to the S3 bucket under `static/`.

Changing the application later is the same command. The launch template gets a new version and the Auto Scaling group replaces instances one at a time, waiting for each new instance to signal that it is healthy.

## Option B: CloudFormation console

1. Open CloudFormation, Create stack, With new resources.
2. Upload `infrastructure/main.yaml`.
3. Stack name: `scalable-web`. Set `ProjectName` to the same value and fill in `AlertEmail`.
4. Leave the other parameters at their defaults. Acknowledge that the stack creates IAM resources.
5. Wait for `CREATE_COMPLETE` (20 to 30 minutes).
6. Upload the static files: S3, open the bucket shown in the `StaticBucketName` output, create a folder named `static`, and upload `app/static/style.css` and `app/static/favicon.svg` into it.
7. Open the `ApplicationUrl` output.

## Parameters

| Parameter | Default | Notes |
| --- | --- | --- |
| ProjectName | scalable-web | Prefix for resource names |
| AlertEmail | empty | Alarm notifications; confirm the subscription email |
| NatGatewayMode | single | `per-az` adds a second NAT Gateway |
| InstanceType | t3.micro | t3.small or t3.medium allowed |
| MinSize / DesiredCapacity / MaxSize | 2 / 2 / 6 | Min is at least 2 so both AZs always have an instance |
| CpuTargetPercent | 50 | Target tracking value for average CPU |
| RequestsPerTarget | 1000 | Target tracking value for ALB requests per instance per minute |
| DBInstanceClass | db.t3.micro | |
| DBEngineVersion | 8.4 | 8.0 adds RDS Extended Support charges |
| DBMultiAZ | true | Set false only to save money while developing |
| DomainName, HostedZoneId, CloudFrontCertificateArn | empty | All three together enable the custom domain. The certificate must be in us-east-1 |

## Using a custom domain (optional)

1. Have a public hosted zone in Route 53 for your domain.
2. In ACM in **us-east-1**, request a public certificate for `app.example.com` with DNS validation and create the validation record in Route 53.
3. Deploy with the three parameters:

```bash
./scripts/deploy.sh DomainName=app.example.com HostedZoneId=Z123EXAMPLE \
  CloudFrontCertificateArn=arn:aws:acm:us-east-1:111122223333:certificate/abcd-...
```

The stack adds the domain as a CloudFront alternate name and creates A and AAAA alias records.

## Connecting to an instance

There is no SSH. Use Session Manager:

```bash
aws ssm start-session --target i-0123456789abcdef0
sudo journalctl -u webapp -n 50       # application log
sudo cat /var/log/user-data.log       # bootstrap log
```

Or in the console: EC2, select the instance, Connect, Session Manager.

## Troubleshooting

| Symptom | Likely cause | Check |
| --- | --- | --- |
| Stack fails at `AppAutoScalingGroup` with "received 0 SUCCESS signals" | User data failed on the instances | Session Manager into an instance, read `/var/log/user-data.log`. Instances need the NAT route to install packages |
| Page loads but shows "Database unreachable" | Database still starting, failing over, or a security group change | `/api/info` shows the exact error. Check `db-sg` allows 3306 from `app-sg` |
| Page has no styling | Static files not uploaded | Run `deploy.sh` again or upload `app/static/*` to `s3://<bucket>/static/` |
| Every request returns 403 | Calling the ALB DNS name directly | Use the CloudFront URL. Direct ALB access is blocked by design |
| No alarm emails | Subscription not confirmed | SNS, Subscriptions, status must be Confirmed |
| `DELETE_FAILED` on the bucket | Bucket not empty | Use `scripts/destroy.sh`, which empties it first |
