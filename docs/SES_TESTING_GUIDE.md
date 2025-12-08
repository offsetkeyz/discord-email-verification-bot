# SES Compliance Testing Guide

Comprehensive testing procedures for SES bounce/complaint handling and monitoring features.

## Table of Contents

1. [Unit Testing](#unit-testing)
2. [Integration Testing](#integration-testing)
3. [AWS Simulator Testing](#aws-simulator-testing)
4. [End-to-End Testing](#end-to-end-testing)
5. [Monitoring Validation](#monitoring-validation)

---

## Unit Testing

### Test Suppression List Module

Create test file: `/home/offsetkeyz/claude_coding_projects/au-discord-bot/tests/test_ses_suppression.py`

```python
import pytest
import boto3
from moto import mock_dynamodb
from lambda.ses_suppression_list import (
    add_to_suppression_list,
    is_suppressed,
    remove_from_suppression_list
)


@mock_dynamodb
def test_add_to_suppression_list():
    """Test adding email to suppression list."""
    # Create mock table
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='ses-email-suppression-list',
        KeySchema=[
            {'AttributeName': 'email', 'KeyType': 'HASH'},
            {'AttributeName': 'reason', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'email', 'AttributeType': 'S'},
            {'AttributeName': 'reason', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # Test adding bounce
    result = add_to_suppression_list(
        email='test@example.edu',
        reason='bounce',
        bounce_type='Permanent',
        details={'subtype': 'General'}
    )

    assert result is True

    # Verify in table
    response = table.get_item(
        Key={'email': 'test@example.edu', 'reason': 'bounce'}
    )
    assert 'Item' in response
    assert response['Item']['bounce_type'] == 'Permanent'


@mock_dynamodb
def test_is_suppressed():
    """Test checking if email is suppressed."""
    # Create mock table and add suppressed email
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='ses-email-suppression-list',
        KeySchema=[
            {'AttributeName': 'email', 'KeyType': 'HASH'},
            {'AttributeName': 'reason', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'email', 'AttributeType': 'S'},
            {'AttributeName': 'reason', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # Add suppressed email
    add_to_suppression_list('suppressed@example.edu', 'bounce', 'Permanent')

    # Test suppressed email
    assert is_suppressed('suppressed@example.edu') is True

    # Test non-suppressed email
    assert is_suppressed('valid@example.edu') is False


@mock_dynamodb
def test_remove_from_suppression():
    """Test removing email from suppression list."""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='ses-email-suppression-list',
        KeySchema=[
            {'AttributeName': 'email', 'KeyType': 'HASH'},
            {'AttributeName': 'reason', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'email', 'AttributeType': 'S'},
            {'AttributeName': 'reason', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # Add and then remove
    add_to_suppression_list('test@example.edu', 'bounce', 'Permanent')
    assert is_suppressed('test@example.edu') is True

    remove_from_suppression_list('test@example.edu', 'bounce')
    assert is_suppressed('test@example.edu') is False
```

**Run Tests:**
```bash
cd /home/offsetkeyz/claude_coding_projects/au-discord-bot
pytest tests/test_ses_suppression.py -v
```

---

## Integration Testing

### Test SES Email with Suppression Check

Create test file: `/home/offsetkeyz/claude_coding_projects/au-discord-bot/tests/test_ses_email_integration.py`

```python
import pytest
from moto import mock_ses, mock_dynamodb, mock_cloudwatch
from lambda.ses_email import send_verification_email
from lambda.ses_suppression_list import add_to_suppression_list


@mock_ses
@mock_dynamodb
@mock_cloudwatch
def test_send_email_checks_suppression():
    """Test that send_verification_email checks suppression list."""
    # Create mock suppression table
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    dynamodb.create_table(
        TableName='ses-email-suppression-list',
        KeySchema=[
            {'AttributeName': 'email', 'KeyType': 'HASH'},
            {'AttributeName': 'reason', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'email', 'AttributeType': 'S'},
            {'AttributeName': 'reason', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # Verify SES email
    ses = boto3.client('ses', region_name='us-east-1')
    ses.verify_email_identity(EmailAddress='from@example.com')

    # Test 1: Normal email should send
    result = send_verification_email('valid@example.edu', '123456')
    assert result is True

    # Test 2: Suppressed email should NOT send
    add_to_suppression_list('suppressed@example.edu', 'bounce', 'Permanent')
    result = send_verification_email('suppressed@example.edu', '123456')
    assert result is False


@mock_ses
@mock_cloudwatch
def test_email_metrics_published():
    """Test that CloudWatch metrics are published."""
    import boto3

    # Setup SES
    ses = boto3.client('ses', region_name='us-east-1')
    ses.verify_email_identity(EmailAddress='from@example.com')

    # Send email
    send_verification_email('test@example.edu', '123456')

    # Check CloudWatch metrics were published
    cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
    metrics = cloudwatch.list_metrics(Namespace='DiscordBot/SES')

    metric_names = [m['MetricName'] for m in metrics['Metrics']]
    assert 'EmailsSent' in metric_names
```

**Run Tests:**
```bash
pytest tests/test_ses_email_integration.py -v
```

---

## AWS Simulator Testing

AWS provides special email addresses that simulate bounces and complaints.

### Test Bounce Handling

```bash
# 1. Send email to bounce simulator
aws ses send-email \
    --from "verificationcode.noreply@thedailydecrypt.com" \
    --destination "ToAddresses=bounce@simulator.amazonses.com" \
    --message "Subject={Data=Bounce Test},Body={Text={Data=Testing bounce handling}}"

# 2. Wait 30 seconds for SNS notification

# 3. Check Lambda logs
aws logs tail /aws/lambda/ses-notification-handler --follow

# Expected output: "Added bounce@simulator.amazonses.com to suppression list"

# 4. Verify in DynamoDB
aws dynamodb get-item \
    --table-name ses-email-suppression-list \
    --key '{"email": {"S": "bounce@simulator.amazonses.com"}, "reason": {"S": "bounce"}}'

# Expected: Item found with bounce_type: "Permanent"
```

### Test Complaint Handling

```bash
# 1. Send email to complaint simulator
aws ses send-email \
    --from "verificationcode.noreply@thedailydecrypt.com" \
    --destination "ToAddresses=complaint@simulator.amazonses.com" \
    --message "Subject={Data=Complaint Test},Body={Text={Data=Testing complaint handling}}"

# 2. Wait 30 seconds

# 3. Check Lambda logs
aws logs tail /aws/lambda/ses-notification-handler --follow

# Expected: "Added complaint@simulator.amazonses.com to suppression list"

# 4. Verify in DynamoDB
aws dynamodb get-item \
    --table-name ses-email-suppression-list \
    --key '{"email": {"S": "complaint@simulator.amazonses.com"}, "reason": {"S": "complaint"}}'
```

### Test Other Simulator Addresses

```bash
# Success (no bounce)
aws ses send-email \
    --from "verificationcode.noreply@thedailydecrypt.com" \
    --destination "ToAddresses=success@simulator.amazonses.com" \
    --message "Subject={Data=Success Test},Body={Text={Data=Should succeed}}"

# Out-of-office auto-responder
aws ses send-email \
    --from "verificationcode.noreply@thedailydecrypt.com" \
    --destination "ToAddresses=ooto@simulator.amazonses.com" \
    --message "Subject={Data=OOTO Test},Body={Text={Data=Auto-responder test}}"

# Suppress list (already suppressed by SES)
aws ses send-email \
    --from "verificationcode.noreply@thedailydecrypt.com" \
    --destination "ToAddresses=suppressionlist@simulator.amazonses.com" \
    --message "Subject={Data=Suppression Test},Body={Text={Data=Should fail}}"
```

---

## End-to-End Testing

### Test Complete Flow

**Scenario:** User verification with bounce/complaint handling

```bash
# 1. Setup: Create test verification session
# (Use Discord bot or API to trigger verification)

# 2. Send verification email
# Email sent via Lambda → SES

# 3. Simulate bounce notification
aws sns publish \
    --topic-arn arn:aws:sns:us-east-1:YOUR_ACCOUNT:ses-bounce-complaint-notifications \
    --message '{
        "notificationType": "Bounce",
        "bounce": {
            "bounceType": "Permanent",
            "bounceSubType": "General",
            "bouncedRecipients": [{
                "emailAddress": "test@example.edu",
                "diagnosticCode": "550 5.1.1 User unknown"
            }],
            "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"
        }
    }'

# 4. Verify suppression added
aws dynamodb get-item \
    --table-name ses-email-suppression-list \
    --key '{"email": {"S": "test@example.edu"}, "reason": {"S": "bounce"}}'

# 5. Attempt to send again (should be blocked)
# Try sending to same email → should fail with "on suppression list" message

# 6. Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
    --namespace DiscordBot/SES \
    --metric-name EmailsSuppressed \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum
```

---

## Monitoring Validation

### Test CloudWatch Alarms

**Test Bounce Rate Alarm:**

```bash
# 1. Get current alarm state
aws cloudwatch describe-alarms --alarm-names ses-high-bounce-rate-CRITICAL

# 2. Put test metric data to trigger alarm
aws cloudwatch put-metric-data \
    --namespace AWS/SES \
    --metric-name Reputation.BounceRate \
    --value 0.06 \
    --timestamp $(date -u +%Y-%m-%dT%H:%M:%S)

# 3. Wait 5 minutes for alarm evaluation

# 4. Check alarm state changed to ALARM
aws cloudwatch describe-alarms \
    --alarm-names ses-high-bounce-rate-CRITICAL \
    --query 'MetricAlarms[0].StateValue' \
    --output text

# Expected: ALARM

# 5. Reset alarm with normal value
aws cloudwatch put-metric-data \
    --namespace AWS/SES \
    --metric-name Reputation.BounceRate \
    --value 0.01 \
    --timestamp $(date -u +%Y-%m-%dT%H:%M:%S)
```

**Test Email Metrics:**

```bash
# Publish test metrics
aws cloudwatch put-metric-data \
    --namespace DiscordBot/SES \
    --metric-name EmailsSent \
    --value 100

aws cloudwatch put-metric-data \
    --namespace DiscordBot/SES \
    --metric-name EmailsFailed \
    --value 5

# View metrics
aws cloudwatch get-metric-statistics \
    --namespace DiscordBot/SES \
    --metric-name EmailsSent \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum
```

### Test Dashboard

```bash
# View dashboard
aws cloudwatch get-dashboard --dashboard-name SES-Monitoring

# Or open in browser:
echo "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=SES-Monitoring"
```

---

## Automated Test Suite

Create comprehensive test script: `scripts/test-ses-compliance.sh`

```bash
#!/bin/bash
# Automated SES compliance testing

set -e

echo "Starting SES Compliance Tests..."

# 1. Unit tests
echo "1. Running unit tests..."
pytest tests/test_ses_suppression.py -v

# 2. Integration tests
echo "2. Running integration tests..."
pytest tests/test_ses_email_integration.py -v

# 3. AWS simulator tests
echo "3. Testing bounce handling..."
aws ses send-email \
    --from "verificationcode.noreply@thedailydecrypt.com" \
    --destination "ToAddresses=bounce@simulator.amazonses.com" \
    --message "Subject={Data=Test},Body={Text={Data=Bounce test}}" \
    > /dev/null

sleep 30

# Check suppression list
BOUNCE_COUNT=$(aws dynamodb scan \
    --table-name ses-email-suppression-list \
    --filter-expression "email = :email" \
    --expression-attribute-values '{":email": {"S": "bounce@simulator.amazonses.com"}}' \
    --select COUNT \
    --query 'Count' \
    --output text)

if [ "$BOUNCE_COUNT" -gt 0 ]; then
    echo "   ✓ Bounce handling working"
else
    echo "   ✗ Bounce handling failed"
    exit 1
fi

# 4. Test complaint handling
echo "4. Testing complaint handling..."
aws ses send-email \
    --from "verificationcode.noreply@thedailydecrypt.com" \
    --destination "ToAddresses=complaint@simulator.amazonses.com" \
    --message "Subject={Data=Test},Body={Text={Data=Complaint test}}" \
    > /dev/null

sleep 30

COMPLAINT_COUNT=$(aws dynamodb scan \
    --table-name ses-email-suppression-list \
    --filter-expression "email = :email" \
    --expression-attribute-values '{":email": {"S": "complaint@simulator.amazonses.com"}}' \
    --select COUNT \
    --query 'Count' \
    --output text)

if [ "$COMPLAINT_COUNT" -gt 0 ]; then
    echo "   ✓ Complaint handling working"
else
    echo "   ✗ Complaint handling failed"
    exit 1
fi

# 5. Test CloudWatch alarms exist
echo "5. Checking CloudWatch alarms..."
ALARM_COUNT=$(aws cloudwatch describe-alarms \
    --alarm-name-prefix ses- \
    --query 'length(MetricAlarms)' \
    --output text)

if [ "$ALARM_COUNT" -ge 4 ]; then
    echo "   ✓ CloudWatch alarms configured ($ALARM_COUNT alarms)"
else
    echo "   ✗ Missing CloudWatch alarms (found $ALARM_COUNT, expected >= 4)"
    exit 1
fi

echo ""
echo "✅ All SES compliance tests passed!"
```

---

## Test Checklist

Before deploying to production, verify:

- [ ] Unit tests pass for suppression list module
- [ ] Integration tests pass for email sending with suppression check
- [ ] Bounce simulator test adds email to suppression list
- [ ] Complaint simulator test adds email to suppression list
- [ ] Suppression check prevents sending to suppressed emails
- [ ] CloudWatch metrics are published correctly
- [ ] CloudWatch alarms are configured and working
- [ ] SNS notifications are received by Lambda
- [ ] Lambda has proper IAM permissions
- [ ] DynamoDB table is created with correct schema
- [ ] DNS records (SPF, DKIM, DMARC) are verified
- [ ] Operations runbook is understood by team

---

## Troubleshooting Tests

### Test Fails: "Table not found"

```bash
# Create table first
./scripts/create-suppression-table.sh
```

### Test Fails: "Permission denied"

```bash
# Check IAM role has DynamoDB permissions
aws iam get-role-policy \
    --role-name YOUR_LAMBDA_ROLE \
    --policy-name DynamoDBSuppressionAccess
```

### Simulator Email Not Triggering Notification

1. Check SNS subscription is confirmed
2. Verify Lambda has permission to be invoked by SNS
3. Check Lambda logs for errors
4. Ensure SES notification topic is configured

### Metrics Not Appearing in CloudWatch

1. Check Lambda has cloudwatch:PutMetricData permission
2. Verify namespace is exactly "DiscordBot/SES"
3. Wait 5 minutes for metrics to appear
4. Check Lambda logs for metric publishing errors

---

**Last Updated:** 2024-12-08
