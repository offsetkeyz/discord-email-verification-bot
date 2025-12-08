#!/bin/bash
# Create CloudWatch alarms for SES monitoring

set -e

echo "Creating CloudWatch alarms for SES monitoring..."
echo ""

# Get SNS topic ARN for alarms (optional - comment out if no SNS topic)
# SNS_TOPIC_ARN=$(aws sns list-topics --query "Topics[?contains(TopicArn, 'ses-alerts')].TopicArn" --output text)
# ALARM_ACTIONS=""
# if [ -n "$SNS_TOPIC_ARN" ]; then
#     ALARM_ACTIONS="--alarm-actions $SNS_TOPIC_ARN"
#     echo "Using SNS topic for alarm notifications: $SNS_TOPIC_ARN"
# fi

echo "1. Creating bounce rate alarm (CRITICAL - AWS suspends at >5%)..."
aws cloudwatch put-metric-alarm \
    --alarm-name ses-high-bounce-rate-CRITICAL \
    --alarm-description "SES bounce rate exceeded 5% - risk of suspension" \
    --metric-name Reputation.BounceRate \
    --namespace AWS/SES \
    --statistic Average \
    --period 3600 \
    --threshold 0.05 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --treat-missing-data notBreaching

echo "   Created: ses-high-bounce-rate-CRITICAL"

echo ""
echo "2. Creating complaint rate alarm (CRITICAL - AWS suspends at >0.1%)..."
aws cloudwatch put-metric-alarm \
    --alarm-name ses-high-complaint-rate-CRITICAL \
    --alarm-description "SES complaint rate exceeded 0.1% - risk of suspension" \
    --metric-name Reputation.ComplaintRate \
    --namespace AWS/SES \
    --statistic Average \
    --period 3600 \
    --threshold 0.001 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --treat-missing-data notBreaching

echo "   Created: ses-high-complaint-rate-CRITICAL"

echo ""
echo "3. Creating bounce rate warning alarm (WARNING at 3%)..."
aws cloudwatch put-metric-alarm \
    --alarm-name ses-bounce-rate-warning \
    --alarm-description "SES bounce rate exceeded 3% - approaching critical threshold" \
    --metric-name Reputation.BounceRate \
    --namespace AWS/SES \
    --statistic Average \
    --period 3600 \
    --threshold 0.03 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --treat-missing-data notBreaching

echo "   Created: ses-bounce-rate-warning"

echo ""
echo "4. Creating complaint rate warning alarm (WARNING at 0.05%)..."
aws cloudwatch put-metric-alarm \
    --alarm-name ses-complaint-rate-warning \
    --alarm-description "SES complaint rate exceeded 0.05% - approaching critical threshold" \
    --metric-name Reputation.ComplaintRate \
    --namespace AWS/SES \
    --statistic Average \
    --period 3600 \
    --threshold 0.0005 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --treat-missing-data notBreaching

echo "   Created: ses-complaint-rate-warning"

echo ""
echo "5. Creating email failure rate alarm..."
aws cloudwatch put-metric-alarm \
    --alarm-name ses-email-failure-rate-high \
    --alarm-description "Email failure rate exceeded 10%" \
    --metrics '[
        {
            "Id": "failed",
            "MetricStat": {
                "Metric": {
                    "Namespace": "DiscordBot/SES",
                    "MetricName": "EmailsFailed"
                },
                "Period": 300,
                "Stat": "Sum"
            },
            "ReturnData": false
        },
        {
            "Id": "sent",
            "MetricStat": {
                "Metric": {
                    "Namespace": "DiscordBot/SES",
                    "MetricName": "EmailsSent"
                },
                "Period": 300,
                "Stat": "Sum"
            },
            "ReturnData": false
        },
        {
            "Id": "failure_rate",
            "Expression": "failed / (sent + failed) * 100",
            "ReturnData": true
        }
    ]' \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2 \
    --treat-missing-data notBreaching

echo "   Created: ses-email-failure-rate-high"

echo ""
echo "6. Creating suppressed email alarm..."
aws cloudwatch put-metric-alarm \
    --alarm-name ses-suppressed-emails-detected \
    --alarm-description "Emails are being suppressed due to bounces/complaints" \
    --metric-name EmailsSuppressed \
    --namespace DiscordBot/SES \
    --statistic Sum \
    --period 300 \
    --threshold 1 \
    --comparison-operator GreaterThanOrEqualToThreshold \
    --evaluation-periods 1 \
    --treat-missing-data notBreaching

echo "   Created: ses-suppressed-emails-detected"

echo ""
echo "============================================"
echo "CloudWatch alarms created successfully!"
echo "============================================"
echo ""
echo "Created alarms:"
echo "  - ses-high-bounce-rate-CRITICAL (>5%)"
echo "  - ses-high-complaint-rate-CRITICAL (>0.1%)"
echo "  - ses-bounce-rate-warning (>3%)"
echo "  - ses-complaint-rate-warning (>0.05%)"
echo "  - ses-email-failure-rate-high (>10%)"
echo "  - ses-suppressed-emails-detected (>=1)"
echo ""
echo "Next steps:"
echo "1. Create SNS topic for alarm notifications: aws sns create-topic --name ses-alerts"
echo "2. Subscribe to topic: aws sns subscribe --topic-arn <ARN> --protocol email --notification-endpoint your@email.com"
echo "3. Update alarms to add --alarm-actions <SNS-TOPIC-ARN>"
echo "4. Monitor CloudWatch console: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#alarmsV2:"
echo ""
