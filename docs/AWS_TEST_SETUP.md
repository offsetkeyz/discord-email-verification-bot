# AWS Test Environment Setup for Contributors

This guide helps contributors set up their own AWS test environment to develop and test changes safely without affecting production.

## Overview

You have three options for testing:

1. **LocalStack** (Free, no AWS account needed)
2. **AWS Test Account** (Recommended for realistic testing)
3. **Shared Test Tables** (If provided by maintainers)

## Option 1: LocalStack (No AWS Account)

LocalStack simulates AWS services locally on your machine.

### Install LocalStack

```bash
# Install LocalStack
pip install localstack

# Install AWS CLI (if not already installed)
pip install awscli-local
```

### Start LocalStack

```bash
# Start LocalStack with required services
localstack start -d

# Verify services are running
localstack status services
```

### Configure Environment

```bash
# Set endpoint URL for all AWS SDK calls
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
```

### Create Test Tables

```bash
# Create sessions table
awslocal dynamodb create-table \
  --table-name discord-verification-sessions-test \
  --attribute-definitions \
    AttributeName=user_guild_id,AttributeType=S \
  --key-schema \
    AttributeName=user_guild_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# Create records table
awslocal dynamodb create-table \
  --table-name discord-verification-records-test \
  --attribute-definitions \
    AttributeName=verification_id,AttributeType=S \
    AttributeName=email,AttributeType=S \
  --key-schema \
    AttributeName=verification_id,KeyType=HASH \
  --global-secondary-indexes \
    IndexName=email-index,KeySchema=[{AttributeName=email,KeyType=HASH}],Projection={ProjectionType=ALL} \
  --billing-mode PAY_PER_REQUEST

# Create guild configs table
awslocal dynamodb create-table \
  --table-name discord-guild-configs-test \
  --attribute-definitions \
    AttributeName=guild_id,AttributeType=S \
  --key-schema \
    AttributeName=guild_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### Limitations

- SES emails won't actually send (but you can test the logic)
- Lambda must be invoked locally, not via Function URL
- Slightly different behavior from real AWS

## Option 2: AWS Test Account (Recommended)

### Prerequisites

- AWS account (free tier covers most testing)
- AWS CLI configured
- IAM permissions to create resources

### 1. Create IAM Test User

Create a dedicated user for testing:

```bash
# Create test user
aws iam create-user --user-name discord-bot-contributor-test

# Create access key
aws iam create-access-key --user-name discord-bot-contributor-test
```

Save the Access Key ID and Secret Access Key.

### 2. Attach Test Policy

Create an IAM policy with minimum permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBTestAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/discord-*-test"
    },
    {
      "Sid": "LambdaTestAccess",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:InvokeFunction",
        "lambda:GetFunction",
        "lambda:DeleteFunction",
        "lambda:CreateFunctionUrlConfig",
        "lambda:DeleteFunctionUrlConfig"
      ],
      "Resource": "arn:aws:lambda:*:*:function:discord-*-test"
    },
    {
      "Sid": "SESTestAccess",
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail",
        "ses:VerifyEmailIdentity"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SSMTestAccess",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:PutParameter",
        "ssm:DeleteParameter"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/discord-bot-test/*"
    },
    {
      "Sid": "LogsAccess",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:GetLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/discord-*-test*"
    },
    {
      "Sid": "IAMPassRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::*:role/discord-*-test"
    }
  ]
}
```

Save this as `test-policy.json` and attach it:

```bash
# Create policy
aws iam create-policy \
  --policy-name DiscordBotTestPolicy \
  --policy-document file://test-policy.json

# Attach to user
aws iam attach-user-policy \
  --user-name discord-bot-contributor-test \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/DiscordBotTestPolicy
```

### 3. Create Test DynamoDB Tables

```bash
# Sessions table
aws dynamodb create-table \
  --table-name discord-verification-sessions-test \
  --attribute-definitions \
    AttributeName=user_guild_id,AttributeType=S \
  --key-schema \
    AttributeName=user_guild_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Enable TTL on sessions table
aws dynamodb update-time-to-live \
  --table-name discord-verification-sessions-test \
  --time-to-live-specification "Enabled=true, AttributeName=ttl" \
  --region us-east-1

# Records table with GSI
aws dynamodb create-table \
  --table-name discord-verification-records-test \
  --attribute-definitions \
    AttributeName=verification_id,AttributeType=S \
    AttributeName=email,AttributeType=S \
  --key-schema \
    AttributeName=verification_id,KeyType=HASH \
  --global-secondary-indexes \
    '[{
      "IndexName": "email-index",
      "KeySchema": [{"AttributeName":"email","KeyType":"HASH"}],
      "Projection": {"ProjectionType":"ALL"}
    }]' \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Guild configs table
aws dynamodb create-table \
  --table-name discord-guild-configs-test \
  --attribute-definitions \
    AttributeName=guild_id,AttributeType=S \
  --key-schema \
    AttributeName=guild_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 4. Create IAM Role for Lambda

```bash
# Trust policy for Lambda
cat > lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "lambda.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create role
aws iam create-role \
  --role-name discord-verification-lambda-role-test \
  --assume-role-policy-document file://lambda-trust-policy.json

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name discord-verification-lambda-role-test \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Attach your test policy
aws iam attach-role-policy \
  --role-name discord-verification-lambda-role-test \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/DiscordBotTestPolicy
