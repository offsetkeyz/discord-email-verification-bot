# SES Compliance Quick Reference Card

One-page reference for SES compliance features.

## Quick Deploy

```bash
cd /home/offsetkeyz/claude_coding_projects/au-discord-bot
./scripts/deploy-ses-compliance.sh
```

## Critical Files

| File | Purpose |
|------|---------|
| `lambda/ses_suppression_list.py` | Suppression list management |
| `lambda/ses_notification_handler.py` | Bounce/complaint processor |
| `lambda/ses_email.py` | Modified to check suppression |

## AWS Resources

| Type | Name | Purpose |
|------|------|---------|
| DynamoDB | `ses-email-suppression-list` | Stores bounced/complained emails |
| Lambda | `ses-notification-handler` | Processes notifications |
| SNS Topic | `ses-bounce-complaint-notifications` | SES notifications |
| Alarms | `ses-*` | Monitors bounce/complaint rates |

## Key Functions

```python
# Check if email is suppressed
from ses_suppression_list import is_suppressed
if is_suppressed('user@example.edu'):
    return False  # Don't send

# Add to suppression (automatic via handler)
add_to_suppression_list(email, reason='bounce', bounce_type='Permanent')

# Publish metrics (automatic in ses_email.py)
publish_email_metric('EmailsSent')
```

## CloudWatch Alarms

| Alarm | Threshold | Severity |
|-------|-----------|----------|
| `ses-high-bounce-rate-CRITICAL` | >5% | CRITICAL |
| `ses-high-complaint-rate-CRITICAL` | >0.1% | CRITICAL |
| `ses-bounce-rate-warning` | >3% | WARNING |
| `ses-complaint-rate-warning` | >0.05% | WARNING |

## Testing Commands

```bash
# Test bounce
aws ses send-email \
    --from noreply@domain.com \
    --destination bounce@simulator.amazonses.com \
    --message "Subject={Data=Test},Body={Text={Data=Test}}"

# Test complaint
aws ses send-email \
    --from noreply@domain.com \
    --destination complaint@simulator.amazonses.com \
    --message "Subject={Data=Test},Body={Text={Data=Test}}"

# Check suppression list
aws dynamodb scan --table-name ses-email-suppression-list --select COUNT

# View metrics
aws cloudwatch get-metric-statistics \
    --namespace DiscordBot/SES \
    --metric-name EmailsSent \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum
```

## DNS Records Required

```
# SPF
TXT @ "v=spf1 include:amazonses.com ~all"

# DKIM (3 CNAME records - get tokens from AWS)
CNAME token1._domainkey token1.dkim.amazonses.com
CNAME token2._domainkey token2.dkim.amazonses.com
CNAME token3._domainkey token3.dkim.amazonses.com

# DMARC
TXT _dmarc "v=DMARC1; p=quarantine; rua=mailto:dmarc@domain.com"

# SES Verification
TXT _amazonses "verification-token-from-aws"
```

Verify: `./scripts/verify-dns.sh <domain>`

## Environment Variables

### Main Lambda:
```
SUPPRESSION_LIST_TABLE=ses-email-suppression-list
AWS_DEFAULT_REGION=us-east-1
```

### Notification Handler:
```
SUPPRESSION_LIST_TABLE=ses-email-suppression-list
AWS_DEFAULT_REGION=us-east-1
```

## Daily Checklist

```bash
# 1. Check alarms
aws cloudwatch describe-alarms --alarm-name-prefix ses- \
    --query 'MetricAlarms[?StateValue==`ALARM`].[AlarmName,StateValue]'

# 2. Check suppression list growth
aws dynamodb scan --table-name ses-email-suppression-list --select COUNT

# 3. View yesterday's metrics
aws cloudwatch get-metric-statistics \
    --namespace DiscordBot/SES --metric-name EmailsSent \
    --start-time $(date -u -d '1 day ago' +%Y-%m-%dT00:00:00) \
    --end-time $(date -u +%Y-%m-%dT00:00:00) \
    --period 86400 --statistics Sum
```

## Troubleshooting

### Email not sending?
1. Check suppression list: `is_suppressed(email)`
2. Check Lambda logs: `aws logs tail /aws/lambda/discord-verification-handler --follow`
3. Verify SES status: `aws ses get-account-sending-enabled`

### High bounce rate?
1. Check recent bounces in DynamoDB
2. Validate email format before sending
3. Review bounce types (permanent vs transient)

### Alarm triggered?
1. Check alarm details: `aws cloudwatch describe-alarms --alarm-names <name>`
2. Review metrics in console
3. Follow incident response in runbook

## Scripts Reference

```bash
# Deploy everything
./scripts/deploy-ses-compliance.sh

# Create suppression table only
./scripts/create-suppression-table.sh

# Create alarms only
./scripts/create-ses-alarms.sh

# Verify DNS
./scripts/verify-dns.sh <domain>
```

## Documentation

- Full Setup: `docs/SES_SETUP_GUIDE.md`
- Operations: `docs/SES_OPERATIONS_RUNBOOK.md`
- Testing: `docs/SES_TESTING_GUIDE.md`
- Summary: `SES_COMPLIANCE_IMPLEMENTATION_SUMMARY.md`

## AWS Console Links

```
SES Console:
https://console.aws.amazon.com/ses/home?region=us-east-1

CloudWatch Alarms:
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#alarmsV2:

DynamoDB Tables:
https://console.aws.amazon.com/dynamodbv2/home?region=us-east-1#tables

Lambda Functions:
https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions
```

## Critical Thresholds

| Metric | Warning | Critical | AWS Limit |
|--------|---------|----------|-----------|
| Bounce Rate | 3% | 5% | >5% suspension |
| Complaint Rate | 0.05% | 0.1% | >0.1% suspension |

## Emergency Contacts

1. Check runbook: `docs/SES_OPERATIONS_RUNBOOK.md`
2. AWS Support: Create case via console
3. Escalate per runbook procedures

---

**Last Updated:** 2024-12-08
**Document Version:** 1.0
