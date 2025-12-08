# Deployment Checklist for Discord Email Verification Bot

This checklist ensures production readiness before deploying the Lambda function to AWS.

## Pre-Deployment Validation

### 1. Code Preparation

- [ ] All Lambda Python files present in `lambda/` directory
- [ ] No syntax errors (run `python -m py_compile lambda/*.py`)
- [ ] All imports resolve correctly
- [ ] `requirements.txt` is complete and valid
- [ ] Code review completed
- [ ] All tests passing (run `pytest tests/`)

### 2. AWS Infrastructure Setup

#### DynamoDB Tables

- [ ] Create `discord-verification-sessions` table
  - Partition key: `user_id` (String)
  - Sort key: `guild_id` (String)
  - Billing mode: On-demand (PAY_PER_REQUEST)
  - TTL enabled on `ttl` attribute

- [ ] Create `discord-verification-records` table
  - Partition key: `verification_id` (String)
  - Sort key: `created_at` (Number)
  - GSI: `user_guild-index`
    - Partition key: `user_guild_composite` (String)
    - Sort key: `created_at` (Number)
  - Billing mode: On-demand (PAY_PER_REQUEST)

- [ ] Create `discord-guild-configs` table
  - Partition key: `guild_id` (String)
  - Billing mode: On-demand (PAY_PER_REQUEST)

#### SES Configuration

- [ ] Verify sender email address in SES
- [ ] Move out of SES sandbox (production only)
  - Request production access via AWS Support
  - Verify sending limits increased
- [ ] Test email sending from verified address

#### SSM Parameter Store

- [ ] Create `/discord-bot/token` parameter
  - Type: SecureString
  - Value: Discord bot token from Developer Portal
  - Encryption: AWS managed key (or custom KMS key)

#### Lambda Function

- [ ] Create Lambda function
  - Runtime: Python 3.11 or 3.12
  - Architecture: x86_64 (or arm64 for cost savings)
  - Memory: 256 MB (minimum recommended)
  - Timeout: 30 seconds
  - Handler: `lambda_function.lambda_handler`

- [ ] Upload Lambda deployment package
  ```bash
  cd lambda
  pip install -r ../requirements.txt -t .
  zip -r function.zip .
  aws lambda update-function-code --function-name discord-verification-bot --zip-file fileb://function.zip
  ```

- [ ] Configure environment variables
  - `DISCORD_PUBLIC_KEY`: From Discord Developer Portal
  - `DISCORD_APP_ID`: From Discord Developer Portal
  - `DYNAMODB_SESSIONS_TABLE`: `discord-verification-sessions`
  - `DYNAMODB_RECORDS_TABLE`: `discord-verification-records`
  - `DYNAMODB_GUILD_CONFIGS_TABLE`: `discord-guild-configs`
  - `FROM_EMAIL`: Verified SES email address

#### IAM Permissions

- [ ] Create Lambda execution role with permissions:

  **DynamoDB:**
  ```json
  {
    "Effect": "Allow",
    "Action": [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query"
    ],
    "Resource": [
      "arn:aws:dynamodb:REGION:ACCOUNT:table/discord-verification-sessions",
      "arn:aws:dynamodb:REGION:ACCOUNT:table/discord-verification-records",
      "arn:aws:dynamodb:REGION:ACCOUNT:table/discord-verification-records/index/*",
      "arn:aws:dynamodb:REGION:ACCOUNT:table/discord-guild-configs"
    ]
  }
  ```

  **SES:**
  ```json
  {
    "Effect": "Allow",
    "Action": [
      "ses:SendEmail",
      "ses:SendRawEmail"
    ],
    "Resource": "*"
  }
  ```

  **SSM:**
  ```json
  {
    "Effect": "Allow",
    "Action": [
      "ssm:GetParameter",
      "ssm:GetParameters"
    ],
    "Resource": "arn:aws:ssm:REGION:ACCOUNT:parameter/discord-bot/*"
  }
  ```

  **CloudWatch Logs:**
  ```json
  {
    "Effect": "Allow",
    "Action": [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ],
    "Resource": "arn:aws:logs:REGION:ACCOUNT:log-group:/aws/lambda/discord-verification-bot:*"
  }
  ```

