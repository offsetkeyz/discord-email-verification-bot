#!/bin/bash
#
# AWS Setup Script for Discord Email Verification Bot
# This script automates the deployment of all AWS resources needed for the bot
#
# Prerequisites:
# - AWS CLI installed and configured (aws configure)
# - Python 3.11+ installed
# - Valid Discord application (bot token, public key, app ID)
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
FUNCTION_NAME="discord-verification-handler"
ROLE_NAME="discord-verification-lambda-role"
LAYER_NAME="discord-bot-dependencies"
SESSIONS_TABLE="discord-verification-sessions"
RECORDS_TABLE="discord-verification-records"
CONFIGS_TABLE="discord-guild-configs"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}==>${NC} $1"
}

check_prerequisites() {
    log_step "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first:"
        log_error "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed."
        exit 1
    fi

    # Check jq (optional but helpful)
    if ! command -v jq &> /dev/null; then
        log_warn "jq is not installed. JSON output will be less readable."
        log_warn "Install with: sudo apt-get install jq (Ubuntu) or brew install jq (Mac)"
    fi

    log_info "All prerequisites met!"

    # Get AWS account info
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    REGION=$(aws configure get region)
    if [ -z "$REGION" ]; then
        REGION="us-east-1"
        log_warn "No default region set, using us-east-1"
    fi

    log_info "AWS Account: $ACCOUNT_ID"
    log_info "AWS Region: $REGION"
}

prompt_user_input() {
    log_step "Gathering configuration..."

    echo ""
    echo "Please provide the following information from your Discord application:"
    echo "https://discord.com/developers/applications"
    echo ""

    # Discord Bot Token
    read -p "Discord Bot Token: " DISCORD_TOKEN
    if [ -z "$DISCORD_TOKEN" ]; then
        log_error "Bot token is required"
        exit 1
    fi

    # Discord Public Key
    read -p "Discord Public Key: " DISCORD_PUBLIC_KEY
    if [ -z "$DISCORD_PUBLIC_KEY" ]; then
        log_error "Public key is required"
        exit 1
    fi

    # Discord App ID
    read -p "Discord Application ID: " DISCORD_APP_ID
    if [ -z "$DISCORD_APP_ID" ]; then
        log_error "Application ID is required"
        exit 1
    fi

    # SES From Email
    echo ""
    read -p "Email address to send verification codes from: " FROM_EMAIL
    if [ -z "$FROM_EMAIL" ]; then
        log_error "From email is required"
        exit 1
    fi

    echo ""
    log_info "Configuration collected!"
}

create_dynamodb_tables() {
    log_step "Creating DynamoDB tables..."

    # Sessions table
    if aws dynamodb describe-table --table-name $SESSIONS_TABLE &> /dev/null; then
        log_warn "Table $SESSIONS_TABLE already exists, skipping..."
    else
        log_info "Creating $SESSIONS_TABLE table..."
        aws dynamodb create-table \
            --table-name $SESSIONS_TABLE \
            --attribute-definitions \
                AttributeName=user_id,AttributeType=S \
                AttributeName=guild_id,AttributeType=S \
            --key-schema \
                AttributeName=user_id,KeyType=HASH \
                AttributeName=guild_id,KeyType=RANGE \
            --billing-mode PAY_PER_REQUEST \
            --region $REGION > /dev/null

        log_info "Waiting for table to be active..."
        aws dynamodb wait table-exists --table-name $SESSIONS_TABLE --region $REGION

        # Enable TTL
        log_info "Enabling TTL on $SESSIONS_TABLE..."
        aws dynamodb update-time-to-live \
            --table-name $SESSIONS_TABLE \
            --time-to-live-specification "Enabled=true, AttributeName=ttl" \
            --region $REGION > /dev/null

        log_info "✓ $SESSIONS_TABLE created"
    fi

    # Records table
    if aws dynamodb describe-table --table-name $RECORDS_TABLE &> /dev/null; then
        log_warn "Table $RECORDS_TABLE already exists, skipping..."
    else
        log_info "Creating $RECORDS_TABLE table..."
        aws dynamodb create-table \
            --table-name $RECORDS_TABLE \
            --attribute-definitions \
                AttributeName=verification_id,AttributeType=S \
                AttributeName=created_at,AttributeType=N \
                AttributeName=user_guild_composite,AttributeType=S \
            --key-schema \
                AttributeName=verification_id,KeyType=HASH \
                AttributeName=created_at,KeyType=RANGE \
            --global-secondary-indexes \
                "[{\"IndexName\":\"user_guild-index\",\"KeySchema\":[{\"AttributeName\":\"user_guild_composite\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"created_at\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}]" \
            --billing-mode PAY_PER_REQUEST \
            --region $REGION > /dev/null

        log_info "Waiting for table to be active..."
        aws dynamodb wait table-exists --table-name $RECORDS_TABLE --region $REGION

        log_info "✓ $RECORDS_TABLE created"
    fi

    # Guild configs table
    if aws dynamodb describe-table --table-name $CONFIGS_TABLE &> /dev/null; then
        log_warn "Table $CONFIGS_TABLE already exists, skipping..."
    else
        log_info "Creating $CONFIGS_TABLE table..."
        aws dynamodb create-table \
            --table-name $CONFIGS_TABLE \
            --attribute-definitions \
                AttributeName=guild_id,AttributeType=S \
            --key-schema \
                AttributeName=guild_id,KeyType=HASH \
            --billing-mode PAY_PER_REQUEST \
            --region $REGION > /dev/null

        log_info "Waiting for table to be active..."
        aws dynamodb wait table-exists --table-name $CONFIGS_TABLE --region $REGION

        log_info "✓ $CONFIGS_TABLE created"
    fi

    log_info "All DynamoDB tables ready!"
}

