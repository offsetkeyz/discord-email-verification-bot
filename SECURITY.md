# Security Documentation

## Critical Security Procedures

### Bot Token Management

**⚠️ IMPORTANT:** The Discord bot token should NEVER be stored in code, configuration files, or git history.

#### Storing the Bot Token Securely

The bot token must be stored in AWS Systems Manager Parameter Store as a SecureString:

```bash
# Store the bot token in SSM
aws ssm put-parameter \
  --name /discord-bot/token \
  --value "YOUR_DISCORD_BOT_TOKEN_HERE" \
  --type SecureString \
  --description "Discord bot authentication token" \
  --overwrite
```

#### Rotating the Bot Token

If you suspect the bot token has been compromised, follow these steps immediately:

1. **Revoke the old token** (within 5 minutes):
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Select your application
   - Go to Bot section
   - Click "Reset Token"
   - Copy the new token immediately (it won't be shown again)

2. **Update AWS SSM with the new token** (within 10 minutes):
   ```bash
   aws ssm put-parameter \
     --name /discord-bot/token \
     --value "NEW_BOT_TOKEN_HERE" \
     --type SecureString \
     --overwrite
   ```

3. **Restart the Lambda function** (if using environment variables):
   ```bash
   # Update Lambda configuration to refresh environment
   aws lambda update-function-configuration \
     --function-name discord-verification-handler \
     --description "Token rotated on $(date)"
   ```

4. **Verify the new token works**:
   - Test the `/verify` command in Discord
   - Check CloudWatch logs for authentication errors

5. **Audit access logs**:
   ```bash
   # Check for suspicious activity
   aws logs tail /aws/lambda/discord-verification-handler \
     --since 24h \
     --filter-pattern "ERROR"
   ```

#### Token Storage Best Practices

✅ **DO:**
- Store tokens in AWS SSM Parameter Store or Secrets Manager
- Use IAM policies to restrict access to the token
- Enable CloudTrail logging for SSM parameter access
- Rotate tokens regularly (every 90 days)
- Use different tokens for dev/staging/prod environments

❌ **DON'T:**
- Store tokens in code files
- Commit tokens to git
- Share tokens via email or chat
- Store tokens in environment variables in Lambda (use SSM instead)
- Log the full token value

#### Checking Token Permissions

Verify the Lambda function can access the SSM parameter:

```bash
# Test SSM parameter access
aws ssm get-parameter \
  --name /discord-bot/token \
  --with-decryption \
  --query "Parameter.Value" \
  --output text

# Verify Lambda role has permission
aws iam get-role-policy \
  --role-name discord-verification-lambda-role \
  --policy-name discord-bot-policy
```

## Other Security Considerations

### Signature Verification
All Discord interactions MUST be verified using the Ed25519 signature. Never skip signature verification in production.

### Rate Limiting
The bot implements rate limiting to prevent abuse:
- Per-guild: 60-second cooldown
- Global per-user: 300-second cooldown (5 minutes)
- Maximum 3 verification attempts per session

### Data Encryption
All DynamoDB tables should have encryption at rest enabled:
```bash
aws dynamodb update-table \
  --table-name discord-verification-sessions \
  --sse-specification Enabled=true,SSEType=KMS
```

### IAM Permissions
Lambda execution role should follow the principle of least privilege. See `docs/iam-policy.json` for the recommended policy.

### Monitoring
Set up CloudWatch alarms for:
- Invalid signature attempts
- Failed authentications
- DynamoDB throttling
- Lambda errors

## Incident Response

If you suspect a security breach:

1. **Immediately revoke all tokens** (Discord bot token, AWS credentials if compromised)
2. **Check CloudWatch logs** for unauthorized activity
3. **Audit DynamoDB data** for tampering
4. **Review IAM access logs** in CloudTrail
5. **Notify server administrators**
6. **Document the incident** with timeline and impact
7. **Implement additional controls** to prevent recurrence

## Security Contacts

For security issues, contact:
- Project maintainer: [Add contact info]
- Emergency: Follow incident response plan above

## Security Updates

Last security review: 2025-12-07
Next scheduled review: [Set date]