```

### 5. Deploy Test Lambda Function

```bash
# Package the function
cd lambda
zip -r ../lambda-test.zip *.py
cd ..

# Create function
aws lambda create-function \
  --function-name discord-verification-handler-test \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/discord-verification-lambda-role-test \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda-test.zip \
  --timeout 30 \
  --memory-size 512 \
  --environment Variables="{
    DYNAMODB_SESSIONS_TABLE=discord-verification-sessions-test,
    DYNAMODB_RECORDS_TABLE=discord-verification-records-test,
    DYNAMODB_GUILD_CONFIGS_TABLE=discord-guild-configs-test,
    DISCORD_APP_ID=YOUR_APP_ID,
    DISCORD_PUBLIC_KEY=YOUR_PUBLIC_KEY,
    FROM_EMAIL=test@yourdomain.com
  }" \
  --region us-east-1

# Create Function URL (for Discord webhook)
aws lambda create-function-url-config \
  --function-name discord-verification-handler-test \
  --auth-type NONE \
  --region us-east-1
```

### 6. Configure SES (for Email Testing)

```bash
# Verify your test email address
aws ses verify-email-identity \
  --email-address test@yourdomain.com \
  --region us-east-1

# Check verification status
aws ses get-identity-verification-attributes \
  --identities test@yourdomain.com \
  --region us-east-1
```

**Note**: SES starts in sandbox mode - you can only send emails to verified addresses. This is perfect for testing!

### 7. Store Bot Token in SSM

```bash
aws ssm put-parameter \
  --name "/discord-bot-test/token" \
  --value "YOUR_TEST_BOT_TOKEN" \
  --type "SecureString" \
  --region us-east-1
```

## Updating Your Test Lambda

When you make code changes:

```bash
# Re-package
cd lambda
zip -r ../lambda-test.zip *.py
cd ..

# Update function code
aws lambda update-function-code \
  --function-name discord-verification-handler-test \
  --zip-file fileb://lambda-test.zip \
  --region us-east-1

# Wait for update to complete
aws lambda wait function-updated \
  --function-name discord-verification-handler-test \
  --region us-east-1
```

## Testing Your Changes

### 1. View Logs

```bash
# Tail logs in real-time
aws logs tail /aws/lambda/discord-verification-handler-test --follow --region us-east-1

# View recent logs
aws logs tail /aws/lambda/discord-verification-handler-test --since 5m --region us-east-1
```

### 2. Invoke Function Manually

```bash
# Test PING
aws lambda invoke \
  --function-name discord-verification-handler-test \
  --payload '{"body":"{\"type\":1}"}' \
  --region us-east-1 \
  response.json

cat response.json
```

### 3. Test in Discord

1. Get your Function URL from Lambda console
2. Configure it as Discord Interaction Endpoint
3. Test the `/setup` and verification flow

## Cost Management

### Expected Costs

With normal testing:
- **DynamoDB**: $0-1/month (on-demand, low volume)
- **Lambda**: $0 (free tier covers 1M requests)
- **SES**: $0 (sandbox mode)
- **Total**: ~$0-1/month

### Clean Up After Testing

```bash
# Delete Lambda function
aws lambda delete-function \
  --function-name discord-verification-handler-test \
  --region us-east-1

# Delete DynamoDB tables
aws dynamodb delete-table --table-name discord-verification-sessions-test --region us-east-1
aws dynamodb delete-table --table-name discord-verification-records-test --region us-east-1
aws dynamodb delete-table --table-name discord-guild-configs-test --region us-east-1

# Delete SSM parameters
aws ssm delete-parameter --name "/discord-bot-test/token" --region us-east-1
```

## Troubleshooting

### Lambda Function Won't Deploy

- Check IAM role has correct permissions
- Verify zip file contains all necessary files
- Check Python version compatibility (use 3.11)

### Can't Send Emails

- Verify email address in SES console
- Check you're in SES sandbox mode (expected)
- Add test recipient emails to verified identities

### DynamoDB Access Denied

- Check table names match environment variables
- Verify IAM policy allows table access
- Ensure table names end with `-test`

### Discord Webhook Not Working

- Verify Function URL is correct
- Check Discord app has correct public key
- View Lambda logs for detailed errors

## Option 3: Shared Test Tables

If the maintainers provide shared test DynamoDB tables, you'll receive:

- Read-only AWS credentials
- Table names
- Instructions for connecting

This option is simpler but may have limitations on what you can test.

## Next Steps

After setup:
1. Run the test suite: `pytest tests/`
2. Make your changes
3. Test locally and in AWS
4. Submit a pull request

## Questions?

- Check [CONTRIBUTING.md](../CONTRIBUTING.md) for general setup
- Open a GitHub Discussion for help
- Comment on your PR with specific questions