setup_ses() {
    log_step "Setting up AWS SES..."

    # Verify email identity
    log_info "Verifying email identity: $FROM_EMAIL"
    aws ses verify-email-identity --email-address "$FROM_EMAIL" --region $REGION 2>/dev/null || true

    log_warn "⚠️  IMPORTANT: Check your email ($FROM_EMAIL) and click the verification link!"
    log_warn "⚠️  The bot cannot send emails until the address is verified."
    echo ""
    read -p "Press Enter after you've verified the email address..."

    # Check verification status
    VERIFICATION_STATUS=$(aws ses get-identity-verification-attributes \
        --identities "$FROM_EMAIL" \
        --region $REGION \
        --query "VerificationAttributes.\"$FROM_EMAIL\".VerificationStatus" \
        --output text)

    if [ "$VERIFICATION_STATUS" = "Success" ]; then
        log_info "✓ Email verified successfully!"
    else
        log_warn "Email verification status: $VERIFICATION_STATUS"
        log_warn "You may need to verify it before sending emails."
    fi

    # Check if in sandbox mode
    log_info "Checking SES account status..."
    log_warn "Note: By default, SES is in sandbox mode (can only send to verified addresses)."
    log_warn "To send to any email address, request production access in the AWS Console:"
    log_warn "https://console.aws.amazon.com/ses/home?region=$REGION#/account"
}

create_iam_role() {
    log_step "Creating IAM role..."

    # Check if role exists
    if aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
        log_warn "IAM role $ROLE_NAME already exists, skipping creation..."
        ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
    else
        # Create trust policy
        TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

        log_info "Creating role $ROLE_NAME..."
        ROLE_ARN=$(aws iam create-role \
            --role-name $ROLE_NAME \
            --assume-role-policy-document "$TRUST_POLICY" \
            --description "Role for Discord verification Lambda function" \
            --query 'Role.Arn' \
            --output text)

        log_info "✓ Role created: $ROLE_ARN"
    fi

    # Create/update role policy
    ROLE_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:$REGION:$ACCOUNT_ID:table/$SESSIONS_TABLE",
        "arn:aws:dynamodb:$REGION:$ACCOUNT_ID:table/$RECORDS_TABLE",
        "arn:aws:dynamodb:$REGION:$ACCOUNT_ID:table/$RECORDS_TABLE/index/*",
        "arn:aws:dynamodb:$REGION:$ACCOUNT_ID:table/$CONFIGS_TABLE"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter"
      ],
      "Resource": "arn:aws:ssm:$REGION:$ACCOUNT_ID:parameter/discord-bot/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

    log_info "Attaching policy to role..."
    aws iam put-role-policy \
        --role-name $ROLE_NAME \
        --policy-name discord-verification-lambda-policy \
        --policy-document "$ROLE_POLICY"

    log_info "✓ IAM role configured"

    # Wait for role to propagate
    log_info "Waiting for IAM role to propagate (10 seconds)..."
    sleep 10
}

store_bot_token() {
    log_step "Storing bot token in SSM Parameter Store..."

    # Check if parameter exists
    if aws ssm get-parameter --name /discord-bot/token --region $REGION &> /dev/null; then
        log_warn "Parameter /discord-bot/token already exists"
        read -p "Overwrite with new token? (y/N): " OVERWRITE
        if [[ $OVERWRITE =~ ^[Yy]$ ]]; then
            aws ssm put-parameter \
                --name /discord-bot/token \
                --value "$DISCORD_TOKEN" \
                --type SecureString \
                --overwrite \
                --region $REGION > /dev/null
            log_info "✓ Bot token updated"
        else
            log_info "Keeping existing token"
        fi
    else
        aws ssm put-parameter \
            --name /discord-bot/token \
            --value "$DISCORD_TOKEN" \
            --type SecureString \
            --region $REGION > /dev/null
        log_info "✓ Bot token stored securely"
    fi
}

