# Discord Server Testing Plan
## Post-Deployment Validation Guide

**Date Created:** 2025-12-08
**Purpose:** Comprehensive testing plan for Discord test server after merging PRs #16 (Phase 4 E2E & Deployment Tests) and #17 (SES Compliance Implementation)

---

## Table of Contents

1. [Overview](#overview)
2. [Pre-Testing Preparation](#pre-testing-preparation)
3. [SES Sandbox Constraints](#ses-sandbox-constraints)
4. [Test Scenarios](#test-scenarios)
5. [Monitoring & Logging](#monitoring--logging)
6. [Success Criteria](#success-criteria)
7. [Troubleshooting Guide](#troubleshooting-guide)

---

## Overview

### Current State
- All PRs merged to main branch
- Lambda function deployed to AWS
- DynamoDB tables configured (sessions, records, guild_configs)
- SES in sandbox mode with verified sender email
- CodeQL security fixes implemented
- Comprehensive test suite passing (96 Phase 4 tests + all previous tests)

### Testing Objectives
This testing plan validates functionality that automated tests cannot fully cover:
- Real Discord UI/UX flows
- Actual SES email delivery
- Production AWS service integration
- Multi-user concurrent operations
- Real-world timing and latency
- Discord permission handling
- Cross-device compatibility

---

## Pre-Testing Preparation

### 1. AWS Environment Verification

**DynamoDB Tables Checklist:**
```bash
# Verify all tables exist
aws dynamodb list-tables --region us-east-1 | grep discord

# Expected tables:
# - discord-verification-sessions
# - discord-verification-records
# - discord-guild-configs

# Check TTL on sessions table
aws dynamodb describe-time-to-live \
  --table-name discord-verification-sessions \
  --region us-east-1

# Expected: TTL enabled on 'ttl' attribute
```

**Lambda Function Checklist:**
```bash
# Check Lambda exists and is deployed
aws lambda get-function \
  --function-name discord-verification-handler \
  --region us-east-1

# Verify environment variables
aws lambda get-function-configuration \
  --function-name discord-verification-handler \
  --region us-east-1 | jq '.Environment.Variables'

# Expected variables:
# - DISCORD_PUBLIC_KEY
# - DISCORD_APP_ID (optional)
# - DYNAMODB_SESSIONS_TABLE
# - DYNAMODB_RECORDS_TABLE
# - DYNAMODB_GUILD_CONFIGS_TABLE
# - FROM_EMAIL
```

**SES Sandbox Setup:**
```bash
# Verify sender email
aws ses get-identity-verification-attributes \
  --identities noreply@yourdomain.com \
  --region us-east-1

# Check sandbox status
aws sesv2 get-account \
  --region us-east-1 | jq '.ProductionAccessEnabled'

# Add verified test recipient emails (REQUIRED in sandbox)
aws ses verify-email-identity \
  --email-identity your-test-email@domain.com \
  --region us-east-1
```

### 2. Test User Setup

**Verified Email Addresses Needed:**

Since SES is in sandbox mode, you MUST pre-verify all test email addresses:

1. **Primary tester email** (your personal .edu email)
   ```bash
   aws ses verify-email-identity \
     --email-identity your.name@university.edu \
     --region us-east-1
   ```

2. **Secondary tester email** (for multi-user tests)
   ```bash
   aws ses verify-email-identity \
     --email-identity colleague@university.edu \
     --region us-east-1
   ```

3. **Check verification inbox:**
   - AWS will send verification emails to each address
   - Click verification link within 24 hours
   - Confirm "Success" status in AWS Console

**Discord Test Accounts:**
- Admin account (has Administrator permission in test server)
- Regular user account #1 (for primary testing)
- Regular user account #2 (for concurrent testing)
- Mobile device account (for cross-platform testing)

### 3. Test Server Configuration

**Create Test Discord Server:**
- Server name: "Email Verification Bot Testing"
- Create test roles:
  - "Verified Student" (will be assigned by bot)
  - "Test Admin" (for testing admin checks)
- Create channels:
  - #verification (public channel for verification message)
  - #verified-only (restricted to "Verified Student" role)
  - #admin-only (for admin testing)

**Bot Invitation:**
```
Required bot permissions:
- Manage Roles (CRITICAL - bot role must be ABOVE "Verified Student" role)
- View Channels
- Send Messages
- Use Slash Commands

Invite URL format:
https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&permissions=268435456&scope=bot%20applications.commands
```

### 4. Clean State Verification

**Clear Previous Test Data:**
```bash
# Check for existing sessions
aws dynamodb scan \
  --table-name discord-verification-sessions \
  --region us-east-1

# Check existing records
aws dynamodb scan \
  --table-name discord-verification-records \
  --region us-east-1

# Check guild configs
aws dynamodb scan \
  --table-name discord-guild-configs \
  --region us-east-1

# Optional: Delete specific test data if restarting
aws dynamodb delete-item \
  --table-name discord-verification-sessions \
  --key '{"user_id": {"S": "USER_ID"}, "guild_id": {"S": "GUILD_ID"}}' \
  --region us-east-1
```

---

## SES Sandbox Constraints

### Understanding Sandbox Mode

**What Sandbox Mode Means:**
- Can ONLY send emails to verified email addresses
- Maximum 200 emails per 24-hour period
- Maximum 1 email per second sending rate
- Emails to unverified addresses will be REJECTED

**Implications for Testing:**

1. **CRITICAL:** Every test user email MUST be pre-verified in SES
2. Cannot test with random university emails
3. Cannot invite external users to test without verifying their emails first
4. Bounce/complaint tracking limited in sandbox

**Working with Sandbox Limitations:**

```bash
# Add each tester's email before they test
aws ses verify-email-identity \
  --email-identity tester@auburn.edu \
  --region us-east-1

# Monitor sending quota
aws ses get-send-quota --region us-east-1

# Expected output:
# {
#   "Max24HourSend": 200.0,
#   "MaxSendRate": 1.0,
#   "SentLast24Hours": X.0
# }

# Check for bounces/complaints (should be 0 in sandbox testing)
aws ses get-send-statistics --region us-east-1
```

**Error Handling to Expect:**

When testing with unverified email:
```
User sees: "Failed to send verification email. This might be because our email
service is in sandbox mode and can't send to unverified addresses."

CloudWatch logs: "Email address is not verified. The following identities failed
the check in region US-EAST-1"
```

### Sandbox Exit Strategy (Future)

To move to production and send to any email:
1. Go to AWS Console > SES > Account Dashboard
2. Click "Request production access"
3. Fill out use case form (typical approval: 24-48 hours)
4. After approval, remove verification requirement

---

## Test Scenarios

### Scenario 1: Admin Setup Flow (PRIORITY 1)

**Objective:** Validate the /setup command for guild configuration

**Prerequisites:**
- Logged in as admin user
- Bot has been invited to server
- Bot's role is above "Verified Student" in role hierarchy

**Test Steps:**

1. **Initial Setup**
   ```
   Command: /setup-email-verification
   Expected: Bot responds with role and channel selection menus
   ```

2. **Role Selection**
   - Select "Verified Student" from role dropdown
   - Expected: Selection acknowledged

3. **Channel Selection**
   - Select "#verification" from channel dropdown
   - Expected: Prompt for email domains

4. **Domain Configuration**
   - Enter domains: `auburn.edu,student.sans.edu,test.edu`
   - Expected: Domain validation passes
   - Invalid test: `gmail.com` should be rejected

5. **Custom Message (Optional)**
   - Test with emoji: "Welcome to AU! Click below to verify your student email"
   - Test message link: Copy a Discord message URL and paste
   - Expected: Message preview shown

6. **Configuration Review**
   - Review all settings in preview
   - Click "Approve Setup"
   - Expected: Configuration saved to DynamoDB

7. **Verification Message Posted**
   - Check #verification channel
   - Expected: Bot posts message with "Start Verification" button
   - Button should be interactive and blue (PRIMARY style)

**Success Criteria:**
- [ ] Setup completes without errors
- [ ] Guild config saved to DynamoDB (verify via AWS Console)
- [ ] Verification message appears in correct channel
- [ ] Button is clickable and styled correctly
- [ ] Custom message/emojis render properly

**Monitoring:**
```bash
# Check guild config was saved
aws dynamodb get-item \
  --table-name discord-guild-configs \
  --key '{"guild_id": {"S": "YOUR_GUILD_ID"}}' \
  --region us-east-1

# Expected fields:
# - role_id
# - channel_id
# - allowed_domains (list)
# - custom_message
# - setup_by_user_id
# - created_at
```

---

### Scenario 2: Happy Path Verification (PRIORITY 1)

**Objective:** Complete end-to-end verification as a new user

**Prerequisites:**
- User does NOT have "Verified Student" role
- User's .edu email is verified in SES (CRITICAL for sandbox)
- Guild is configured (Scenario 1 completed)

**Test Steps:**

1. **Start Verification**
   - Click "Start Verification" button in #verification channel
   - Expected: Email input modal appears
   - Title: "Email Verification"

2. **Submit Valid Email**
   - Enter: `your.name@auburn.edu` (or your verified .edu email)
   - Click Submit
   - Expected:
     - "I've sent a verification code to your.name@auburn.edu"
     - "Submit Code" button appears
     - Session created in DynamoDB

3. **Check Email Delivery**
   - Check email inbox (should arrive within 10-30 seconds)
   - Verify sender: `noreply@yourdomain.com`
   - Verify subject contains "verification code"
   - Verify 6-digit code is present
   - Expected timing: < 30 seconds

4. **Submit Verification Code**
   - Click "Submit Code" button
   - Enter the 6-digit code from email
   - Click Submit
   - Expected:
     - "Verification complete! You now have access to the server."
     - "Verified Student" role assigned
     - Can now access #verified-only channel

5. **Verify Role Assignment**
   - Check user's roles in server member list
   - Expected: "Verified Student" role visible
   - Try accessing #verified-only channel
   - Expected: Can view and send messages

6. **Verify Database State**
   - Session should be deleted from sessions table
   - Verification record should exist in records table

**Success Criteria:**
- [ ] Modal appears without errors
- [ ] Email sent and received within 30 seconds
- [ ] Email contains valid 6-digit code
- [ ] Code verification succeeds on first try
- [ ] Role assigned automatically
- [ ] User can access restricted channels
- [ ] Session cleaned up (deleted)
- [ ] Permanent record created

**Monitoring:**
```bash
# Check session was created (during step 2)
aws dynamodb get-item \
  --table-name discord-verification-sessions \
  --key '{"user_id": {"S": "USER_ID"}, "guild_id": {"S": "GUILD_ID"}}' \
  --region us-east-1

# Check session was deleted (after step 4)
# Should return no item

# Check verification record exists
aws dynamodb scan \
  --table-name discord-verification-records \
  --filter-expression "user_id = :uid AND guild_id = :gid" \
  --expression-attribute-values '{":uid":{"S":"USER_ID"}, ":gid":{"S":"GUILD_ID"}}' \
  --region us-east-1

# Check CloudWatch logs
aws logs tail /aws/lambda/discord-verification-handler --follow
```

---

### Scenario 3: Invalid Email Domain (PRIORITY 1)

**Objective:** Verify rejection of non-allowed email domains

**Prerequisites:**
- User in test server
- Guild configured with specific domains (auburn.edu, test.edu)

**Test Steps:**

1. Click "Start Verification"
2. Enter: `test.user@gmail.com`
3. Submit

**Expected Behavior:**
- Error message appears
- Message shows allowed domains list
- No email sent
- No session created in DynamoDB
- User prompted to try again

**Success Criteria:**
- [ ] Invalid domain rejected
- [ ] Clear error message with allowed domains
- [ ] No session created
- [ ] No email sent (check SES metrics)
- [ ] User can retry immediately

**Alternative Test Cases:**
- `user@yahoo.com` - should fail
- `user@student.edu` - should fail (not in allowed list)
- `user@AUBURN.EDU` - should pass (case-insensitive)
- `user+tag@auburn.edu` - should pass (email tag support)
- `invalid-email` - should fail (invalid format)

---

### Scenario 4: Incorrect Verification Code (PRIORITY 2)

**Objective:** Test attempt tracking and lockout after max failures

**Prerequisites:**
- User has active verification session
- Email with code received

**Test Steps:**

1. **First Wrong Attempt**
   - Click "Submit Code"
   - Enter: `000000` (incorrect)
   - Expected: "Incorrect code. You have 2 attempt(s) remaining."
   - Session attempts incremented to 1

2. **Second Wrong Attempt**
   - Click "Submit Code" again
   - Enter: `111111` (incorrect)
   - Expected: "Incorrect code. You have 1 attempt(s) remaining."
   - Session attempts incremented to 2

3. **Third Wrong Attempt (Final)**
   - Click "Submit Code" again
   - Enter: `222222` (incorrect)
   - Expected: "Incorrect code. Too many failed attempts. Please click 'Start Verification' to start over."
   - Session deleted
   - Must restart verification process

4. **Restart and Succeed**
   - Wait 60 seconds (rate limit)
   - Click "Start Verification"
   - Submit email
   - Get new code
   - Submit correct code
   - Verify success

**Success Criteria:**
- [ ] First 2 attempts show remaining count
- [ ] Third attempt triggers lockout
- [ ] Session deleted after 3 failures
- [ ] User can restart after cooldown
- [ ] New verification works correctly

**Configuration:**
```python
# From verification_logic.py
MAX_VERIFICATION_ATTEMPTS = 3  # This is the threshold
```

---

### Scenario 5: Rate Limiting (PRIORITY 2)

**Objective:** Validate 60-second cooldown between verification attempts

**Prerequisites:**
- User in test server
- No active session

**Test Steps:**

1. **First Verification Attempt**
   - Click "Start Verification"
   - Submit email: `user@auburn.edu`
   - Note timestamp (e.g., 10:00:00)

2. **Immediate Second Attempt**
   - Click "Start Verification" again immediately
   - Expected: "Please wait X seconds before starting a new verification."
   - X should be close to 60

3. **Wait and Retry**
   - Wait exactly 60 seconds
   - Click "Start Verification"
   - Expected: New email modal appears (rate limit expired)

**Success Criteria:**
- [ ] First attempt succeeds
- [ ] Second immediate attempt blocked
- [ ] Error message shows seconds remaining
- [ ] After 60 seconds, can verify again
- [ ] Rate limit is per-user per-guild

**Advanced Rate Limit Test:**
```
Test in Multiple Guilds:
1. Verify in Guild A at 10:00:00
2. Verify in Guild B at 10:00:30
   - Expected: ALLOWED (different guild_id)
3. Verify in Guild A again at 10:00:40
   - Expected: BLOCKED (still within 60s for Guild A)
```

---

### Scenario 6: Code Expiration (PRIORITY 2)

**Objective:** Verify codes expire after 15 minutes

**Prerequisites:**
- Active verification session

**Test Steps:**

1. **Start Verification**
   - Click "Start Verification"
   - Submit email
   - Receive code

2. **Wait 16 Minutes**
   - Do NOT submit code yet
   - Wait 16 minutes (can speed up in test by temporarily changing system clock if needed)

3. **Submit Expired Code**
   - Click "Submit Code"
   - Enter correct code (from email)
   - Expected: "Verification code has expired (15 minutes). Please click 'Start Verification' again."
   - Session deleted

4. **Restart Fresh**
   - Click "Start Verification"
   - New code should work

**Success Criteria:**
- [ ] Code expires after 15 minutes
- [ ] Clear expiration message
- [ ] Old session deleted
- [ ] Can get new code successfully

**Note:** For quick testing, you can manually modify the `expires_at` field in DynamoDB:
```bash
# Get current session
aws dynamodb get-item \
  --table-name discord-verification-sessions \
  --key '{"user_id": {"S": "USER_ID"}, "guild_id": {"S": "GUILD_ID"}}'

# Update expires_at to past time
aws dynamodb update-item \
  --table-name discord-verification-sessions \
  --key '{"user_id": {"S": "USER_ID"}, "guild_id": {"S": "GUILD_ID"}}' \
  --update-expression "SET expires_at = :exp" \
  --expression-attribute-values '{":exp": {"S": "2025-01-01T00:00:00"}}'

# Now submit code - should see expiration error
```

---

### Scenario 7: Already Verified User (PRIORITY 2)

**Objective:** Prevent re-verification of already verified users

**Prerequisites:**
- User has "Verified Student" role
- OR user has verification record in database

**Test Steps:**

1. **Test Role-Based Check**
   - User with "Verified Student" role clicks "Start Verification"
   - Expected: "You already have the verified role! No need to verify again."

2. **Test Database Check**
   - Remove role manually from user
   - User still has database record
   - Click "Start Verification"
   - Expected: "You are already verified in this server!"

**Success Criteria:**
- [ ] Role check prevents verification
- [ ] Database check prevents verification
- [ ] Appropriate message shown for each case
- [ ] No email sent
- [ ] No session created

---

### Scenario 8: Multi-User Concurrent Testing (PRIORITY 3)

**Objective:** Verify multiple users can verify simultaneously

**Prerequisites:**
- 2+ test users
- 2+ verified emails in SES
- All users lack "Verified Student" role

**Test Steps:**

1. **User 1 Starts**
   - User 1 clicks "Start Verification"
   - Submits email: `user1@auburn.edu`

2. **User 2 Starts (Concurrent)**
   - User 2 clicks "Start Verification" while User 1 is active
   - Submits email: `user2@auburn.edu`

3. **Both Submit Codes**
   - User 1 submits correct code
   - User 2 submits correct code
   - Both should succeed

4. **Verify Independence**
   - Check sessions table: should have 2 separate sessions (temporarily)
   - Check records table: should have 2 separate records
   - Verify different codes generated
   - Both users get roles

**Success Criteria:**
- [ ] Both users can start verification concurrently
- [ ] Sessions don't interfere with each other
- [ ] Separate codes generated
- [ ] Both emails delivered
- [ ] Both verifications succeed
- [ ] Both records saved

**Database Validation:**
```bash
# Check for concurrent sessions
aws dynamodb scan \
  --table-name discord-verification-sessions \
  --filter-expression "guild_id = :gid" \
  --expression-attribute-values '{":gid": {"S": "GUILD_ID"}}'

# Should show multiple active sessions
```

---

### Scenario 9: Cross-Guild Verification (PRIORITY 3)

**Objective:** Validate guild-specific verification isolation

**Prerequisites:**
- 2 test Discord servers (Guild A, Guild B)
- Bot invited to both
- Both configured with /setup
- Same user account

**Test Steps:**

1. **Verify in Guild A**
   - Join Guild A
   - Complete verification in Guild A
   - Receive "Verified Student" role in Guild A

2. **Switch to Guild B**
   - Join Guild B
   - User should NOT have "Verified Student" role in Guild B
   - Click "Start Verification" in Guild B
   - Expected: Can verify again (different guild)

3. **Complete Guild B Verification**
   - Submit email
   - Submit code
   - Receive role in Guild B

4. **Verify Database**
   - Check records table
   - Should have 2 records: one for Guild A, one for Guild B

**Success Criteria:**
- [ ] Verification is guild-specific
- [ ] User can verify in multiple guilds
- [ ] Separate records created
- [ ] Roles only apply to respective guilds

---

### Scenario 10: Mobile/Desktop Cross-Platform (PRIORITY 3)

**Objective:** Test bot interactions on different platforms

**Test Platforms:**
- Discord Desktop App (Windows/Mac/Linux)
- Discord Web Browser
- Discord Mobile App (iOS/Android)
- Discord PWA (Progressive Web App)

**Test Steps for Each Platform:**

1. Click "Start Verification" button
2. Verify modal appears correctly
3. Submit email via on-screen keyboard
4. Click "Submit Code" button
5. Enter code via modal
6. Verify success message

**Platform-Specific Checks:**

**Mobile:**
- [ ] Buttons are tap-friendly (not too small)
- [ ] Modal keyboard auto-appears
- [ ] Email keyboard layout shows @ and .edu shortcuts
- [ ] Code input shows numeric keyboard
- [ ] Long messages don't break layout
- [ ] Ephemeral messages visible

**Desktop:**
- [ ] Modals centered properly
- [ ] Tab navigation works
- [ ] Enter key submits forms
- [ ] Copy/paste works for codes

**Web Browser:**
- [ ] No CORS issues
- [ ] Webhooks fire correctly
- [ ] All interactions responsive

**Success Criteria:**
- [ ] Consistent behavior across all platforms
- [ ] No UI breaking or layout issues
- [ ] All modals functional
- [ ] Buttons clickable on all devices

---

### Scenario 11: Permission Edge Cases (PRIORITY 3)

**Objective:** Test permission-related failures

**Test Cases:**

1. **Bot Role Below Verified Role**
   - Move bot's role below "Verified Student" in hierarchy
   - Complete verification
   - Expected: Verification succeeds but role assignment fails
   - Message: "Verification successful, but I encountered an issue assigning your role."

2. **Bot Missing Manage Roles Permission**
   - Remove "Manage Roles" permission from bot
   - Complete verification
   - Expected: Same as above

3. **Non-Admin Tries /setup**
   - Regular user runs `/setup-email-verification`
   - Expected: "You need Administrator permissions to run this command."

4. **User Tries Setup in DM**
   - User DMs bot with `/setup-email-verification`
   - Expected: Command fails or not shown

**Success Criteria:**
- [ ] Permission errors handled gracefully
- [ ] Clear error messages
- [ ] Logs show authorization failures
- [ ] Security audit logs capture attempts

---

### Scenario 12: SES Sandbox Email Failures (PRIORITY 2)

**Objective:** Test error handling when email fails to send

**Test Cases:**

1. **Unverified Email Address (Sandbox)**
   - Try verification with `random@unverified.edu`
   - Expected: "Failed to send verification email. This might be because our email service is in sandbox mode..."
   - Session deleted

2. **SES Quota Exhausted**
   - Send 200 emails in 24 hours (SES sandbox limit)
   - Try 201st verification
   - Expected: Email send fails, appropriate error shown

3. **Invalid From Address**
   - Temporarily change FROM_EMAIL to unverified address
   - Try verification
   - Expected: Email fails, error logged

**Success Criteria:**
- [ ] SES errors caught and handled
- [ ] User-friendly error messages
- [ ] Sessions cleaned up on email failure
- [ ] CloudWatch logs show SES errors

**CloudWatch Error Patterns to Watch:**
```
"MessageRejected: Email address is not verified"
"Throttling: Maximum sending rate exceeded"
"InvalidParameterValue: Missing final '@domain'"
```

---

### Scenario 13: DynamoDB Edge Cases (PRIORITY 3)

**Objective:** Test database failure handling

**Test Cases:**

1. **Session Already Exists**
   - Start verification (creates session)
   - Wait 60 seconds
   - Start verification again
   - Expected: Old session overwritten, new code sent

2. **Malformed Session Data**
   - Manually corrupt session in DynamoDB
   - Try to submit code
   - Expected: Error handled gracefully

3. **Missing Guild Config**
   - Delete guild config from DynamoDB
   - Try to start verification
   - Expected: "This server hasn't been configured yet."

**Manual DynamoDB Operations:**
```bash
# Create malformed session for testing
aws dynamodb put-item \
  --table-name discord-verification-sessions \
  --item '{
    "user_id": {"S": "TEST_USER"},
    "guild_id": {"S": "TEST_GUILD"},
    "code": {"S": "INVALID"}
  }'

# Delete guild config
aws dynamodb delete-item \
  --table-name discord-guild-configs \
  --key '{"guild_id": {"S": "GUILD_ID"}}'
```

**Success Criteria:**
- [ ] Database errors don't crash Lambda
- [ ] Appropriate fallback behavior
- [ ] Error messages user-friendly
- [ ] Errors logged to CloudWatch

---

### Scenario 14: Logging and Monitoring (PRIORITY 1)

**Objective:** Verify security logging and PII redaction

**Test Steps:**

1. **Trigger Various Actions**
   - Setup command
   - Start verification
   - Submit email
   - Submit code (correct and incorrect)
   - Rate limit error

2. **Check CloudWatch Logs**
   ```bash
   aws logs tail /aws/lambda/discord-verification-handler \
     --follow \
     --format short \
     --region us-east-1
   ```

3. **Verify Log Contents**

**What SHOULD Be Logged:**
- User IDs (Discord IDs are not PII)
- Guild IDs
- Timestamps
- Action types (button_click, modal_submit, command)
- Success/failure status
- Error messages
- Rate limit triggers
- Authorization checks

**What SHOULD NOT Be Logged:**
- Full email addresses (should be redacted: `u***@auburn.edu`)
- Verification codes
- Discord tokens
- AWS credentials

**Success Criteria:**
- [ ] All major actions logged
- [ ] Emails redacted in logs
- [ ] No sensitive data exposed
- [ ] Log timestamps accurate
- [ ] Error stack traces helpful
- [ ] Structured logging format

**Sample Expected Log Entry:**
```
[INFO] 2025-12-08T15:30:45.123Z - Email verification started
  user_id: 123456789012345678
  guild_id: 987654321098765432
  email: u***@auburn.edu
  action: start_verification

[INFO] 2025-12-08T15:30:46.789Z - Verification code sent
  verification_id: ver_abc123xyz
  email_redacted: u***@auburn.edu

[ERROR] 2025-12-08T15:31:20.456Z - Incorrect verification code
  user_id: 123456789012345678
  attempts: 1
  remaining: 2
```

---

### Scenario 15: Performance and Latency (PRIORITY 2)

**Objective:** Measure real-world response times

**Test Steps:**

1. **Measure Button Click Latency**
   - Click "Start Verification"
   - Time from click to modal appearing
   - Expected: < 3 seconds (Discord's interaction timeout)
   - Optimal: < 1 second

2. **Measure Email Delivery Time**
   - Submit email
   - Time from submission to email arrival
   - Expected: < 30 seconds
   - Optimal: < 10 seconds

3. **Measure Code Submission**
   - Submit code
   - Time from submission to role assignment
   - Expected: < 3 seconds
   - Optimal: < 1 second

4. **Cold Start Test**
   - Wait 15 minutes (Lambda cold start)
   - Trigger any interaction
   - Measure response time
   - Expected: < 5 seconds

**Success Criteria:**
- [ ] All interactions < 3 seconds
- [ ] No Discord timeout errors
- [ ] Email delivery < 30 seconds
- [ ] Cold start < 5 seconds
- [ ] Subsequent calls < 1 second

**Performance Monitoring:**
```bash
# Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=discord-verification-handler \
  --start-time 2025-12-08T00:00:00Z \
  --end-time 2025-12-08T23:59:59Z \
  --period 3600 \
  --statistics Average,Maximum \
  --region us-east-1

# Expected:
# Average: < 500ms
# Maximum: < 3000ms
```

---

## Monitoring & Logging

### Real-Time Monitoring During Tests

**CloudWatch Logs Live Tail:**
```bash
# Start watching logs before testing
aws logs tail /aws/lambda/discord-verification-handler \
  --follow \
  --format short \
  --filter-pattern "ERROR" \
  --region us-east-1

# In separate terminal, watch all logs
aws logs tail /aws/lambda/discord-verification-handler \
  --follow \
  --region us-east-1
```

**Key Log Patterns to Watch:**

1. **Successful Verification:**
   ```
   START RequestId: ...
   [INFO] Interaction received: type=3 (MESSAGE_COMPONENT)
   [INFO] Email verification started: user_id=X, guild_id=Y
   [INFO] Verification code sent: email_redacted=u***@domain.edu
   [INFO] Code verification successful
   [INFO] Role assigned successfully
   END RequestId: ...
   ```

2. **Error Patterns:**
   ```
   [ERROR] Failed to send email: MessageRejected
   [ERROR] DynamoDB error: ResourceNotFoundException
   [ERROR] Discord API error: Missing Permissions
   [ERROR] Invalid signature
   ```

3. **Security Events:**
   ```
   [WARN] Rate limit triggered: user_id=X, seconds_remaining=45
   [WARN] Max attempts exceeded: user_id=X
   [INFO] Authorization check: user=admin(123), permissions=8, admin=True
   ```

### CloudWatch Metrics Dashboard

**Create Custom Dashboard:**
```bash
aws cloudwatch put-dashboard \
  --dashboard-name DiscordBotMetrics \
  --dashboard-body file://dashboard.json
```

**dashboard.json:**
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum"}],
          [".", "Errors", {"stat": "Sum"}],
          [".", "Duration", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Lambda Function Metrics"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/DynamoDB", "ConsumedReadCapacityUnits", {"stat": "Sum"}],
          [".", "ConsumedWriteCapacityUnits", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "DynamoDB Usage"
      }
    }
  ]
}
```

### SES Monitoring

**Check Email Statistics:**
```bash
# Get send statistics
aws ses get-send-statistics --region us-east-1

# Check quota usage
aws ses get-send-quota --region us-east-1

# Check identity verification
aws ses get-identity-verification-attributes \
  --identities noreply@yourdomain.com \
  --region us-east-1
```

**Expected During Testing:**
- Sends: 5-20 (depending on test scenarios)
- Bounces: 0
- Complaints: 0
- Rejects: May see rejects if testing unverified emails in sandbox

### DynamoDB Monitoring

**Check Table Metrics:**
```bash
# Sessions table (should be mostly empty - sessions cleaned up)
aws dynamodb describe-table \
  --table-name discord-verification-sessions \
  --region us-east-1

# Records table (should grow with each verification)
aws dynamodb describe-table \
  --table-name discord-verification-records \
  --region us-east-1

# Guild configs (should have 1+ entries)
aws dynamodb describe-table \
  --table-name discord-guild-configs \
  --region us-east-1
```

**Scan for Active Sessions:**
```bash
aws dynamodb scan \
  --table-name discord-verification-sessions \
  --region us-east-1 \
  --select COUNT

# Expected: 0-2 (only during active verifications)
```

**Check Verification Records:**
```bash
aws dynamodb scan \
  --table-name discord-verification-records \
  --region us-east-1 \
  --select COUNT

# Expected: Increases with each successful verification
```

---

## Success Criteria

### Overall Testing Success

**Must Pass (Critical):**
- [ ] All Priority 1 scenarios pass
- [ ] Admin setup completes successfully
- [ ] At least 3 happy path verifications succeed
- [ ] Email delivery works consistently
- [ ] Role assignment works every time
- [ ] No Lambda errors in CloudWatch
- [ ] No exposed PII in logs
- [ ] Rate limiting works correctly
- [ ] Invalid emails rejected properly

**Should Pass (Important):**
- [ ] All Priority 2 scenarios pass
- [ ] Code expiration works
- [ ] Attempt limiting works
- [ ] Cross-platform testing passes
- [ ] Concurrent users work
- [ ] Performance within SLA

**Nice to Have (Optional):**
- [ ] All Priority 3 scenarios pass
- [ ] Cross-guild isolation verified
- [ ] All edge cases handled
- [ ] Mobile UX is smooth

### Performance Benchmarks

| Metric | Target | Acceptable | Poor |
|--------|--------|------------|------|
| Button response | < 1s | < 3s | > 3s |
| Email delivery | < 10s | < 30s | > 30s |
| Code verification | < 1s | < 3s | > 3s |
| Cold start | < 3s | < 5s | > 5s |
| Lambda duration | < 500ms | < 1s | > 1s |

### Reliability Metrics

**Success Rates:**
- Verification completion rate: > 95%
- Email delivery rate: > 99%
- Role assignment rate: 100% (given correct permissions)

**Error Handling:**
- All errors logged: 100%
- User-friendly error messages: 100%
- Graceful degradation: 100%

---

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue 1: "Application did not respond"

**Symptoms:**
- Discord shows error after clicking button
- 3-second timeout exceeded

**Diagnosis:**
```bash
# Check Lambda execution time
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "Duration" \
  --max-items 5

# Check for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "ERROR" \
  --max-items 10
```

**Solutions:**
1. Check Lambda timeout setting (should be 30s)
2. Verify no DynamoDB throttling
3. Check network connectivity (VPC config if applicable)
4. Look for slow Discord API calls

---

#### Issue 2: Email Not Received

**Symptoms:**
- User submits email
- No email arrives in inbox
- No SES error in logs

**Diagnosis:**
```bash
# Check SES send statistics
aws ses get-send-statistics --region us-east-1

# Check for bounces/rejects
aws sesv2 list-suppressed-destinations --region us-east-1

# Verify email identity
aws ses get-identity-verification-attributes \
  --identities test@auburn.edu \
  --region us-east-1
```

**Solutions:**
1. **Sandbox Mode:** Verify recipient email in SES
2. **Spam Folder:** Check spam/junk folder
3. **Wrong Region:** Verify SES region matches Lambda region
4. **Quota:** Check SES quota not exceeded
5. **From Address:** Verify FROM_EMAIL environment variable

**Sandbox Workaround:**
```bash
# Verify the test email
aws ses verify-email-identity \
  --email-identity test@auburn.edu \
  --region us-east-1

# Check verification email in inbox
# Click verification link
# Retry bot verification
```

---

#### Issue 3: Role Not Assigned

**Symptoms:**
- Verification succeeds
- No error message
- Role not assigned to user

**Diagnosis:**
```bash
# Check Lambda logs for role assignment
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "assign_role"

# Check bot token in SSM
aws ssm get-parameter \
  --name /discord-bot/token \
  --with-decryption \
  --region us-east-1
```

**Solutions:**
1. **Role Hierarchy:** Move bot's role ABOVE "Verified Student" role
2. **Permissions:** Verify bot has "Manage Roles" permission
3. **Token:** Verify bot token in SSM is correct
4. **API Error:** Check Discord API error in logs

**Fix Role Hierarchy:**
1. Go to Server Settings > Roles
2. Drag bot's role above "Verified Student"
3. Save changes
4. Retry verification

---

#### Issue 4: Rate Limit Not Working

**Symptoms:**
- User can spam "Start Verification"
- No rate limit message

**Diagnosis:**
```bash
# Check sessions table for rate limit tracking
aws dynamodb scan \
  --table-name discord-verification-sessions \
  --region us-east-1
```

**Possible Causes:**
1. `created_at` timestamp not set correctly
2. Rate limit check skipped due to code bug
3. Session not created on first attempt

**Solutions:**
1. Check `check_rate_limit()` function logs
2. Verify DynamoDB write succeeded
3. Check for Lambda timeout during session creation

---

#### Issue 5: Modal Not Appearing

**Symptoms:**
- Click button
- Nothing happens
- No modal shown

**Diagnosis:**
```bash
# Check interaction type
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "Interaction received"

# Check response type
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "InteractionResponseType"
```

**Solutions:**
1. **Response Type:** Verify returning type 9 (MODAL)
2. **Response Time:** Must respond within 3 seconds
3. **JSON Format:** Verify response JSON is valid
4. **Component Schema:** Check modal component structure

**Test Modal Response:**
```python
# Expected response structure
{
    'type': 9,  # MODAL
    'data': {
        'custom_id': 'email_submission_modal',
        'title': 'Email Verification',
        'components': [...]
    }
}
```

---

#### Issue 6: Database Connection Errors

**Symptoms:**
- "ResourceNotFoundException"
- "AccessDeniedException"

**Diagnosis:**
```bash
# Check IAM role permissions
aws iam get-role-policy \
  --role-name discord-verification-lambda-role \
  --policy-name DynamoDBAccess

# Verify tables exist
aws dynamodb list-tables --region us-east-1
```

**Solutions:**
1. **Table Names:** Verify environment variables match actual table names
2. **Permissions:** Verify IAM role has DynamoDB permissions
3. **Region:** Verify DynamoDB region matches Lambda region
4. **Table Status:** Verify tables are ACTIVE status

---

#### Issue 7: Signature Verification Failures

**Symptoms:**
- All interactions return 401
- "Invalid signature" in logs

**Diagnosis:**
```bash
# Check public key
aws lambda get-function-configuration \
  --function-name discord-verification-handler \
  --query 'Environment.Variables.DISCORD_PUBLIC_KEY'
```

**Solutions:**
1. Verify DISCORD_PUBLIC_KEY in environment variables
2. Copy fresh public key from Discord Developer Portal
3. Verify no extra whitespace in key
4. Verify key is 64 hex characters

**Update Public Key:**
```bash
aws lambda update-function-configuration \
  --function-name discord-verification-handler \
  --environment Variables={DISCORD_PUBLIC_KEY=CORRECT_KEY_HERE,...}
```

---

### Emergency Rollback

**If Testing Reveals Critical Bugs:**

1. **Disable Bot Immediately:**
   ```
   - Go to Discord Developer Portal
   - General Information > Interactions Endpoint URL
   - Clear the URL field
   - Save changes
   ```

2. **Revert Lambda Code:**
   ```bash
   # List versions
   aws lambda list-versions-by-function \
     --function-name discord-verification-handler

   # Rollback to previous version
   aws lambda update-alias \
     --function-name discord-verification-handler \
     --name production \
     --function-version $PREVIOUS_VERSION
   ```

3. **Notify Stakeholders:**
   - Post in test server
   - Document issue in GitHub
   - Create rollback plan

---

## Post-Testing Actions

### After Successful Testing

**1. Document Results:**
```markdown
# Test Results - 2025-12-08

## Summary
- Total scenarios tested: X
- Passed: Y
- Failed: Z
- Known issues: List

## Performance Metrics
- Average response time: Xms
- Email delivery: Ys
- Success rate: Z%

## Recommendations
- Move to SES production mode
- Increase Lambda memory if needed
- Set up CloudWatch alarms
```

**2. Production Readiness Checklist:**
- [ ] All Priority 1 tests passed
- [ ] No critical bugs found
- [ ] Performance acceptable
- [ ] Logging working correctly
- [ ] Monitoring set up
- [ ] Documentation updated

**3. Move SES to Production (Optional):**
```
If you want to remove email verification requirement:
1. Go to AWS Console > SES > Account Dashboard
2. Click "Request production access"
3. Fill out form with use case
4. Wait 24-48 hours for approval
5. After approval, can send to any email
```

**4. Set Up Alerts:**
```bash
# Create error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name discord-bot-error-rate \
  --alarm-description "Alert on high error rate" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1
```

**5. Schedule Regular Testing:**
- Weekly: Run happy path verification
- Monthly: Run full test suite
- After changes: Run relevant scenarios

---

## Appendix

### A. Test Data Templates

**Verified Test Emails (Sandbox):**
```
test1@auburn.edu (verified in SES)
test2@auburn.edu (verified in SES)
admin@auburn.edu (verified in SES)
```

**Test Guild IDs:**
```
Primary Test Guild: 123456789012345678
Secondary Test Guild: 987654321098765432
```

**Test User IDs:**
```
Admin User: 111111111111111111
Regular User 1: 222222222222222222
Regular User 2: 333333333333333333
```

### B. Quick Reference Commands

**AWS CLI Quick Reference:**
```bash
# Check logs
aws logs tail /aws/lambda/discord-verification-handler --follow

# Check SES quota
aws ses get-send-quota

# Scan sessions
aws dynamodb scan --table-name discord-verification-sessions

# Update Lambda env var
aws lambda update-function-configuration \
  --function-name discord-verification-handler \
  --environment Variables={KEY=VALUE}
```

**DynamoDB Quick Queries:**
```bash
# Get session
aws dynamodb get-item \
  --table-name discord-verification-sessions \
  --key '{"user_id": {"S": "USER_ID"}, "guild_id": {"S": "GUILD_ID"}}'

# Get guild config
aws dynamodb get-item \
  --table-name discord-guild-configs \
  --key '{"guild_id": {"S": "GUILD_ID"}}'

# Count records
aws dynamodb scan \
  --table-name discord-verification-records \
  --select COUNT
```

### C. Testing Checklist

**Before Each Test Session:**
- [ ] AWS credentials configured
- [ ] CloudWatch logs tail running
- [ ] SES quota checked
- [ ] DynamoDB tables accessible
- [ ] Discord test server ready
- [ ] Test emails verified in SES
- [ ] Test user accounts ready

**During Testing:**
- [ ] Document each scenario result
- [ ] Screenshot any errors
- [ ] Save CloudWatch logs
- [ ] Note performance timings
- [ ] Track any anomalies

**After Testing:**
- [ ] Clean up test data
- [ ] Document issues found
- [ ] Update test plan if needed
- [ ] Share results with team
- [ ] Plan fixes for failures

---

## Summary

This comprehensive testing plan covers:

1. **15 Test Scenarios** from Priority 1 (critical) to Priority 3 (optional)
2. **SES Sandbox Workarounds** with verified email requirements
3. **Monitoring & Logging** validation
4. **Performance Benchmarks** and latency testing
5. **Troubleshooting Guide** for common issues
6. **Success Criteria** for production readiness

**Estimated Testing Time:**
- Priority 1 scenarios: 2-3 hours
- Priority 2 scenarios: 1-2 hours
- Priority 3 scenarios: 1-2 hours
- Total comprehensive testing: 4-7 hours

**Key Reminders:**
- All test emails MUST be verified in SES (sandbox mode)
- Maximum 200 emails per 24 hours in sandbox
- Monitor CloudWatch logs during all tests
- Document all failures with screenshots and logs
- Test on multiple devices/platforms

**Next Steps:**
1. Verify all pre-testing preparation items
2. Start with Priority 1 scenarios
3. Document results in real-time
4. Address any critical issues before continuing
5. Complete full test suite
6. Prepare for production deployment

Good luck with your testing! 🚀
