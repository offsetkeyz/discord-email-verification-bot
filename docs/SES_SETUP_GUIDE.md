# AWS SES Production Setup Guide

Complete guide for configuring AWS SES for production email delivery with the Discord Email Verification Bot.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Domain Verification](#domain-verification)
3. [Email Authentication (SPF, DKIM, DMARC)](#email-authentication)
4. [Production Access Request](#production-access-request)
5. [Bounce and Complaint Handling](#bounce-and-complaint-handling)
6. [CloudWatch Monitoring](#cloudwatch-monitoring)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

- AWS account with SES service access
- Domain name with DNS control (e.g., `thedailydecrypt.com`)
- AWS CLI configured with appropriate credentials
- Lambda function already deployed

## Domain Verification

### Step 1: Verify Domain in SES

```bash
# Verify your domain with SES
aws ses verify-domain-identity --domain thedailydecrypt.com

# Output will contain a verification token
# Example output:
# {
#     "VerificationToken": "abc123xyz..."
# }
```

### Step 2: Add DNS TXT Record

Add the verification token to your DNS:

```
Type: TXT
Name: _amazonses.thedailydecrypt.com
Value: <verification-token-from-step-1>
TTL: 1800
```

### Step 3: Check Verification Status

```bash
# Check if domain is verified
aws ses get-identity-verification-attributes --identities thedailydecrypt.com

# Wait for "VerificationStatus": "Success"
```

## Email Authentication

Proper email authentication (SPF, DKIM, DMARC) is CRITICAL for deliverability and avoiding spam folders.

### Step 1: Enable DKIM Signing

```bash
# Enable DKIM for your domain
aws ses set-identity-dkim-enabled --identity thedailydecrypt.com --dkim-enabled

# Get DKIM tokens
aws ses get-identity-dkim-attributes --identities thedailydecrypt.com
```

### Step 2: Add DKIM DNS Records

You'll receive 3 DKIM tokens. Add all three as CNAME records:

```
Type: CNAME
Name: token1._domainkey.thedailydecrypt.com
Value: token1.dkim.amazonses.com
TTL: 1800

Type: CNAME
Name: token2._domainkey.thedailydecrypt.com
Value: token2.dkim.amazonses.com
TTL: 1800

Type: CNAME
Name: token3._domainkey.thedailydecrypt.com
Value: token3.dkim.amazonses.com
TTL: 1800
```

### Step 3: Configure SPF Record

Add SPF record to authorize SES to send on behalf of your domain:

```
Type: TXT
Name: thedailydecrypt.com
Value: v=spf1 include:amazonses.com ~all
TTL: 1800
```

**Note:** If you already have an SPF record, merge it:
```
v=spf1 include:amazonses.com include:_spf.google.com ~all
```

### Step 4: Configure DMARC Record

Add DMARC policy to protect your domain and get feedback:

```
Type: TXT
Name: _dmarc.thedailydecrypt.com
Value: v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@thedailydecrypt.com; ruf=mailto:dmarc-forensics@thedailydecrypt.com; fo=1; pct=100
TTL: 1800
```

**DMARC Policy Explanation:**
- `p=quarantine`: Quarantine suspicious emails (use `p=reject` for strict policy)
- `rua=`: Aggregate reports destination
- `ruf=`: Forensic reports destination
- `fo=1`: Generate reports for all failures
- `pct=100`: Apply policy to 100% of emails

### Step 5: Verify DNS Propagation

```bash
# Check SPF
dig TXT thedailydecrypt.com

# Check DKIM
dig CNAME token1._domainkey.thedailydecrypt.com

# Check DMARC
dig TXT _dmarc.thedailydecrypt.com
```

## Production Access Request

By default, SES is in **sandbox mode** with these limitations:
- Can only send to verified email addresses
- Maximum 200 emails per 24 hours
- Maximum 1 email per second

### Request Production Access

1. **Go to AWS SES Console:**
   ```
   https://console.aws.amazon.com/ses/home?region=us-east-1#/account
   ```

2. **Click "Request Production Access"**

3. **Fill Out Request Form:**
   - **Mail Type:** Transactional
   - **Website URL:** Your Discord server or project website
   - **Use Case Description:**
     ```
     We operate a Discord email verification bot that sends verification
     codes to university students (.edu domains) to verify their academic
     status. Each user receives a single verification email containing a
     6-digit code. Emails are only sent after explicit user request via
     Discord slash command. We implement:

     - Bounce/complaint suppression list
     - Rate limiting per user
     - Email validation before sending
     - Automatic bounce/complaint handling via SNS
     - CloudWatch monitoring and alerting

     Expected volume: 500-1000 emails/day during academic year.
     ```
   - **Compliance with AWS Policies:** Yes
   - **Will you comply with AWS policies?** Yes
   - **Describe your process for handling bounces/complaints:**
     ```
     We process SES bounce and complaint notifications via SNS -> Lambda.
     Permanent bounces and all complaints are automatically added to a
     DynamoDB suppression list. Emails on the suppression list are blocked
     from receiving future emails. We monitor bounce/complaint rates via
     CloudWatch alarms.
     ```

4. **Wait for Approval** (typically 24-48 hours)

### After Approval

Check your new limits:

```bash
aws ses get-send-quota

# Example output:
# {
#     "Max24HourSend": 50000.0,
#     "MaxSendRate": 14.0,
#     "SentLast24Hours": 0.0
# }
```

## Bounce and Complaint Handling

AWS **REQUIRES** bounce and complaint handling. Failure to implement this can result in account suspension.

### Step 1: Create DynamoDB Suppression Table

```bash
cd /home/offsetkeyz/claude_coding_projects/au-discord-bot
./scripts/create-suppression-table.sh
```

### Step 2: Create SNS Topic for SES Notifications

```bash
# Create SNS topic
aws sns create-topic --name ses-bounce-complaint-notifications

# Note the TopicArn from output
# Example: arn:aws:sns:us-east-1:123456789012:ses-bounce-complaint-notifications
```

### Step 3: Configure SES to Publish to SNS

```bash
# Get your SNS topic ARN
SNS_TOPIC_ARN=$(aws sns list-topics --query "Topics[?contains(TopicArn, 'ses-bounce-complaint')].TopicArn" --output text)

# Configure bounce notifications
aws ses set-identity-notification-topic \
    --identity thedailydecrypt.com \
    --notification-type Bounce \
    --sns-topic $SNS_TOPIC_ARN

# Configure complaint notifications
aws ses set-identity-notification-topic \
    --identity thedailydecrypt.com \
    --notification-type Complaint \
    --sns-topic $SNS_TOPIC_ARN

# Disable email feedback forwarding (use SNS instead)
aws ses set-identity-feedback-forwarding-enabled \
    --identity thedailydecrypt.com \
    --no-forwarding-enabled
```

### Step 4: Create Lambda Function for Notification Handling

```bash
# Package the notification handler
cd lambda
zip -r ses-notification-handler.zip ses_notification_handler.py ses_suppression_list.py

# Create IAM role for Lambda (if not exists)
aws iam create-role \
    --role-name SESNotificationHandlerRole \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }'

# Attach policies
aws iam attach-role-policy \
    --role-name SESNotificationHandlerRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create inline policy for DynamoDB access
aws iam put-role-policy \
    --role-name SESNotificationHandlerRole \
    --policy-name DynamoDBSuppressionAccess \
    --policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:DeleteItem"
            ],
            "Resource": "arn:aws:dynamodb:us-east-1:*:table/ses-email-suppression-list"
        }]
    }'

# Get role ARN
ROLE_ARN=$(aws iam get-role --role-name SESNotificationHandlerRole --query 'Role.Arn' --output text)

# Create Lambda function
aws lambda create-function \
    --function-name ses-notification-handler \
    --runtime python3.11 \
    --role $ROLE_ARN \
    --handler ses_notification_handler.lambda_handler \
    --zip-file fileb://ses-notification-handler.zip \
    --timeout 30 \
    --environment Variables="{SUPPRESSION_LIST_TABLE=ses-email-suppression-list,AWS_DEFAULT_REGION=us-east-1}"
```

### Step 5: Subscribe Lambda to SNS Topic

```bash
# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function --function-name ses-notification-handler --query 'Configuration.FunctionArn' --output text)

# Subscribe Lambda to SNS
aws sns subscribe \
    --topic-arn $SNS_TOPIC_ARN \
    --protocol lambda \
    --notification-endpoint $LAMBDA_ARN

# Grant SNS permission to invoke Lambda
aws lambda add-permission \
    --function-name ses-notification-handler \
    --statement-id AllowSNSInvoke \
    --action lambda:InvokeFunction \
    --principal sns.amazonaws.com \
    --source-arn $SNS_TOPIC_ARN
```

### Step 6: Update Main Lambda Environment Variables

```bash
# Add SUPPRESSION_LIST_TABLE to main Lambda
aws lambda update-function-configuration \
    --function-name discord-verification-handler \
    --environment Variables="{SUPPRESSION_LIST_TABLE=ses-email-suppression-list,...existing vars...}"

# Update IAM role to allow DynamoDB access
aws iam put-role-policy \
    --role-name <your-main-lambda-role> \
    --policy-name DynamoDBSuppressionAccess \
    --policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:Query"
            ],
            "Resource": "arn:aws:dynamodb:us-east-1:*:table/ses-email-suppression-list"
        }]
    }'
```

## CloudWatch Monitoring

### Step 1: Create CloudWatch Alarms

```bash
./scripts/create-ses-alarms.sh
```

### Step 2: Create SNS Topic for Alerts

```bash
# Create alert topic
aws sns create-topic --name ses-alerts

# Get topic ARN
ALERT_TOPIC_ARN=$(aws sns list-topics --query "Topics[?contains(TopicArn, 'ses-alerts')].TopicArn" --output text)

# Subscribe your email
aws sns subscribe \
    --topic-arn $ALERT_TOPIC_ARN \
    --protocol email \
    --notification-endpoint your-email@example.com

# Confirm subscription via email
```

### Step 3: Update Alarms with SNS Actions

```bash
# Update bounce rate alarm
aws cloudwatch put-metric-alarm \
    --alarm-name ses-high-bounce-rate-CRITICAL \
    --alarm-actions $ALERT_TOPIC_ARN \
    --alarm-description "SES bounce rate exceeded 5% - risk of suspension" \
    --metric-name Reputation.BounceRate \
    --namespace AWS/SES \
    --statistic Average \
    --period 3600 \
    --threshold 0.05 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --treat-missing-data notBreaching

# Update complaint rate alarm
aws cloudwatch put-metric-alarm \
    --alarm-name ses-high-complaint-rate-CRITICAL \
    --alarm-actions $ALERT_TOPIC_ARN \
    --alarm-description "SES complaint rate exceeded 0.1% - risk of suspension" \
    --metric-name Reputation.ComplaintRate \
    --namespace AWS/SES \
    --statistic Average \
    --period 3600 \
    --threshold 0.001 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --treat-missing-data notBreaching
```

### Step 4: Create Dashboard (Optional)

```bash
aws cloudwatch put-dashboard \
    --dashboard-name SES-Monitoring \
    --dashboard-body file://ses-dashboard.json
```

Create `ses-dashboard.json`:
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/SES", "Reputation.BounceRate"],
          [".", "Reputation.ComplaintRate"]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "SES Reputation Metrics",
        "yAxis": {
          "left": {
            "min": 0,
            "max": 0.1
          }
        }
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["DiscordBot/SES", "EmailsSent"],
          [".", "EmailsFailed"],
          [".", "EmailsSuppressed"]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Email Sending Metrics"
      }
    }
  ]
}
```

## Testing

### Test 1: Verify DNS Configuration

```bash
# Check all DNS records
./scripts/verify-dns.sh thedailydecrypt.com
```

### Test 2: Send Test Email

```bash
# Send test via AWS CLI
aws ses send-email \
    --from "verificationcode.noreply@thedailydecrypt.com" \
    --destination "ToAddresses=your-test@email.com" \
    --message "Subject={Data=Test Email},Body={Text={Data=Testing SES configuration}}"
```

### Test 3: Simulate Bounce

Send email to AWS's bounce testing address:

```bash
aws ses send-email \
    --from "verificationcode.noreply@thedailydecrypt.com" \
    --destination "ToAddresses=bounce@simulator.amazonses.com" \
    --message "Subject={Data=Bounce Test},Body={Text={Data=Testing bounce handling}}"

# Check SNS topic received notification
aws sns list-subscriptions-by-topic --topic-arn $SNS_TOPIC_ARN

# Check DynamoDB for suppression entry
aws dynamodb get-item \
    --table-name ses-email-suppression-list \
    --key '{"email": {"S": "bounce@simulator.amazonses.com"}, "reason": {"S": "bounce"}}'
```

### Test 4: Simulate Complaint

```bash
aws ses send-email \
    --from "verificationcode.noreply@thedailydecrypt.com" \
    --destination "ToAddresses=complaint@simulator.amazonses.com" \
    --message "Subject={Data=Complaint Test},Body={Text={Data=Testing complaint handling}}"
```

### Test 5: Check Suppression List Works

Try sending to suppressed address - should be blocked by `is_suppressed()` check.

## Troubleshooting

### Email Not Delivered

1. **Check SES sending status:**
   ```bash
   aws ses get-send-quota
   aws ses get-account-sending-enabled
   ```

2. **Check CloudWatch Logs:**
   ```bash
   aws logs tail /aws/lambda/discord-verification-handler --follow
   ```

3. **Verify DNS records:**
   ```bash
   dig TXT thedailydecrypt.com
   dig CNAME token._domainkey.thedailydecrypt.com
   ```

### High Bounce Rate

1. **Check bounce types:**
   - Permanent bounces → Invalid emails, remove from lists
   - Transient bounces → Temporary issues, retry later

2. **Review suppression list:**
   ```bash
   aws dynamodb scan --table-name ses-email-suppression-list
   ```

3. **Investigate root cause:**
   - Are email addresses validated before sending?
   - Are you sending to old/invalid email lists?

### Emails in Spam Folder

1. **Verify DKIM, SPF, DMARC:**
   ```bash
   # Use mail-tester.com - send email to provided address
   # Get score and recommendations
   ```

2. **Check sender reputation:**
   - Use tools like Google Postmaster Tools
   - Monitor bounce/complaint rates

3. **Review email content:**
   - Avoid spam trigger words
   - Include unsubscribe link
   - Use proper HTML structure

### Account Suspended

1. **Contact AWS Support immediately**
2. **Review bounce/complaint reports**
3. **Implement corrective actions:**
   - Clean email lists
   - Improve validation
   - Review sending practices

## Next Steps

After completing this setup:

1. Monitor CloudWatch dashboard daily for first week
2. Review bounce/complaint reports weekly
3. Set up DMARC report analysis
4. Document any issues in operations runbook
5. Test disaster recovery procedures

See [SES_OPERATIONS_RUNBOOK.md](./SES_OPERATIONS_RUNBOOK.md) for ongoing operational procedures.