### 3. Lambda Function URL / API Gateway

Choose one:

#### Option A: Lambda Function URL (Recommended - Simpler)

- [ ] Create Function URL
  - Auth type: NONE (Discord handles auth via signatures)
  - CORS: Disabled
- [ ] Copy Function URL (e.g., `https://abc123.lambda-url.us-east-1.on.aws/`)

#### Option B: API Gateway (More Features)

- [ ] Create REST API
- [ ] Create POST method
- [ ] Set integration to Lambda function
- [ ] Deploy to stage (e.g., `prod`)
- [ ] Copy invoke URL

### 4. Discord Bot Configuration

- [ ] Go to Discord Developer Portal (https://discord.com/developers/applications)
- [ ] Select your application
- [ ] Navigate to "General Information"
  - Copy `APPLICATION ID`
  - Copy `PUBLIC KEY`
- [ ] Navigate to "Bot"
  - Copy bot token
  - Store in SSM Parameter Store
  - Enable required privileged intents (if using message content)
- [ ] Navigate to "OAuth2" > "URL Generator"
  - Select scopes: `bot`, `applications.commands`
  - Select permissions:
    - Manage Roles
    - View Channels
    - Send Messages
  - Copy generated URL for bot invitation

### 5. Register Slash Commands

Run this script to register slash commands (or use Discord Developer Portal):

```python
import requests
import os

BOT_TOKEN = os.environ['DISCORD_BOT_TOKEN']  # From SSM
APP_ID = os.environ['DISCORD_APP_ID']

url = f"https://discord.com/api/v10/applications/{APP_ID}/commands"

command = {
    "name": "setup-email-verification",
    "description": "Configure email verification for this server",
    "default_member_permissions": "8"  # Administrator only
}

headers = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json"
}

response = requests.post(url, json=command, headers=headers)
print(response.json())
```

### 6. Set Interaction Endpoint

- [ ] In Discord Developer Portal > "General Information"
- [ ] Set "Interactions Endpoint URL" to your Lambda Function URL or API Gateway URL
- [ ] Click "Save Changes"
- [ ] Discord will send PING request to verify endpoint
- [ ] Verify endpoint responds with PONG (check CloudWatch Logs)

## Post-Deployment Validation

### 1. Smoke Tests (Run Immediately After Deployment)

- [ ] PING test passes (Discord verifies endpoint)
- [ ] Lambda cold start completes within timeout
- [ ] CloudWatch log group created
- [ ] No errors in CloudWatch Logs

### 2. End-to-End Testing

- [ ] Invite bot to test Discord server (use OAuth2 URL from step 4)
- [ ] Run `/setup-email-verification` command as administrator
  - [ ] Role selection works
  - [ ] Channel selection works
  - [ ] Domain configuration works
  - [ ] Custom message works (optional)
  - [ ] Setup approval saves configuration
- [ ] Test verification flow as regular user
  - [ ] Click verification button
  - [ ] Receive verification email
  - [ ] Enter correct code - role assigned
  - [ ] Enter incorrect code - error message shown
  - [ ] Rate limiting works (60s cooldown)
- [ ] Verify DynamoDB tables contain expected data
  - [ ] Sessions table has active sessions
  - [ ] Records table has verification records
  - [ ] Guild configs table has guild configuration

### 3. Monitoring Setup

- [ ] Create CloudWatch dashboard
  - Lambda invocations
  - Lambda errors
  - Lambda duration
  - DynamoDB read/write capacity
  - SES send statistics

- [ ] Create CloudWatch alarms
  - [ ] Lambda error rate > 5%
  - [ ] Lambda duration > 25 seconds
  - [ ] Lambda throttling > 10/min
  - [ ] DynamoDB read/write throttling
  - [ ] SES bounce rate > 10%

- [ ] Set up SNS notifications for alarms
  - [ ] Email notifications
  - [ ] Slack/Discord webhook (optional)

### 4. Security Validation

- [ ] Signature verification works (invalid signatures rejected)
- [ ] Bot token stored in SSM (not in environment variables)
- [ ] PII redaction active in logs
- [ ] HTTPS only (no HTTP)
- [ ] Rate limiting prevents abuse
- [ ] Failed attempts tracked and limited

### 5. Performance Validation

- [ ] Cold start < 5 seconds
- [ ] Warm invocation < 1 second
- [ ] Discord response < 3 seconds (interaction timeout)
- [ ] Email delivery < 10 seconds
- [ ] DynamoDB queries < 100ms

## Rollback Procedures

If deployment fails or issues occur:

### 1. Immediate Rollback

- [ ] Revert Lambda function code to previous version
  ```bash
  aws lambda update-function-code \
    --function-name discord-verification-bot \
    --s3-bucket your-bucket \
    --s3-key previous-version.zip
  ```

### 2. Disable Bot

- [ ] Remove Interactions Endpoint URL in Discord Developer Portal
- [ ] This stops Discord from sending requests to Lambda

### 3. Investigation

- [ ] Check CloudWatch Logs for errors
- [ ] Review DynamoDB tables for data corruption
- [ ] Verify environment variables
- [ ] Test locally with sample events

### 4. Communication

- [ ] Notify server administrators
- [ ] Post status in bot's status channel (if configured)
- [ ] Document issue and resolution

## Production Best Practices

### Ongoing Maintenance

- [ ] Monitor CloudWatch metrics daily
- [ ] Review error logs weekly
- [ ] Update dependencies monthly
- [ ] Test backup and restore procedures quarterly
- [ ] Rotate bot token annually (or if compromised)

### Scaling Considerations

- [ ] Monitor DynamoDB throttling (upgrade to provisioned if needed)
- [ ] Monitor Lambda concurrent executions (request limit increase if needed)
- [ ] Monitor SES sending limits (request increase if needed)
- [ ] Consider multi-region deployment for HA (optional)

### Cost Optimization

- [ ] Review DynamoDB usage (on-demand vs provisioned)
- [ ] Set CloudWatch log retention (7-30 days)
- [ ] Use Lambda arm64 for 20% cost savings (optional)
- [ ] Monitor SES costs (free tier: 62,000 emails/month)

### Security Hardening

- [ ] Enable AWS CloudTrail for audit logging
- [ ] Use AWS Secrets Manager for enhanced secret rotation (optional)
- [ ] Implement IP whitelisting if using API Gateway (optional)
- [ ] Enable AWS WAF for DDoS protection (optional)

## Testing Commands

Run deployment tests before and after deployment:

```bash
# Run all deployment tests
cd /home/offsetkeyz/claude_coding_projects/au-discord-bot
pytest tests/deployment/ -v

# Run infrastructure tests only
pytest tests/deployment/test_infrastructure.py -v

# Run configuration tests only
pytest tests/deployment/test_configuration.py -v

# Run smoke tests only (quick validation)
pytest tests/deployment/ -v -m smoke

# Run with coverage
pytest tests/deployment/ -v --cov=lambda --cov-report=term-missing
```

## Troubleshooting

### Common Issues

**Lambda returns 401 for all requests:**
- Check `DISCORD_PUBLIC_KEY` environment variable
- Verify public key from Discord Developer Portal (64 hex characters)
- Check CloudWatch Logs for signature verification errors

**Lambda times out:**
- Increase timeout (recommend 30 seconds)
- Check network connectivity to AWS services
- Verify DynamoDB tables exist and are accessible
- Check if Lambda is in VPC without NAT Gateway

**Email not sending:**
- Verify sender email in SES
- Check if SES is in sandbox mode (can only send to verified addresses)
- Request production access for unrestricted sending
- Check IAM permissions for SES

**Bot commands not appearing in Discord:**
- Verify slash commands registered (use script above)
- Check bot has `applications.commands` scope
- Kick and re-invite bot if permissions changed
- Wait 1 hour for command cache to update

**DynamoDB access denied:**
- Check IAM role attached to Lambda
- Verify IAM policy has required permissions
- Check resource ARNs in IAM policy match table names
- Verify table names in environment variables match actual tables

---

**Deployment completed successfully!**

Mark the date and version:
- Deployment Date: ________________
- Lambda Version: ________________
- Deployed By: ________________
- Notes: ________________
