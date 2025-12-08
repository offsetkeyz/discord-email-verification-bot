# Testing Quick Start Guide
## Discord Email Verification Bot - Post-Deployment Testing

**Last Updated:** 2025-12-08
**For:** Testing after PRs #16 and #17 merged to main

---

## 1. Critical Pre-Testing Setup (DO THIS FIRST)

### Verify Your Test Emails in SES (CRITICAL for Sandbox)

Since SES is in sandbox mode, you MUST verify every email address before testing:

```bash
# Verify your primary test email
aws ses verify-email-identity \
  --email-identity your.name@auburn.edu \
  --region us-east-1

# Verify additional test emails for multi-user testing
aws ses verify-email-identity \
  --email-identity colleague@auburn.edu \
  --region us-east-1
```

**Important:** Check your email inbox for verification emails from AWS and click the links!

### Verify AWS Resources Exist

```bash
# Quick check all resources are ready
aws dynamodb list-tables --region us-east-1 | grep discord
aws lambda get-function --function-name discord-verification-handler --region us-east-1 > /dev/null && echo "Lambda OK"
aws ses get-send-quota --region us-east-1
```

---

## 2. Start Monitoring

Open a terminal and start watching logs:

```bash
aws logs tail /aws/lambda/discord-verification-handler --follow --region us-east-1
```

Keep this running during all tests to see real-time feedback.

---

## 3. Essential Tests (30 Minutes)

### Test 1: Admin Setup (5 min)

1. In Discord, run: `/setup-email-verification`
2. Select "Verified Student" role
3. Select "#verification" channel
4. Enter domains: `auburn.edu,test.edu`
5. Approve setup
6. Verify message appears in #verification channel

**Success:** Message with "Start Verification" button appears

---

### Test 2: Happy Path Verification (5 min)

1. Click "Start Verification" button
2. Enter your verified .edu email (e.g., `yourname@auburn.edu`)
3. Check email inbox (wait up to 30 seconds)
4. Click "Submit Code" in Discord
5. Enter 6-digit code from email
6. Verify you receive "Verified Student" role

**Success:** Role assigned, can access #verified-only channel

---

### Test 3: Invalid Email Domain (2 min)

1. Click "Start Verification"
2. Enter: `test@gmail.com`
3. Submit

**Success:** Error message lists allowed domains, no email sent

---

### Test 4: Wrong Code Attempts (5 min)

1. Start verification, submit valid email
2. Click "Submit Code"
3. Enter wrong code: `000000`
4. Verify: "2 attempt(s) remaining"
5. Submit wrong code again: `111111`
6. Verify: "1 attempt(s) remaining"
7. Submit wrong code again: `222222`
8. Verify: "Too many failed attempts"

**Success:** Locked out after 3 attempts, can restart verification

---

### Test 5: Rate Limiting (3 min)

1. Complete a verification
2. Immediately click "Start Verification" again
3. Verify: "Please wait X seconds"
4. Wait 60 seconds
5. Try again - should work

**Success:** Rate limit enforced for 60 seconds

---

### Test 6: Multi-User Testing (10 min)

**Need:** 2 Discord accounts, 2 verified .edu emails

1. User 1 starts verification
2. User 2 starts verification (while User 1 is active)
3. Both submit different emails
4. Both submit their codes
5. Both should get roles

**Success:** Both users verify independently without interference

---

## 4. Quick Health Check Commands

### Check Active Sessions
```bash
aws dynamodb scan --table-name discord-verification-sessions --select COUNT --region us-east-1
```
Expected: 0-2 (only during active verifications)

### Check Verification Records
```bash
aws dynamodb scan --table-name discord-verification-records --select COUNT --region us-east-1
```
Expected: Increases with each successful verification

### Check Guild Config
```bash
aws dynamodb get-item \
  --table-name discord-guild-configs \
  --key '{"guild_id": {"S": "YOUR_GUILD_ID"}}' \
  --region us-east-1
```
Expected: Shows your setup configuration

### Check SES Sending
```bash
aws ses get-send-statistics --region us-east-1
```
Look for recent sends, 0 bounces, 0 complaints

---

## 5. Common Issues & Quick Fixes

### Email Not Received

