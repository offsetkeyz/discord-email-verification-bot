# Discord Bot Testing - Quick Reference Card

## Critical First Steps

1. **Update Discord Endpoint:**
   - Portal: https://discord.com/developers/applications
   - App ID: 1446567306170863686
   - Endpoint: `https://dmnw3lxadg36anjkjmkfbjegbi0vemfx.lambda-url.us-east-1.on.aws/`

2. **Start Monitoring:**
   ```bash
   aws logs tail /aws/lambda/discord-verification-handler --follow --region us-east-1
   ```

3. **Verify Resources:**
   ```bash
   aws dynamodb list-tables --region us-east-1 | grep discord
   aws lambda get-function --function-name discord-verification-handler --region us-east-1
   aws ses get-send-quota --region us-east-1
   ```

## Essential 6 Tests (30 minutes)

### Test 1: Admin Setup (5 min)
- Run `/setup-email-verification`
- Select role, channel, domains
- Verify message appears with button

### Test 2: Happy Path (5 min)
- Click "Start Verification"
- Submit valid .edu email
- Check inbox for code (<30 sec)
- Submit code
- Verify role assigned

### Test 3: Invalid Domain (2 min)
- Submit `test@gmail.com`
- Verify rejection with error message

### Test 4: Wrong Codes (5 min)
- Submit 3 wrong codes
- Verify lockout after 3 attempts

### Test 5: Rate Limit (3 min)
- Start verification twice rapidly
- Verify 60-second cooldown

### Test 6: Multi-User (10 min)
- 2 users verify concurrently
- Verify both succeed independently

## Key Information

**Deployment:**
- Region: us-east-1
- Guild ID: 704494754129510431
- Channel ID: 768351579773468672
- Role ID: 849471214711996486

**SES Status:**
- Production mode (can send to ANY email)
- No pre-verification needed
- Domain: thedailydecrypt.com

**Performance Targets:**
- Button response: <3 seconds
- Email delivery: <30 seconds
- Code verification: <3 seconds

## Common Commands

```bash
# Watch logs
aws logs tail /aws/lambda/discord-verification-handler --follow --region us-east-1

# Check sessions (should be 0-2)
aws dynamodb scan --table-name discord-verification-sessions --select COUNT --region us-east-1

# Check records (increases with each verification)
aws dynamodb scan --table-name discord-verification-records --select COUNT --region us-east-1

# Check SES stats
aws ses get-send-statistics --region us-east-1

# Get guild config
aws dynamodb get-item \
  --table-name discord-guild-configs \
  --key '{"guild_id": {"S": "704494754129510431"}}' \
  --region us-east-1
```

## Troubleshooting

| Issue | Quick Fix |
|-------|-----------|
| No email received | Check spam folder, verify FROM_EMAIL env var |
| Role not assigned | Bot role must be ABOVE verified role |
| App didn't respond | Check CloudWatch logs, verify 30s timeout |
| Modal not appearing | Check response time <3s, verify JSON format |
| Rate limit not working | Check DynamoDB sessions table has `created_at` |

## Success Criteria

- [ ] 6/6 essential tests pass
- [ ] 3+ successful verifications
- [ ] No Lambda errors
- [ ] Email delivery <30s average
- [ ] Roles assigned correctly
- [ ] No PII in logs

## Emergency Stop

1. Discord Portal > General Information
2. Clear "Interactions Endpoint URL"
3. Save Changes
4. Bot stops receiving interactions immediately

## Full Documentation

See `/home/offsetkeyz/claude_coding_projects/au-discord-bot/DISCORD_TESTING_GUIDE.md` for comprehensive testing scenarios and detailed troubleshooting.
