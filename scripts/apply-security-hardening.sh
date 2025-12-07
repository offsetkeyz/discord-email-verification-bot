#!/bin/bash
#
# Security Hardening Deployment Script
# Applies security configurations to the Discord verification bot infrastructure
#
# Usage: ./scripts/apply-security-hardening.sh
#

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Discord Bot Security Hardening${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Check required environment variables
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}ERROR: AWS_ACCOUNT_ID environment variable not set${NC}"
    echo "Export your AWS account ID: export AWS_ACCOUNT_ID=123456789012"
    exit 1
fi

if [ -z "$VERIFIED_EMAIL_ADDRESS" ]; then
    echo -e "${YELLOW}WARNING: VERIFIED_EMAIL_ADDRESS not set${NC}"
    echo "Using default: verificationcode.noreply@thedailydecrypt.com"
    VERIFIED_EMAIL_ADDRESS="verificationcode.noreply@thedailydecrypt.com"
fi

# Step 1: Enable DynamoDB Encryption at Rest
echo -e "${YELLOW}[1/6] Enabling DynamoDB encryption at rest...${NC}"
for table in discord-verification-sessions discord-verification-records discord-guild-configs; do
    echo "  - Encrypting table: $table"
    aws dynamodb update-table \
        --table-name "$table" \
        --sse-specification Enabled=true,SSEType=KMS \
        --region us-east-1 || echo "    (Table may already be encrypted or doesn't exist)"
done
echo -e "${GREEN}✓ DynamoDB encryption enabled${NC}"
echo ""

# Step 2: Update Lambda IAM Policy
echo -e "${YELLOW}[2/6] Updating Lambda IAM policy...${NC}"

# Replace placeholders in IAM policy
sed "s/\${AWS_ACCOUNT_ID}/$AWS_ACCOUNT_ID/g; s/\${VERIFIED_EMAIL_ADDRESS}/$VERIFIED_EMAIL_ADDRESS/g" \
    docs/iam-policy.json > /tmp/iam-policy-resolved.json

# Assume Lambda role name
LAMBDA_ROLE_NAME="${LAMBDA_ROLE_NAME:-discord-verification-lambda-role}"

echo "  - Applying policy to role: $LAMBDA_ROLE_NAME"
aws iam put-role-policy \
    --role-name "$LAMBDA_ROLE_NAME" \
    --policy-name discord-bot-policy \
    --policy-document file:///tmp/iam-policy-resolved.json \
    --region us-east-1

rm /tmp/iam-policy-resolved.json
echo -e "${GREEN}✓ IAM policy updated${NC}"
echo ""

# Step 3: Set CloudWatch Logs Retention
echo -e "${YELLOW}[3/6] Configuring CloudWatch Logs retention...${NC}"
LOG_GROUP="/aws/lambda/discord-verification-handler"

# Create log group if it doesn't exist
aws logs create-log-group \
    --log-group-name "$LOG_GROUP" \
    --region us-east-1 2>/dev/null || echo "  Log group already exists"

# Set 7-day retention
aws logs put-retention-policy \
    --log-group-name "$LOG_GROUP" \
    --retention-in-days 7 \
    --region us-east-1

echo -e "${GREEN}✓ CloudWatch Logs retention set to 7 days${NC}"
echo ""

# Step 4: Configure Lambda Reserved Concurrency
echo -e "${YELLOW}[4/6] Setting Lambda reserved concurrency...${NC}"
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-discord-verification-handler}"

aws lambda put-function-concurrency \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --reserved-concurrent-executions 10 \
    --region us-east-1 || echo "  (Function may not exist yet)"

echo -e "${GREEN}✓ Lambda concurrency limited to 10${NC}"
echo ""

# Step 5: Create CloudWatch Alarms
echo -e "${YELLOW}[5/6] Creating CloudWatch alarms...${NC}"

# Lambda errors alarm
aws cloudwatch put-metric-alarm \
    --alarm-name discord-bot-lambda-errors \
    --alarm-description "Alert on Lambda function errors" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=FunctionName,Value="$LAMBDA_FUNCTION_NAME" \
    --evaluation-periods 1 \
    --region us-east-1

# Invalid signature attempts
aws logs put-metric-filter \
    --log-group-name "$LOG_GROUP" \
    --filter-name InvalidSignatureFilter \
    --filter-pattern "ERROR: Invalid Discord signature" \
    --metric-transformations \
        metricName=InvalidSignatures,metricNamespace=DiscordBot,metricValue=1 \
    --region us-east-1

aws cloudwatch put-metric-alarm \
    --alarm-name discord-bot-invalid-signatures \
    --alarm-description "Alert on invalid signature attempts" \
    --metric-name InvalidSignatures \
    --namespace DiscordBot \
    --statistic Sum \
    --period 60 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --region us-east-1

echo -e "${GREEN}✓ CloudWatch alarms created${NC}"
echo ""

# Step 6: Verify Security Configuration
echo -e "${YELLOW}[6/6] Verifying security configuration...${NC}"

echo "  - Checking DynamoDB encryption:"
for table in discord-verification-sessions discord-verification-records discord-guild-configs; do
    encryption=$(aws dynamodb describe-table \
        --table-name "$table" \
        --query 'Table.SSEDescription.Status' \
        --output text \
        --region us-east-1 2>/dev/null || echo "NONE")

    if [ "$encryption" = "ENABLED" ]; then
        echo -e "    ${GREEN}✓${NC} $table: encrypted"
    else
        echo -e "    ${YELLOW}⚠${NC} $table: not encrypted or doesn't exist"
    fi
done

echo "  - Checking Lambda configuration:"
concurrency=$(aws lambda get-function-concurrency \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --query 'ReservedConcurrentExecutions' \
    --output text \
    --region us-east-1 2>/dev/null || echo "unlimited")
echo "    Reserved concurrency: $concurrency"

echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Security hardening complete!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "Next steps:"
echo "1. Review CloudWatch alarms in the AWS Console"
echo "2. Test the bot to ensure everything works correctly"
echo "3. Monitor logs for any security events"
echo ""
echo "Important: Don't forget to:"
echo "• Rotate the Discord bot token if it was compromised"
echo "• Update SSM parameters with secure values"
echo "• Test signature verification is working"
echo ""