**Problem:** Submitted email but nothing in inbox
**Solution:**
1. Check spam folder
2. Verify email in SES:
   ```bash
   aws ses verify-email-identity --email-identity your@email.edu --region us-east-1
   ```
3. Check CloudWatch logs for SES errors

---

### Role Not Assigned

**Problem:** Verification succeeded but no role
**Solution:**
1. Check role hierarchy: Bot role must be ABOVE "Verified Student"
2. Server Settings > Roles > Drag bot role up
3. Verify bot has "Manage Roles" permission

---

### "Application did not respond"

**Problem:** Discord shows error after clicking button
**Solution:**
1. Check CloudWatch logs for errors
2. Verify Lambda timeout is 30 seconds
3. Check DynamoDB tables are accessible

---

### Rate Limit Not Working

**Problem:** Can spam verification button
**Solution:**
1. Check CloudWatch logs for rate limit checks
2. Verify sessions table is writable
3. May need to redeploy Lambda code

---

## 6. Testing Checklist

**Before Starting:**
- [ ] Test emails verified in SES
- [ ] CloudWatch logs tail running
- [ ] Discord test server ready
- [ ] Bot invited with correct permissions
- [ ] Bot role above "Verified Student" role

**Essential Tests:**
- [ ] Admin setup completes
- [ ] Happy path verification works
- [ ] Invalid domain rejected
- [ ] Wrong code attempts tracked
- [ ] Rate limiting works
- [ ] Multi-user testing works

**Success Criteria:**
- [ ] At least 3 successful verifications
- [ ] No Lambda errors in CloudWatch
- [ ] Emails delivered < 30 seconds
- [ ] Roles assigned correctly
- [ ] No PII in logs

---

## 7. After Testing

### Clean Up Test Data (Optional)
```bash
# Clear test sessions
aws dynamodb delete-item \
  --table-name discord-verification-sessions \
  --key '{"user_id": {"S": "TEST_USER_ID"}, "guild_id": {"S": "TEST_GUILD_ID"}}' \
  --region us-east-1
```

### Document Results
Create a simple test report:
```markdown
# Test Results - [Date]

## Tests Passed: X/6
- [x] Admin setup
- [x] Happy path verification
- [x] Invalid email rejection
- [ ] Failed test name (reason)

## Issues Found:
1. Issue description
2. Steps to reproduce

## Performance:
- Email delivery: X seconds
- Button response: X seconds
```

---

## 8. Next Steps

**If All Tests Pass:**
1. Review full testing plan: `DISCORD_SERVER_TESTING_PLAN.md`
2. Consider additional scenarios (cross-platform, edge cases)
3. Set up CloudWatch alarms for production
4. Consider moving SES out of sandbox mode

**If Tests Fail:**
1. Document failure with screenshots
2. Check CloudWatch logs for errors
3. Review troubleshooting guide in full testing plan
4. Create GitHub issue with reproduction steps

---

## Emergency Contacts & Resources

**AWS Console Links:**
- Lambda: `https://console.aws.amazon.com/lambda`
- DynamoDB: `https://console.aws.amazon.com/dynamodb`
- SES: `https://console.aws.amazon.com/ses`
- CloudWatch: `https://console.aws.amazon.com/cloudwatch`

**Discord Developer Portal:**
- `https://discord.com/developers/applications`

**Documentation:**
- Full Testing Plan: `DISCORD_SERVER_TESTING_PLAN.md`
- Deployment Checklist: `DEPLOYMENT_CHECKLIST.md`
- Security Docs: `SECURITY.md`

---

## Quick Command Reference

```bash
# Watch logs
aws logs tail /aws/lambda/discord-verification-handler --follow --region us-east-1

# Check SES quota
aws ses get-send-quota --region us-east-1

# Verify email in SES
aws ses verify-email-identity --email-identity test@domain.edu --region us-east-1

# Count verification records
aws dynamodb scan --table-name discord-verification-records --select COUNT --region us-east-1

# Get guild config
aws dynamodb get-item --table-name discord-guild-configs --key '{"guild_id": {"S": "GUILD_ID"}}' --region us-east-1
```

---

**Estimated Time:** 30-45 minutes for essential tests

Good luck! 🎉
