#!/bin/bash
# Deploy SES Compliance Features
# This script sets up bounce/complaint handling and monitoring

set -e

echo "============================================"
echo "SES Compliance Features Deployment"
echo "============================================"
echo ""

# Configuration
REGION=${AWS_DEFAULT_REGION:-us-east-1}
DOMAIN=${SES_DOMAIN:-thedailydecrypt.com}
MAIN_LAMBDA=${MAIN_LAMBDA_FUNCTION:-discord-verification-handler}
NOTIFICATION_HANDLER="ses-notification-handler"
SUPPRESSION_TABLE="ses-email-suppression-list"
SNS_TOPIC="ses-bounce-complaint-notifications"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v aws &> /dev/null; then
    error "AWS CLI not found. Please install AWS CLI."
    exit 1
fi
success "AWS CLI installed"

if ! command -v python3 &> /dev/null; then
    error "Python 3 not found. Please install Python 3.11+"
    exit 1
fi
success "Python 3 installed"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    error "AWS credentials not configured. Run: aws configure"
    exit 1
fi
success "AWS credentials configured"

echo ""

# Step 1: Create DynamoDB Suppression Table
echo "Step 1: Creating DynamoDB suppression table..."
if aws dynamodb describe-table --table-name $SUPPRESSION_TABLE &> /dev/null; then
    warning "Table $SUPPRESSION_TABLE already exists, skipping..."
else
    aws dynamodb create-table \
        --table-name $SUPPRESSION_TABLE \
        --attribute-definitions \
            AttributeName=email,AttributeType=S \
            AttributeName=reason,AttributeType=S \
        --key-schema \
            AttributeName=email,KeyType=HASH \
            AttributeName=reason,KeyType=RANGE \
        --billing-mode PAY_PER_REQUEST \
        --tags Key=Purpose,Value=SESCompliance Key=Application,Value=DiscordBot

    echo "Waiting for table to become active..."
    aws dynamodb wait table-exists --table-name $SUPPRESSION_TABLE
    success "Created table: $SUPPRESSION_TABLE"
fi
echo ""

# Step 2: Create SNS Topic
echo "Step 2: Creating SNS topic for SES notifications..."
SNS_TOPIC_ARN=$(aws sns create-topic --name $SNS_TOPIC --query 'TopicArn' --output text 2>/dev/null || \
    aws sns list-topics --query "Topics[?contains(TopicArn, '$SNS_TOPIC')].TopicArn" --output text)

if [ -n "$SNS_TOPIC_ARN" ]; then
    success "SNS topic: $SNS_TOPIC_ARN"
else
    error "Failed to create SNS topic"
    exit 1
fi
echo ""

# Step 3: Package and Deploy Notification Handler Lambda
echo "Step 3: Deploying notification handler Lambda..."

cd lambda
if [ -f ses-notification-handler.zip ]; then
    rm ses-notification-handler.zip
fi

zip -q ses-notification-handler.zip ses_notification_handler.py ses_suppression_list.py
success "Created deployment package"

# Create IAM role for notification handler if doesn't exist
ROLE_NAME="SESNotificationHandlerRole"
ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text 2>/dev/null || echo "")

if [ -z "$ROLE_ARN" ]; then
    echo "Creating IAM role for notification handler..."
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' > /dev/null

    # Attach basic execution policy
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

    # Add DynamoDB policy
    aws iam put-role-policy \
        --role-name $ROLE_NAME \
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
                "Resource": "arn:aws:dynamodb:'$REGION':*:table/'$SUPPRESSION_TABLE'"
            }]
        }'

    success "Created IAM role: $ROLE_NAME"

    # Wait for role to be ready
    echo "Waiting for IAM role to propagate..."
    sleep 10

    ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
else
    success "Using existing IAM role: $ROLE_NAME"
fi

# Create or update Lambda function
if aws lambda get-function --function-name $NOTIFICATION_HANDLER &> /dev/null; then
    echo "Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name $NOTIFICATION_HANDLER \
        --zip-file fileb://ses-notification-handler.zip > /dev/null
    success "Updated Lambda function: $NOTIFICATION_HANDLER"
else
    echo "Creating new Lambda function..."
    aws lambda create-function \
        --function-name $NOTIFICATION_HANDLER \
        --runtime python3.11 \
        --role $ROLE_ARN \
        --handler ses_notification_handler.lambda_handler \
        --zip-file fileb://ses-notification-handler.zip \
        --timeout 30 \
        --environment Variables="{SUPPRESSION_LIST_TABLE=$SUPPRESSION_TABLE,AWS_DEFAULT_REGION=$REGION}" \
        > /dev/null
    success "Created Lambda function: $NOTIFICATION_HANDLER"
fi

LAMBDA_ARN=$(aws lambda get-function --function-name $NOTIFICATION_HANDLER --query 'Configuration.FunctionArn' --output text)

cd ..
echo ""

# Step 4: Subscribe Lambda to SNS
echo "Step 4: Subscribing Lambda to SNS topic..."

# Check if subscription exists
EXISTING_SUB=$(aws sns list-subscriptions-by-topic \
    --topic-arn $SNS_TOPIC_ARN \
    --query "Subscriptions[?Endpoint=='$LAMBDA_ARN'].SubscriptionArn" \
    --output text)

