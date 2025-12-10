#!/bin/bash
#
# AWS Cleanup Script for Discord Email Verification Bot
# This script removes all AWS resources created by setup-aws.sh
#
# WARNING: This will DELETE all data in DynamoDB tables!
# Make sure you have backups if needed.
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration (must match setup-aws.sh)
FUNCTION_NAME="discord-verification-handler"
ROLE_NAME="discord-verification-lambda-role"
LAYER_NAME="discord-bot-dependencies"
SESSIONS_TABLE="discord-verification-sessions"
RECORDS_TABLE="discord-verification-records"
CONFIGS_TABLE="discord-guild-configs"
API_NAME="discord-verification-api"

# Get region
REGION=$(aws configure get region)
if [ -z "$REGION" ]; then
    REGION="us-east-1"
fi

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

echo ""
echo "========================================"
echo "AWS Resource Cleanup for Discord Bot"
echo "========================================"
echo ""
echo "Region: $REGION"
echo ""
echo -e "${RED}WARNING: This will DELETE the following resources:${NC}"
echo "  - Lambda Function: $FUNCTION_NAME"
echo "  - Lambda Layer: $LAYER_NAME"
echo "  - IAM Role: $ROLE_NAME"
echo "  - DynamoDB Tables: $SESSIONS_TABLE, $RECORDS_TABLE, $CONFIGS_TABLE"
echo "  - SSM Parameters: /discord-bot/*"
echo "  - API Gateway: $API_NAME"
echo ""
echo -e "${RED}ALL DATA WILL BE LOST!${NC}"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log_info "Cleanup cancelled"
    exit 0
fi

echo ""
log_step "Starting cleanup..."

# 1. Delete API Gateway
log_step "Deleting API Gateway..."
API_ID=$(aws apigatewayv2 get-apis --region $REGION --query "Items[?Name=='$API_NAME'].ApiId" --output text 2>/dev/null || echo "")
if [ -n "$API_ID" ]; then
    aws apigatewayv2 delete-api --api-id $API_ID --region $REGION
    log_info "Deleted API Gateway: $API_NAME ($API_ID)"
else
    log_warn "API Gateway not found: $API_NAME"
fi

# 2. Delete Lambda Function
log_step "Deleting Lambda Function..."
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &>/dev/null; then
    aws lambda delete-function --function-name $FUNCTION_NAME --region $REGION
    log_info "Deleted Lambda function: $FUNCTION_NAME"
else
    log_warn "Lambda function not found: $FUNCTION_NAME"
fi

# 3. Delete Lambda Layer (all versions)
log_step "Deleting Lambda Layer..."
LAYER_VERSIONS=$(aws lambda list-layer-versions --layer-name $LAYER_NAME --region $REGION --query 'LayerVersions[].Version' --output text 2>/dev/null || echo "")
if [ -n "$LAYER_VERSIONS" ]; then
    for VERSION in $LAYER_VERSIONS; do
        aws lambda delete-layer-version --layer-name $LAYER_NAME --version-number $VERSION --region $REGION
        log_info "Deleted layer version: $LAYER_NAME:$VERSION"
    done
else
    log_warn "Lambda layer not found: $LAYER_NAME"
fi

# 4. Delete IAM Role Policy
log_step "Deleting IAM Role Policy..."
if aws iam get-role --role-name $ROLE_NAME &>/dev/null; then
    aws iam delete-role-policy --role-name $ROLE_NAME --policy-name discord-verification-lambda-policy 2>/dev/null || log_warn "Role policy already deleted or not found"

    # Wait a moment for policy to detach
    sleep 2

    # Delete the role
    aws iam delete-role --role-name $ROLE_NAME
    log_info "Deleted IAM role: $ROLE_NAME"
else
    log_warn "IAM role not found: $ROLE_NAME"
fi

# 5. Delete SSM Parameters
log_step "Deleting SSM Parameters..."
SSM_PARAMS=$(aws ssm describe-parameters --region $REGION --query "Parameters[?starts_with(Name, '/discord-bot/')].Name" --output text 2>/dev/null || echo "")
if [ -n "$SSM_PARAMS" ]; then
    for PARAM in $SSM_PARAMS; do
        aws ssm delete-parameter --name "$PARAM" --region $REGION
        log_info "Deleted SSM parameter: $PARAM"
    done
else
    log_warn "No SSM parameters found with prefix /discord-bot/"
fi

# 6. Delete DynamoDB Tables
log_step "Deleting DynamoDB Tables..."

for TABLE in $SESSIONS_TABLE $RECORDS_TABLE $CONFIGS_TABLE; do
    if aws dynamodb describe-table --table-name $TABLE --region $REGION &>/dev/null; then
        aws dynamodb delete-table --table-name $TABLE --region $REGION
        log_info "Deleted DynamoDB table: $TABLE"
    else
        log_warn "DynamoDB table not found: $TABLE"
    fi
done

# Wait for tables to be deleted
log_step "Waiting for DynamoDB tables to be deleted..."
sleep 5

for TABLE in $SESSIONS_TABLE $RECORDS_TABLE $CONFIGS_TABLE; do
    if aws dynamodb describe-table --table-name $TABLE --region $REGION &>/dev/null; then
        log_info "Waiting for $TABLE to be deleted..."
        aws dynamodb wait table-not-exists --table-name $TABLE --region $REGION 2>/dev/null || true
    fi
done

echo ""
log_step "Cleanup complete!"
echo ""
echo -e "${GREEN}All AWS resources have been removed.${NC}"
echo ""
echo "You can now run ./setup-aws.sh to redeploy from scratch."
echo ""