create_lambda_layer() {
    log_step "Creating Lambda layer with dependencies..."

    # Create temp directory
    LAYER_DIR=$(mktemp -d)
    mkdir -p "$LAYER_DIR/python"

    log_info "Installing Python dependencies..."
    pip install -r lambda-requirements.txt -t "$LAYER_DIR/python" --quiet

    # Create zip
    log_info "Creating layer package..."
    cd "$LAYER_DIR"
    zip -r9 layer.zip python > /dev/null

    # Upload layer
    log_info "Publishing layer to AWS..."
    LAYER_VERSION_ARN=$(aws lambda publish-layer-version \
        --layer-name $LAYER_NAME \
        --description "Dependencies for Discord verification bot" \
        --zip-file fileb://layer.zip \
        --compatible-runtimes python3.11 \
        --region $REGION \
        --query 'LayerVersionArn' \
        --output text)

    # Cleanup
    cd - > /dev/null
    rm -rf "$LAYER_DIR"

    log_info "✓ Layer created: $LAYER_VERSION_ARN"
}

create_lambda_function() {
    log_step "Creating Lambda function..."

    # Create deployment package
    log_info "Creating deployment package..."
    cd lambda
    zip -r ../lambda-deployment.zip *.py > /dev/null
    cd ..

    # Check if function exists
    if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
        log_warn "Lambda function $FUNCTION_NAME already exists"
        log_info "Updating function code..."
        aws lambda update-function-code \
            --function-name $FUNCTION_NAME \
            --zip-file fileb://lambda-deployment.zip \
            --region $REGION > /dev/null

        log_info "Updating function configuration..."
        aws lambda update-function-configuration \
            --function-name $FUNCTION_NAME \
            --environment "Variables={
                DYNAMODB_SESSIONS_TABLE=$SESSIONS_TABLE,
                DYNAMODB_RECORDS_TABLE=$RECORDS_TABLE,
                DYNAMODB_GUILD_CONFIGS_TABLE=$CONFIGS_TABLE,
                DISCORD_PUBLIC_KEY=$DISCORD_PUBLIC_KEY,
                DISCORD_APP_ID=$DISCORD_APP_ID,
                FROM_EMAIL=$FROM_EMAIL,
                AWS_REGION=$REGION
            }" \
            --region $REGION > /dev/null

        log_info "✓ Lambda function updated"
    else
        log_info "Creating new Lambda function..."
        FUNCTION_ARN=$(aws lambda create-function \
            --function-name $FUNCTION_NAME \
            --runtime python3.11 \
            --role $ROLE_ARN \
            --handler lambda_function.lambda_handler \
            --zip-file fileb://lambda-deployment.zip \
            --timeout 30 \
            --memory-size 512 \
            --environment "Variables={
                DYNAMODB_SESSIONS_TABLE=$SESSIONS_TABLE,
                DYNAMODB_RECORDS_TABLE=$RECORDS_TABLE,
                DYNAMODB_GUILD_CONFIGS_TABLE=$CONFIGS_TABLE,
                DISCORD_PUBLIC_KEY=$DISCORD_PUBLIC_KEY,
                DISCORD_APP_ID=$DISCORD_APP_ID,
                FROM_EMAIL=$FROM_EMAIL,
                AWS_REGION=$REGION
            }" \
            --region $REGION \
            --query 'FunctionArn' \
            --output text)

        log_info "✓ Lambda function created: $FUNCTION_ARN"
    fi

    # Attach layer
    log_info "Attaching layer to function..."
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --layers $LAYER_VERSION_ARN \
        --region $REGION > /dev/null

    log_info "✓ Lambda function ready"
}