if [ -n "$EXISTING_SUB" ]; then
    warning "Lambda already subscribed to SNS topic"
else
    aws sns subscribe \
        --topic-arn $SNS_TOPIC_ARN \
        --protocol lambda \
        --notification-endpoint $LAMBDA_ARN > /dev/null

    # Grant SNS permission to invoke Lambda
    aws lambda add-permission \
        --function-name $NOTIFICATION_HANDLER \
        --statement-id AllowSNSInvoke \
        --action lambda:InvokeFunction \
        --principal sns.amazonaws.com \
        --source-arn $SNS_TOPIC_ARN \
        &> /dev/null || true

    success "Subscribed Lambda to SNS topic"
fi
echo ""

# Step 5: Configure SES to publish to SNS
echo "Step 5: Configuring SES notifications..."

# Check if domain is verified
DOMAIN_STATUS=$(aws ses get-identity-verification-attributes \
    --identities $DOMAIN \
    --query "VerificationAttributes.\"$DOMAIN\".VerificationStatus" \
    --output text 2>/dev/null || echo "NotFound")

if [ "$DOMAIN_STATUS" != "Success" ]; then
    warning "Domain $DOMAIN is not verified in SES"
    warning "Run: aws ses verify-domain-identity --domain $DOMAIN"
    warning "Then add DNS records and wait for verification"
else
    success "Domain $DOMAIN is verified"

    # Configure bounce notifications
    aws ses set-identity-notification-topic \
        --identity $DOMAIN \
        --notification-type Bounce \
        --sns-topic $SNS_TOPIC_ARN

    # Configure complaint notifications
    aws ses set-identity-notification-topic \
        --identity $DOMAIN \
        --notification-type Complaint \
        --sns-topic $SNS_TOPIC_ARN

    # Disable email feedback forwarding
    aws ses set-identity-feedback-forwarding-enabled \
        --identity $DOMAIN \
        --no-forwarding-enabled

    success "Configured SES notifications for $DOMAIN"
fi
echo ""

# Step 6: Update main Lambda environment
echo "Step 6: Updating main Lambda function environment..."

if aws lambda get-function --function-name $MAIN_LAMBDA &> /dev/null; then
    # Get current environment variables
    CURRENT_ENV=$(aws lambda get-function-configuration \
        --function-name $MAIN_LAMBDA \
        --query 'Environment.Variables' \
        --output json)

    # Add SUPPRESSION_LIST_TABLE if not exists
    if echo "$CURRENT_ENV" | grep -q "SUPPRESSION_LIST_TABLE"; then
        warning "SUPPRESSION_LIST_TABLE already set in main Lambda"
    else
        # Automatically merge SUPPRESSION_LIST_TABLE into existing environment variables
        if ! command -v jq &> /dev/null; then
            warning "jq is not installed. Please install jq to automatically update Lambda environment variables."
            warning "Or manually add SUPPRESSION_LIST_TABLE=$SUPPRESSION_TABLE to $MAIN_LAMBDA environment."
        else
            UPDATED_ENV=$(echo "$CURRENT_ENV" | jq --arg table "$SUPPRESSION_TABLE" '. + {SUPPRESSION_LIST_TABLE: $table}')
            aws lambda update-function-configuration \
                --function-name $MAIN_LAMBDA \
                --environment "Variables=$UPDATED_ENV"
            success "Added SUPPRESSION_LIST_TABLE=$SUPPRESSION_TABLE to $MAIN_LAMBDA environment"
        fi
else
    warning "Main Lambda function $MAIN_LAMBDA not found"
    warning "Skipping environment update"
fi
echo ""

# Step 7: Create CloudWatch Alarms
echo "Step 7: Creating CloudWatch alarms..."
if [ -f scripts/create-ses-alarms.sh ]; then
    ./scripts/create-ses-alarms.sh > /dev/null 2>&1 || true
    success "Created CloudWatch alarms"
else
    warning "Alarm script not found at scripts/create-ses-alarms.sh"
    warning "Run manually: ./scripts/create-ses-alarms.sh"
fi
echo ""

# Summary
echo "============================================"
echo "Deployment Summary"
echo "============================================"
echo ""
success "DynamoDB table: $SUPPRESSION_TABLE"
success "SNS topic: $SNS_TOPIC_ARN"
success "Lambda function: $NOTIFICATION_HANDLER"
success "SES domain: $DOMAIN"
echo ""

echo "Next Steps:"
echo "1. Verify DNS records for $DOMAIN:"
echo "   ./scripts/verify-dns.sh $DOMAIN"
echo ""
echo "2. Update main Lambda ($MAIN_LAMBDA) IAM role with DynamoDB permissions"
echo "   Use policy from: docs/iam-policy-ses-compliance.json"
echo ""
echo "3. Test bounce handling:"
echo "   aws ses send-email --from noreply@$DOMAIN --destination bounce@simulator.amazonses.com --message ..."
echo ""
echo "4. Monitor CloudWatch dashboard:"
echo "   https://console.aws.amazon.com/cloudwatch/home?region=$REGION#alarmsV2:"
echo ""
echo "5. Review setup guide: docs/SES_SETUP_GUIDE.md"
echo ""

warning "IMPORTANT: Complete steps 1-4 before sending production emails!"
echo ""
