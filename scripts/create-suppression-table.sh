#!/bin/bash
# Create SES email suppression list DynamoDB table

set -e

echo "Creating SES suppression list DynamoDB table..."

aws dynamodb create-table \
    --table-name ses-email-suppression-list \
    --attribute-definitions \
        AttributeName=email,AttributeType=S \
        AttributeName=reason,AttributeType=S \
    --key-schema \
        AttributeName=email,KeyType=HASH \
        AttributeName=reason,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --tags Key=Purpose,Value=SESCompliance Key=Application,Value=DiscordBot

echo "Waiting for table to become active..."
aws dynamodb wait table-exists --table-name ses-email-suppression-list

echo ""
echo "Suppression list table created successfully!"
echo ""
echo "Table name: ses-email-suppression-list"
echo "Billing mode: PAY_PER_REQUEST"
echo "Keys: email (HASH), reason (RANGE)"
echo ""
echo "Next steps:"
echo "1. Set SUPPRESSION_LIST_TABLE environment variable in Lambda"
echo "2. Update Lambda IAM role to allow dynamodb:PutItem, GetItem, DeleteItem on this table"
echo "3. Deploy ses_notification_handler.py as a separate Lambda function"
echo "4. Create SNS topic for SES notifications"
echo "5. Subscribe the notification handler Lambda to the SNS topic"
