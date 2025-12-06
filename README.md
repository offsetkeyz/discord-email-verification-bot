# Discord Email Verification Bot (AWS Lambda)

A serverless Discord bot for email verification using AWS Lambda, DynamoDB, and SES. Supports multi-guild configuration with custom email domains and verification messages.

## 🚀 Quick Start

**Deploy the entire AWS infrastructure in one command:**

```bash
# Configure AWS CLI
aws configure

# Clone and run setup
git clone https://github.com/offsetkeyz/discord-email-verification-bot.git
cd discord-email-verification-bot
./setup-aws.sh
```

The automated setup script handles everything: DynamoDB tables, Lambda function, API Gateway, SES, IAM roles, and slash command registration. **Setup time: ~5 minutes.**

See [Setup](#setup) for detailed instructions.

---

## Features

- **🚀 One-Command Deployment** - Automated `setup-aws.sh` script deploys entire infrastructure
- **Serverless Architecture** - Runs on AWS Lambda with API Gateway webhook
- **Multi-Guild Support** - Each Discord server can configure their own:
  - Allowed email domains
  - Verified role
  - Custom verification message with emoji support
- **Email Verification** - 6-digit codes sent via AWS SES
- **Security Features**:
  - Request signature verification
  - Rate limiting (60-second cooldown between attempts)
  - Code expiration (15 minutes)
  - Maximum 3 verification attempts per code
- **Admin Setup Flow** - Interactive `/setup-email-verification` command for server configuration
- **Persistent Storage** - DynamoDB for session and verification tracking

## Architecture

### AWS Services

- **Lambda** - Bot logic and interaction handling
- **DynamoDB** - Three tables:
  - `discord-verification-sessions` - Active verification sessions (with TTL)
  - `discord-verification-records` - Permanent verification records
  - `discord-guild-configs` - Per-guild configuration
- **API Gateway** - HTTP webhook endpoint for Discord interactions
- **SES** - Email delivery for verification codes
- **SSM Parameter Store** - Secure storage for bot token

### Code Structure

```
lambda/
├── lambda_function.py          # Main Lambda handler and routing
├── handlers.py                 # Verification flow handlers
├── setup_handler.py            # /setup-email-verification command handlers
├── discord_interactions.py     # Discord API interaction types
├── discord_api.py              # Discord API calls (roles, messages)
├── dynamodb_operations.py      # DynamoDB operations
├── ses_email.py                # AWS SES email sending
├── verification_logic.py       # Pure verification logic functions
├── guild_config.py             # Guild configuration management
└── ssm_utils.py               # AWS SSM parameter store utils

setup-aws.sh                    # Automated AWS deployment script
register_slash_commands.py      # Script to register slash commands
```

## Prerequisites

- **AWS Account** with permissions to create:
  - Lambda functions
  - DynamoDB tables
  - SES verified email identity
  - IAM roles and policies
  - SSM parameters
  - API Gateway endpoints
- **Discord Application** from [Discord Developer Portal](https://discord.com/developers/applications)
- **Python 3.11** (for local development/testing)

## Setup

### 1. Discord Application Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" tab:
   - Reset token and copy it (save as `DISCORD_TOKEN`)
   - Enable these privileged intents:
     - **Server Members Intent** (required)
     - **Message Content Intent** (required for message link feature)
4. Go to "General Information":
   - Copy Application ID (save as `DISCORD_APP_ID`)
   - Copy Public Key (save as `DISCORD_PUBLIC_KEY`)
5. Go to "OAuth2" > "URL Generator":
   - Select scopes: `bot`, `applications.commands`
   - Select permissions:
     - Read Messages/View Channels
     - Send Messages
     - Manage Roles
   - Copy the URL and invite bot to your server

### 2. AWS Setup

**Choose one of the following setup methods:**

#### Option A: Automated Setup (Recommended)

We provide a setup script that automates the entire AWS deployment:

```bash
# Make sure you have AWS CLI configured
aws configure

# Run the setup script
./setup-aws.sh
```

The script will:
- ✅ Create all DynamoDB tables with proper schemas
- ✅ Set up SES email verification
- ✅ Create IAM role with appropriate permissions
- ✅ Store bot token in SSM Parameter Store
- ✅ Create Lambda function and layer
- ✅ Set up API Gateway endpoint
- ✅ Register Discord slash commands
- ✅ Provide you with the webhook URL to configure in Discord

**Time to complete:** ~5-10 minutes (mostly waiting for AWS resources)

After the script completes, follow the "Next Steps" it provides to finish Discord configuration.

---

#### Option B: Manual Setup

If you prefer to set up AWS resources manually, follow these detailed instructions:

##### Create DynamoDB Tables

```bash
# Sessions table (for active verification sessions)
aws dynamodb create-table \
  --table-name discord-verification-sessions \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=guild_id,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
    AttributeName=guild_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST

# Enable TTL for auto-cleanup
aws dynamodb update-time-to-live \
  --table-name discord-verification-sessions \
  --time-to-live-specification "Enabled=true, AttributeName=ttl"

# Records table (for permanent verification records)
aws dynamodb create-table \
  --table-name discord-verification-records \
  --attribute-definitions \
    AttributeName=verification_id,AttributeType=S \
    AttributeName=created_at,AttributeType=N \
    AttributeName=user_guild_composite,AttributeType=S \
  --key-schema \
    AttributeName=verification_id,KeyType=HASH \
    AttributeName=created_at,KeyType=RANGE \
  --global-secondary-indexes \
    "[{\"IndexName\":\"user_guild-index\",\"KeySchema\":[{\"AttributeName\":\"user_guild_composite\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"created_at\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}]" \
  --billing-mode PAY_PER_REQUEST

# Guild configs table
aws dynamodb create-table \
  --table-name discord-guild-configs \
  --attribute-definitions \
    AttributeName=guild_id,AttributeType=S \
  --key-schema \
    AttributeName=guild_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

#### Set up SES

```bash
# Verify your email address in SES
aws ses verify-email-identity --email-identity noreply@yourdomain.com

# Check verification status
aws ses get-identity-verification-attributes \
  --identities noreply@yourdomain.com

# Request production access (to send to any email)
# Go to AWS Console > SES > Account Dashboard > Request production access
```

#### Create IAM Role

Create a role `discord-verification-lambda-role` with this policy:

```json
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
        "arn:aws:dynamodb:*:*:table/discord-verification-sessions",
        "arn:aws:dynamodb:*:*:table/discord-verification-records",
        "arn:aws:dynamodb:*:*:table/discord-verification-records/index/*",
        "arn:aws:dynamodb:*:*:table/discord-guild-configs"
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
      "Resource": "arn:aws:ssm:*:*:parameter/discord-bot/*"
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
```

#### Store Bot Token in SSM

```bash
aws ssm put-parameter \
  --name /discord-bot/token \
  --value "YOUR_DISCORD_BOT_TOKEN" \
  --type SecureString
```

#### Create Lambda Function

```bash
# Create deployment package
cd lambda
zip -r ../lambda-deployment.zip *.py
cd ..

# Create Lambda function
aws lambda create-function \
  --function-name discord-verification-handler \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/discord-verification-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda-deployment.zip \
  --timeout 30 \
  --memory-size 512 \
  --environment "Variables={
    DYNAMODB_SESSIONS_TABLE=discord-verification-sessions,
    DYNAMODB_RECORDS_TABLE=discord-verification-records,
    DYNAMODB_GUILD_CONFIGS_TABLE=discord-guild-configs,
    DISCORD_PUBLIC_KEY=YOUR_PUBLIC_KEY,
    FROM_EMAIL=noreply@yourdomain.com
  }"

# Create Lambda layer for dependencies
pip install -r requirements.txt -t python/
zip -r discord-bot-dependencies.zip python/
aws lambda publish-layer-version \
  --layer-name discord-bot-dependencies \
  --zip-file fileb://discord-bot-dependencies.zip \
  --compatible-runtimes python3.11

# Attach layer to function
aws lambda update-function-configuration \
  --function-name discord-verification-handler \
  --layers arn:aws:lambda:REGION:ACCOUNT_ID:layer:discord-bot-dependencies:1
```

#### Create API Gateway

1. Go to API Gateway Console
2. Create HTTP API
3. Add integration to Lambda function `discord-verification-handler`
4. Create route: `POST /interactions`
5. Deploy API and copy the invoke URL

#### Configure Discord Webhook

1. Go back to Discord Developer Portal
2. Go to "General Information"
3. Set "Interactions Endpoint URL" to: `https://YOUR_API_GATEWAY_URL/interactions`
4. Discord will verify the endpoint (signature verification must be working)

### 3. Register Slash Commands

**Note:** If you used the automated setup script (`./setup-aws.sh`), this step is already done. Skip to [Usage](#usage).

**For manual setup only:**

```bash
# Create .env file
cp .env.example .env

# Edit .env with your values
nano .env

# Register commands
python3 register_slash_commands.py
```

## Usage

### For Server Administrators

Run `/setup-email-verification` to configure the bot for your server:

1. **Select Role** - Choose which role to assign when users verify
2. **Select Channel** - Choose which channel to post the verification message
3. **Enter Domains** - Specify allowed email domains (e.g., `yourschool.edu`)
4. **Create Message** - Either:
   - Create a message in Discord with emojis and copy the message link
   - Or skip to keep the existing message (when reconfiguring)
5. **Preview & Approve** - Review the configuration before it goes live

### For Users

1. Click the "Start Verification" button in the verification message
2. Enter your .edu email address
3. Check your email for a 6-digit code
4. Click "Submit Code" and enter the code
5. Get the verified role automatically!

## Local Development

```bash
# Clone repository
git clone https://github.com/yourusername/au-discord-bot.git
cd au-discord-bot

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Test locally (requires AWS credentials configured)
# Lambda can be tested with sam local or directly in AWS
```

## Deployment

```bash
# Create deployment package
python3 -m zipfile -c lambda-deployment.zip lambda/*.py

# Update Lambda function
aws lambda update-function-code \
  --function-name discord-verification-handler \
  --zip-file fileb://lambda-deployment.zip

# Tail logs to verify
aws logs tail /aws/lambda/discord-verification-handler --follow
```

## Monitoring

```bash
# View recent logs
aws logs tail /aws/lambda/discord-verification-handler --follow

# Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=discord-verification-handler \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum

# Query DynamoDB
aws dynamodb scan --table-name discord-guild-configs
aws dynamodb scan --table-name discord-verification-records
```

## Troubleshooting

### Discord shows "Application did not respond"

- Check Lambda logs for errors
- Verify signature verification is working
- Ensure Lambda has correct environment variables
- Check API Gateway integration

### Email not sending

- Verify SES email identity is verified
- Check SES is in production mode (not sandbox)
- Review Lambda logs for SES errors
- Ensure IAM role has SES permissions

### Role not being assigned

- Check bot has "Manage Roles" permission
- Ensure bot's role is ABOVE the verified role in hierarchy
- Verify role ID is correct in guild config
- Check Lambda has SSM parameter store access for bot token

### Rate limiting errors

- Users can only start verification once per 60 seconds
- This prevents spam and protects the email service
- Wait for the cooldown period to expire

## Security Considerations

- Bot token stored securely in SSM Parameter Store
- Request signature verification prevents unauthorized requests
- Rate limiting prevents abuse
- DynamoDB TTL auto-deletes old sessions
- Email addresses stored only for verification records
- All secrets in environment variables or SSM (never in code)

## Cost Estimate

With typical usage (100 verifications/month):

- **Lambda**: ~$0.20/month (generous estimate)
- **DynamoDB**: ~$0.25/month (on-demand pricing)
- **SES**: $0.10/1000 emails = ~$0.01/month
- **API Gateway**: ~$0.01/month
- **Total**: < $1/month

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

[Add your license here]

## Support

For issues or questions:
- Check Lambda logs in CloudWatch
- Review Discord bot permissions
- Verify AWS resources are correctly configured
- Open an issue on GitHub
