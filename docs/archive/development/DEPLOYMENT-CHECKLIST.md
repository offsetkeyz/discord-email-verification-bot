# Fresh Deployment Checklist

Quick reference for deploying the Discord Email Verification Bot from scratch.

---

## Pre-Deployment Checks

### AWS Prerequisites
- [ ] AWS CLI installed: `aws --version`
- [ ] AWS credentials configured: `aws configure`
- [ ] Test AWS access: `aws sts get-caller-identity`
- [ ] Confirm region: `aws configure get region` (should be us-east-1)

### Discord Prerequisites
- [ ] Discord application created at https://discord.com/developers/applications
- [ ] Bot user created for the application
- [ ] Copy these values (you'll need them):
  - [ ] Application ID (from General Information)
  - [ ] Public Key (from General Information)
  - [ ] Bot Token (from Bot section - click Reset Token if needed)

### Email Prerequisites
- [ ] SES email or domain verified
- [ ] Know the FROM_EMAIL address to use
- [ ] SES out of sandbox (or verify recipient emails for testing)

### Local Prerequisites
- [ ] Python 3.11+ installed: `python3 --version`
- [ ] pip installed: `pip --version`
- [ ] In project directory: `cd /home/offsetkeyz/claude_coding_projects/au-discord-bot`

---

## Deployment Steps

### Step 1: Cleanup Existing Resources (Optional)
Only run if you want to start completely fresh:

```bash
./cleanup-aws.sh
# Type 'yes' when prompted
# Wait for completion (~30 seconds)
```

### Step 2: Run Setup Script

```bash
./setup-aws.sh
```

The script will prompt you for:
1. **Discord Bot Token** - Paste from Discord Developer Portal
2. **Discord Public Key** - Paste from Discord Developer Portal
3. **Discord Application ID** - Paste from Discord Developer Portal
4. **FROM_EMAIL** - Enter your verified SES email

### Step 3: Verify SES Email
- Check inbox for SES verification email
- Click the verification link
- Press Enter in the terminal to continue

### Step 4: Wait for Deployment
The script will automatically:
- Create 3 DynamoDB tables (sessions, records, configs)
- Create IAM role with proper permissions
- Store bot token in SSM Parameter Store
- Create Lambda layer with PyNaCl and requests
- Deploy Lambda function with all code
- Create API Gateway endpoint
- Register slash commands with Discord

**Expected time:** 2-3 minutes

### Step 5: Configure Discord Interactions Endpoint
1. Copy the API endpoint URL from the script output (looks like: https://xxxxx.execute-api.us-east-1.amazonaws.com/interactions)
2. Go to https://discord.com/developers/applications/YOUR_APP_ID/information
3. Paste the URL into "Interactions Endpoint URL"
4. Discord will send a test ping - if successful, it will save the URL
5. If it fails, check CloudWatch logs for errors

### Step 6: Invite Bot to Server
1. Go to https://discord.com/developers/applications/YOUR_APP_ID/oauth2/url-generator
2. Select scopes:
   - [x] bot
   - [x] applications.commands
3. Select bot permissions:
   - [x] Manage Roles
   - [x] Send Messages
   - [x] Read Messages/View Channels
4. Copy the generated URL and open in browser
5. Select your server and authorize

### Step 7: Run Setup in Discord
1. In your Discord server, type: `/setup-email-verification`
2. Follow the setup wizard:
   - Select verification role
   - Select channel for verification message
   - Configure allowed email domains (or use defaults)
   - Optionally customize the verification message
   - Review and approve

### Step 8: Test Verification Flow
1. Click "Verify Email" button in the designated channel
2. Enter your .edu email address
3. Check email for verification code
4. Enter the 6-digit code
5. Confirm you receive the verification role

---

## Post-Deployment Verification

### Check Lambda Function
```bash
aws lambda get-function --function-name discord-verification-handler --region us-east-1
```

Should show:
- Runtime: python3.11
- Handler: lambda_function.lambda_handler
- Environment variables: DISCORD_PUBLIC_KEY, DISCORD_APP_ID, FROM_EMAIL, AWS_REGION, and 3 DynamoDB table names

### Check DynamoDB Tables
```bash
aws dynamodb list-tables --region us-east-1
```

Should show:
- discord-verification-sessions
- discord-verification-records
- discord-guild-configs

### Check IAM Role
```bash
aws iam get-role --role-name discord-verification-lambda-role
```

Should exist with trust policy for lambda.amazonaws.com

### Check SSM Parameter
```bash
aws ssm get-parameter --name /discord-bot/token --region us-east-1 --with-decryption
```

Should return your bot token (encrypted)

### Check Lambda Logs
```bash
aws logs tail /aws/lambda/discord-verification-handler --follow
```

Should show logs when you interact with the bot

---

## Troubleshooting

### Issue: Discord says "Interactions Endpoint URL verification failed"
**Solution:**
1. Check CloudWatch logs: `aws logs tail /aws/lambda/discord-verification-handler --follow`
2. Verify DISCORD_PUBLIC_KEY environment variable matches Discord Developer Portal
3. Make sure API Gateway endpoint is correct (should end with /interactions)
4. Try waiting 30 seconds and retrying (Lambda cold start)

### Issue: Email not sending
**Solution:**
1. Verify SES email is verified: `aws ses get-identity-verification-attributes --identities YOUR_EMAIL --region us-east-1`
2. Check if SES is in sandbox mode (can only send to verified emails)
3. Check Lambda logs for SES errors
4. Verify FROM_EMAIL environment variable is correct

### Issue: Bot commands not appearing
**Solution:**
1. Wait up to 1 hour (Discord caches commands globally)
2. Check if commands registered: Look at script output from `register_slash_commands.py`
3. Try inviting bot to a new server (new servers get commands immediately)
4. Verify bot has applications.commands scope

### Issue: Verification code expired
**Solution:**
- Codes expire after 15 minutes by default
- User must click "Verify Email" again to get a new code
- Old codes are automatically invalidated

### Issue: User already verified error
**Solution:**
1. Check if user already has the verification role
2. Admin can remove role and user can verify again
3. Check DynamoDB records table for verification history

### Issue: Lambda timeout
**Solution:**
1. Check Lambda timeout setting (should be 30 seconds)
2. Check SES email sending time in logs
3. Increase timeout if needed: `aws lambda update-function-configuration --function-name discord-verification-handler --timeout 60 --region us-east-1`

---

## Monitoring

### View Recent Logs
```bash
aws logs tail /aws/lambda/discord-verification-handler --since 1h
```

### View Verification Sessions
```bash
aws dynamodb scan --table-name discord-verification-sessions --region us-east-1
```

### View Verification Records
```bash
aws dynamodb scan --table-name discord-verification-records --region us-east-1
```

### View Guild Configs
```bash
aws dynamodb scan --table-name discord-guild-configs --region us-east-1
```

### Check Lambda Metrics
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=discord-verification-handler \
  --start-time 2024-12-08T00:00:00Z \
  --end-time 2024-12-08T23:59:59Z \
  --period 3600 \
  --statistics Sum \
  --region us-east-1
```

---

## Clean Uninstall

To completely remove all resources:

```bash
./cleanup-aws.sh
# Type 'yes' when prompted
```

This will delete:
- Lambda function
- Lambda layer (all versions)
- IAM role and policy
- All 3 DynamoDB tables (ALL DATA LOST)
- SSM parameters (bot token)
- API Gateway

**Note:** This does NOT remove:
- SES email verification
- Discord application
- Bot from servers

---

## Quick Reference

### Key Files
- `setup-aws.sh` - Main deployment script
- `cleanup-aws.sh` - Resource cleanup script
- `register_slash_commands.py` - Register Discord commands
- `lambda/` - All Lambda function code (12 files)
- `lambda-requirements.txt` - Lambda dependencies (PyNaCl, requests)
- `.env` - Local environment variables (created by setup script)

### AWS Resources Created
- Lambda: `discord-verification-handler`
- Layer: `discord-bot-dependencies`
- IAM Role: `discord-verification-lambda-role`
- DynamoDB: `discord-verification-sessions`, `discord-verification-records`, `discord-guild-configs`
- SSM: `/discord-bot/token`
- API Gateway: `discord-verification-api`

### Environment Variables
Lambda function uses:
- `DISCORD_PUBLIC_KEY` - For signature verification
- `DISCORD_APP_ID` - For Discord API calls
- `FROM_EMAIL` - SES sender address
- `AWS_REGION` - AWS region (us-east-1)
- `DYNAMODB_SESSIONS_TABLE` - Sessions table name
- `DYNAMODB_RECORDS_TABLE` - Records table name
- `DYNAMODB_GUILD_CONFIGS_TABLE` - Configs table name

---

## Support

For issues or questions:
1. Check CloudWatch logs first
2. Review AWS-SETUP-REVIEW-REPORT.md for detailed information
3. Verify all environment variables are set correctly
4. Test with a fresh Discord server to rule out caching issues

**Last Updated:** December 8, 2024