create_api_gateway() {
    log_step "Creating API Gateway..."

    # Check if API exists
    API_ID=$(aws apigatewayv2 get-apis --region $REGION --query "Items[?Name=='discord-verification-api'].ApiId" --output text)

    if [ ! -z "$API_ID" ]; then
        log_warn "API Gateway already exists: $API_ID"
    else
        log_info "Creating HTTP API..."
        API_ID=$(aws apigatewayv2 create-api \
            --name discord-verification-api \
            --protocol-type HTTP \
            --region $REGION \
            --query 'ApiId' \
            --output text)

        log_info "✓ API created: $API_ID"
    fi

    # Get Lambda ARN
    LAMBDA_ARN=$(aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query 'Configuration.FunctionArn' --output text)

    # Create integration
    log_info "Creating Lambda integration..."
    INTEGRATION_ID=$(aws apigatewayv2 create-integration \
        --api-id $API_ID \
        --integration-type AWS_PROXY \
        --integration-uri $LAMBDA_ARN \
        --payload-format-version 2.0 \
        --region $REGION \
        --query 'IntegrationId' \
        --output text 2>/dev/null || \
        aws apigatewayv2 get-integrations --api-id $API_ID --region $REGION --query 'Items[0].IntegrationId' --output text)

    # Create route
    log_info "Creating route..."
    aws apigatewayv2 create-route \
        --api-id $API_ID \
        --route-key 'POST /interactions' \
        --target "integrations/$INTEGRATION_ID" \
        --region $REGION > /dev/null 2>&1 || log_warn "Route may already exist"

    # Create/update stage
    log_info "Creating stage..."
    aws apigatewayv2 create-stage \
        --api-id $API_ID \
        --stage-name '$default' \
        --auto-deploy \
        --region $REGION > /dev/null 2>&1 || log_warn "Stage may already exist"

    # Add Lambda permission for API Gateway
    log_info "Granting API Gateway permission to invoke Lambda..."
    aws lambda add-permission \
        --function-name $FUNCTION_NAME \
        --statement-id apigateway-invoke \
        --action lambda:InvokeFunction \
        --principal apigatewayv2.amazonaws.com \
        --source-arn "arn:aws:execute-api:$REGION:$ACCOUNT_ID:$API_ID/*/*/interactions" \
        --region $REGION > /dev/null 2>&1 || log_warn "Permission may already exist"

    # Get API endpoint
    API_ENDPOINT=$(aws apigatewayv2 get-api --api-id $API_ID --region $REGION --query 'ApiEndpoint' --output text)

    log_info "✓ API Gateway ready"
    log_info "API Endpoint: ${API_ENDPOINT}/interactions"
}

update_env_file() {
    log_step "Updating .env file..."

    cat > .env <<EOF
# Discord Bot Configuration
# Get these from https://discord.com/developers/applications

# Your Discord Application ID
DISCORD_APP_ID=$DISCORD_APP_ID

# Your Discord bot token (used for slash command registration and API calls)
DISCORD_TOKEN=$DISCORD_TOKEN

# Your Discord application's public key (used for signature verification)
DISCORD_PUBLIC_KEY=$DISCORD_PUBLIC_KEY

# Email address to send verification codes from (must be verified in AWS SES)
FROM_EMAIL=$FROM_EMAIL

# AWS Region (should match where your resources are deployed)
AWS_REGION=$REGION
EOF

    log_info "✓ .env file updated"
}

register_slash_commands() {
    log_step "Registering slash commands..."

    log_info "Running register_slash_commands.py..."
    python3 register_slash_commands.py

    log_info "✓ Slash commands registered"
}

print_summary() {
    log_step "Setup Complete! 🎉"

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "                    DEPLOYMENT SUMMARY                          "
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "✓ DynamoDB Tables:"
    echo "  - $SESSIONS_TABLE"
    echo "  - $RECORDS_TABLE"
    echo "  - $CONFIGS_TABLE"
    echo ""
    echo "✓ IAM Role: $ROLE_NAME"
    echo ""
    echo "✓ Lambda Function: $FUNCTION_NAME"
    echo ""
    echo "✓ API Gateway Endpoint:"
    echo "  ${API_ENDPOINT}/interactions"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "                    NEXT STEPS                                  "
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "1. Configure Discord Interactions Endpoint:"
    echo "   - Go to: https://discord.com/developers/applications/$DISCORD_APP_ID/information"
    echo "   - Set 'Interactions Endpoint URL' to:"
    echo "     ${API_ENDPOINT}/interactions"
    echo ""
    echo "2. Invite bot to your Discord server:"
    echo "   - Go to: https://discord.com/developers/applications/$DISCORD_APP_ID/oauth2/url-generator"
    echo "   - Select scopes: bot, applications.commands"
    echo "   - Select permissions: Manage Roles, Send Messages, Read Messages"
    echo "   - Copy the generated URL and open in browser"
    echo ""
    echo "3. Run /setup-email-verification in your Discord server to configure"
    echo ""
    echo "4. (Optional) Request SES production access to send to any email:"
    echo "   https://console.aws.amazon.com/ses/home?region=$REGION#/account"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
}

# Main execution
main() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "     Discord Email Verification Bot - AWS Setup Script         "
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    check_prerequisites
    prompt_user_input
    create_dynamodb_tables
    setup_ses
    create_iam_role
    store_bot_token
    create_lambda_layer
    create_lambda_function
    create_api_gateway
    update_env_file
    register_slash_commands
    print_summary
}

# Run main function
main
