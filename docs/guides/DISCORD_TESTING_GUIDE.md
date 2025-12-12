# Discord Server Testing Guide
## Complete Validation Guide for Discord Email Verification Bot

**Last Updated:** December 9, 2025  
**Version:** 1.0  
**Deployment Status:** Fresh deployment complete, ready for live testing

---

## Table of Contents

1. [Overview](#overview)
2. [Pre-Testing Setup](#pre-testing-setup)
3. [Test Environment Configuration](#test-environment-configuration)
4. [Core Functionality Tests](#core-functionality-tests)
5. [Priority Test Scenarios](#priority-test-scenarios)
6. [Monitoring and Logs](#monitoring-and-logs)
7. [Test Results Template](#test-results-template)
8. [Troubleshooting](#troubleshooting)
9. [Success Criteria](#success-criteria)

---

## Overview

### Purpose

This guide provides step-by-step instructions for validating the Discord Email Verification Bot in a live Discord server environment. It covers all functionality, edge cases, and production-readiness checks.

### Current Deployment State

**AWS Resources:**
- Lambda Function: `discord-verification-handler`
- Function URL: `https://dmnw3lxadg36anjkjmkfbjegbi0vemfx.lambda-url.us-east-1.on.aws/`
- Region: `us-east-1`
- DynamoDB Tables: 3 (sessions, records, guild_configs)
- SES Status: **Production mode** (can send to any email address)
- SES Domain: `thedailydecrypt.com` (verified)

**Test Server:**
- Guild ID: `704494754129510431`
- Previous Configuration Backed Up:
  - Channel ID: `768351579773468672`
  - Role ID: `849471214711996486`
  - Domain: `student.sans.edu`

**Test Suite Status:**
- 96/96 E2E and deployment tests passing
- All security fixes implemented
- CodeQL validation complete

### What This Guide Covers

This testing validates functionality that automated tests cannot:
- Real Discord UI/UX interactions
- Actual email delivery via SES
- Live AWS service integration
- Multi-user concurrent operations
- Cross-platform compatibility (desktop, web, mobile)
- Real-world timing and latency
- Discord permission handling

**Estimated Testing Time:**
- Essential tests (Priority 1): 45-60 minutes
- Comprehensive tests (All priorities): 2-3 hours

---

## Pre-Testing Setup

### Step 1: Update Discord Developer Portal

**CRITICAL:** Update the Interactions Endpoint URL before testing.

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application (ID: `1446567306170863686`)
3. Navigate to **General Information**
4. Find **Interactions Endpoint URL**
5. Update to: `https://dmnw3lxadg36anjkjmkfbjegbi0vemfx.lambda-url.us-east-1.on.aws/`
6. Click **Save Changes**
7. Discord will send a PING request to verify the endpoint
8. Wait for green checkmark (Discord successfully verified endpoint)

**Verification:**
```bash
# Watch CloudWatch logs for the PING request
aws logs tail /aws/lambda/discord-verification-handler --follow --region us-east-1
```

Expected log output:
```
[INFO] Interaction received: type=1 (PING)
[INFO] Responding with PONG
```

**If Discord Verification Fails:**
- Check Lambda function is active and reachable
- Verify DISCORD_PUBLIC_KEY environment variable is correct
- Check CloudWatch logs for signature verification errors
- Ensure Lambda has proper permissions

---

### Step 2: Verify AWS Resources

Run these commands to ensure all infrastructure is ready:

**DynamoDB Tables:**
```bash
# Verify all three tables exist and are active
aws dynamodb list-tables --region us-east-1 | grep discord

# Expected output:
# discord-guild-configs
# discord-verification-records
# discord-verification-sessions

# Check TTL is enabled on sessions table
aws dynamodb describe-time-to-live \
  --table-name discord-verification-sessions \
  --region us-east-1

# Expected: TimeToLiveStatus: "ENABLED"
```

**Lambda Function:**
```bash
# Verify Lambda function is active
aws lambda get-function \
  --function-name discord-verification-handler \
  --region us-east-1

# Check environment variables
aws lambda get-function-configuration \
  --function-name discord-verification-handler \
  --region us-east-1 | jq '.Environment.Variables'

# Expected variables:
# - DISCORD_PUBLIC_KEY: fb86b839e3d052f72cb07bddb399a98e43d16c94ab48c9444a9c200ddd518169
# - DYNAMODB_SESSIONS_TABLE: discord-verification-sessions
# - DYNAMODB_RECORDS_TABLE: discord-verification-records
# - DYNAMODB_GUILD_CONFIGS_TABLE: discord-guild-configs
# - FROM_EMAIL: verificationcode.noreply@thedailydecrypt.com
```

**SES Configuration:**
```bash
# Verify SES is in production mode
aws sesv2 get-account --region us-east-1 | jq '.ProductionAccessEnabled'

# Expected: true

# Check sending quota
aws ses get-send-quota --region us-east-1

# Expected:
# Max24HourSend: 50,000+ (production)
# MaxSendRate: 14+ (production)
```

---

### Step 3: Test Account Requirements

**Discord Accounts Needed:**

1. **Admin Account** (has Administrator permission)
   - For running `/setup-email-verification` command
   - For testing admin-only features
   - Must have "Administrator" permission in test server

2. **Test User Account #1** (regular user)
   - For primary verification testing
   - Should NOT have any special roles initially
   - Used for happy path scenarios

3. **Test User Account #2** (regular user)
   - For concurrent user testing
   - For testing multi-user scenarios
   - Should be separate from Account #1

4. **Mobile Device Account** (optional but recommended)
   - For cross-platform testing
   - Can be same as Test User #1 on different device

**Email Addresses Needed:**

Since SES is in **production mode**, you can use ANY email address:
- Your personal .edu email
- Test emails you control
- Temporary email services (for testing only)
- No need to pre-verify emails in SES

**Recommended Test Emails:**
- `your.name@student.sans.edu` (matches previous config)
- `test@yourdomain.edu` (any .edu domain)
- `invalid@gmail.com` (for testing domain rejection)

---

### Step 4: Test Server Configuration

**Server Setup:**

If you don't have a test server ready, create one:

1. **Create Discord Server:**
   - Name: "Email Verification Bot Testing"
   - Template: Community or Blank

2. **Create Roles:**
   - "Verified Student" (this will be assigned by the bot)
     - Color: Green (for visibility)
     - No special permissions needed
   - Ensure bot's role is ABOVE "Verified Student" in hierarchy

3. **Create Channels:**
   - `#verification` - Public channel where verification message will be posted
   - `#verified-only` - Restricted to "Verified Student" role only
   - `#admin-test` - For admin testing

4. **Invite Bot to Server:**

   Use this OAuth2 URL (replace YOUR_APP_ID):
   ```
   https://discord.com/oauth2/authorize?client_id=1446567306170863686&permissions=268435456&scope=bot%20applications.commands
   ```

   **Required Permissions:**
   - Manage Roles (CRITICAL)
   - View Channels
   - Send Messages
   - Use Slash Commands

5. **Configure Role Hierarchy:**
   - Go to Server Settings > Roles
   - Drag bot's role ABOVE "Verified Student"
   - This is CRITICAL for role assignment to work

**Using Existing Test Server (Guild ID: 704494754129510431):**

If using the backed-up configuration:
- Verify Channel `768351579773468672` still exists
- Verify Role `849471214711996486` still exists
- Bot should already be in server
- Check bot's role hierarchy is correct

---

### Step 5: Monitoring Setup

**Start CloudWatch Logs Monitoring:**

Before testing, open a terminal window to watch logs in real-time:

```bash
# Terminal 1: Watch all logs
aws logs tail /aws/lambda/discord-verification-handler \
  --follow \
  --region us-east-1

# Terminal 2 (optional): Watch only errors
aws logs tail /aws/lambda/discord-verification-handler \
  --follow \
  --filter-pattern "ERROR" \
  --region us-east-1
```

Keep these running during ALL tests for immediate feedback.

**Expected Log Patterns:**

**Successful interaction:**
```
START RequestId: abc123...
[INFO] Interaction received: type=3 (MESSAGE_COMPONENT)
[INFO] Button click: start_verification
END RequestId: abc123...
REPORT RequestId: abc123... Duration: 234.56 ms
```

**Error pattern:**
```
[ERROR] Failed to assign role: 403 Forbidden
[ERROR] Missing Permissions
```

---

## Test Environment Configuration

### Discord Application Settings Verification

Before testing, verify these settings in Discord Developer Portal:

**Bot Settings:**
1. Navigate to **Bot** tab
2. Verify bot token exists (don't need to copy it)
3. Check these intents are enabled:
   - **Server Members Intent** - REQUIRED
   - **Message Content Intent** - Optional (for message link feature)

**Application Settings:**
1. Navigate to **General Information**
2. Verify these values match:
   - Application ID: `1446567306170863686`
   - Public Key: `fb86b839e3d052f72cb07bddb399a98e43d16c94ab48c9444a9c200ddd518169`
   - Interactions Endpoint URL: `https://dmnw3lxadg36anjkjmkfbjegbi0vemfx.lambda-url.us-east-1.on.aws/`

**OAuth2 Settings:**
1. Navigate to **OAuth2** > **URL Generator**
2. Verify bot invite URL has:
   - Scopes: `bot`, `applications.commands`
   - Permissions: Manage Roles, View Channels, Send Messages

---

### Slash Commands Registration

Verify the `/setup-email-verification` command is registered:

**Check via Discord:**
- Type `/` in any channel
- Look for `setup-email-verification` in the command list
- Should show description: "Configure email verification for this server"
- Should show "Administrator only" badge

**Check via API (optional):**
```bash
# Requires DISCORD_BOT_TOKEN environment variable
curl -X GET \
  "https://discord.com/api/v10/applications/1446567306170863686/commands" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN"
```

**If Command Not Showing:**
- Wait up to 1 hour for Discord cache to update
- Kick and re-invite bot to server
- Check bot has `applications.commands` scope

---

## Core Functionality Tests

### Test Flow Overview

These tests validate the core user journey:

1. Admin sets up the bot (`/setup-email-verification`)
2. Verification message appears with button
3. User clicks button and enters email
4. User receives verification code via email
5. User submits code
6. User receives verified role

Each test below includes:
- Test ID and priority
- Prerequisites
- Step-by-step instructions
- Expected results
- Pass/fail criteria
- Monitoring checkpoints

---

## Priority Test Scenarios

### Priority 1: Critical Functionality (MUST PASS)

These tests are essential for production readiness.

---

#### Test 1.1: Admin Setup Command

**Test ID:** `ADMIN-001`  
**Priority:** 1 (Critical)  
**Duration:** 5 minutes  

**Prerequisites:**
- Logged in as administrator
- Bot is in server
- Bot's role is above "Verified Student" role

**Test Steps:**

1. **Run Setup Command**
   - In Discord, type: `/setup-email-verification`
   - Press Enter

   **Expected:**
   - Command autocompletes
   - Bot responds with role selection dropdown
   - Response appears within 3 seconds

2. **Select Role**
   - Click the role dropdown
   - Select "Verified Student"

   **Expected:**
   - Selection acknowledged
   - Bot shows channel selection dropdown

3. **Select Channel**
   - Click the channel dropdown
   - Select `#verification`

   **Expected:**
   - Bot prompts for allowed email domains
   - Shows text input modal

4. **Enter Allowed Domains**
   - Enter: `student.sans.edu,auburn.edu,test.edu`
   - Submit

   **Expected:**
   - Domains accepted (case-insensitive)
   - Bot asks about custom message

5. **Custom Message (Test Both Options)**

   **Option A: Skip Custom Message**
   - Click "Skip" or submit empty
   - Expected: Default message used

   **Option B: Use Custom Message**
   - Enter: "Welcome to our server! 🎓 Verify your .edu email to get access."
   - Submit
   - Expected: Emoji renders correctly

6. **Review Configuration**
   - Bot shows preview of all settings:
     - Role: Verified Student
     - Channel: #verification
     - Domains: student.sans.edu, auburn.edu, test.edu
     - Message: (your custom message or default)

   **Expected:**
   - All settings correct
   - "Approve Setup" and "Cancel" buttons visible

7. **Approve Setup**
   - Click "Approve Setup"

   **Expected:**
   - Success message: "Configuration saved!"
   - Verification message posted in #verification channel
   - Message has blue "Start Verification" button

**Pass Criteria:**
- [ ] Setup command appears and runs
- [ ] All dropdowns work correctly
- [ ] Domain input accepts comma-separated list
- [ ] Custom message with emojis works
- [ ] Configuration saves successfully
- [ ] Verification message appears in correct channel
- [ ] Button is clickable and styled correctly

**Monitoring:**

Check CloudWatch for:
```
[INFO] Setup command invoked by user_id=123... guild_id=704...
[INFO] Guild configuration saved
```

Verify DynamoDB:
```bash
aws dynamodb get-item \
  --table-name discord-guild-configs \
  --key '{"guild_id": {"S": "704494754129510431"}}' \
  --region us-east-1
```

Expected output includes:
- `role_id`: "849471214711996486"
- `channel_id`: "768351579773468672"
- `allowed_domains`: ["student.sans.edu", "auburn.edu", "test.edu"]

**Troubleshooting:**

| Issue | Solution |
|-------|----------|
| Command doesn't appear | Wait 1 hour or re-invite bot |
| "You don't have permission" | Must have Administrator role |
| Dropdown menus don't show | Check bot has View Channels permission |
| Button doesn't appear in channel | Check bot has Send Messages permission |

---

#### Test 1.2: Happy Path User Verification

**Test ID:** `USER-001`  
**Priority:** 1 (Critical)  
**Duration:** 5 minutes  

**Prerequisites:**
- Guild is configured (Test 1.1 completed)
- User does NOT have "Verified Student" role
- User has access to .edu email inbox
- Verification message visible in #verification channel

**Test Steps:**

1. **Start Verification**
   - Go to #verification channel
   - Find the bot's verification message
   - Click "Start Verification" button

   **Expected:**
   - Modal window appears within 1-2 seconds
   - Title: "Email Verification"
   - Text input field labeled "Enter your .edu email address"
   - Submit button visible

2. **Submit Valid Email**
   - Enter: `yourname@student.sans.edu`
   - Click Submit

   **Expected:**
   - Modal closes
   - Ephemeral message (only you can see):
     - "I've sent a verification code to y***@student.sans.edu"
     - Email address partially redacted for privacy
     - "Submit Code" button visible
   - Response within 3 seconds

3. **Check Email Delivery**
   - Open email inbox for submitted address
   - Look for email from `verificationcode.noreply@thedailydecrypt.com`

   **Expected:**
   - Email arrives within 30 seconds (usually <10 seconds)
   - Subject: Contains "verification code" or similar
   - Body contains 6-digit numeric code
   - Email is well-formatted and readable
   - No spam/suspicious warnings

4. **Submit Verification Code**
   - In Discord, click "Submit Code" button
   - Modal appears for code entry
   - Enter the 6-digit code from email (e.g., `123456`)
   - Click Submit

   **Expected:**
   - Modal closes
   - Success message appears:
     - "Verification complete! You now have access to the server."
   - Message appears within 1-2 seconds

5. **Verify Role Assignment**
   - Check your roles in the server member list
   - Right-click your name > View Profile

   **Expected:**
   - "Verified Student" role is visible
   - Role color matches configured color

6. **Verify Channel Access**
   - Navigate to #verified-only channel

   **Expected:**
   - Channel is now visible
   - Can view messages
   - Can send messages

**Pass Criteria:**
- [ ] Button click triggers modal within 3 seconds
- [ ] Email submission succeeds
- [ ] Verification email received within 30 seconds
- [ ] Email contains valid 6-digit code
- [ ] Code submission succeeds
- [ ] Success message displays
- [ ] Role assigned automatically
- [ ] Restricted channels accessible

**Performance Benchmarks:**
- Button response: <3 seconds (Discord timeout limit)
- Email delivery: <30 seconds (optimal: <10 seconds)
- Code verification: <3 seconds
- Total time: <60 seconds

**Monitoring:**

CloudWatch logs should show:
```
[INFO] Email verification started: user_id=123..., guild_id=704...
[INFO] Email: y***@student.sans.edu
[INFO] Verification code sent successfully
[INFO] Code verification successful
[INFO] Role assigned: role_id=849...
```

DynamoDB verification:
```bash
# Check session was created (during step 2)
aws dynamodb get-item \
  --table-name discord-verification-sessions \
  --key '{"user_id": {"S": "YOUR_USER_ID"}, "guild_id": {"S": "704494754129510431"}}' \
  --region us-east-1

# Check session was deleted (after step 4)
# Should return no item

# Check permanent record exists
aws dynamodb scan \
  --table-name discord-verification-records \
  --filter-expression "user_id = :uid" \
  --expression-attribute-values '{":uid": {"S": "YOUR_USER_ID"}}' \
  --region us-east-1
```

**Troubleshooting:**

| Issue | Solution |
|-------|----------|
| Modal doesn't appear | Check CloudWatch for timeout/errors |
| Email not received | Check spam folder; verify FROM_EMAIL in Lambda config |
| Role not assigned | Check bot role hierarchy; must be ABOVE verified role |
| Code rejected | Check code hasn't expired (15 min limit) |

---

#### Test 1.3: Invalid Email Domain

**Test ID:** `VALIDATION-001`  
**Priority:** 1 (Critical)  
**Duration:** 2 minutes  

**Prerequisites:**
- Guild configured with specific domains
- User in test server

**Test Steps:**

1. **Start Verification**
   - Click "Start Verification" button

2. **Submit Invalid Domain**
   - Enter: `test.user@gmail.com`
   - Click Submit

   **Expected:**
   - Error message appears (ephemeral)
   - Message says: "Invalid email address. Please use an email from one of these domains: student.sans.edu, auburn.edu, test.edu"
   - No email sent
   - User can try again immediately

3. **Test Multiple Invalid Domains**

   Try each of these:
   - `user@yahoo.com` - Expected: Rejected
   - `user@outlook.com` - Expected: Rejected
   - `user@company.edu` - Expected: Rejected (not in allowed list)
   - `invalid-email` - Expected: Rejected (invalid format)
   - `@student.sans.edu` - Expected: Rejected (missing local part)

4. **Test Valid Domain (Control)**
   - Enter: `test@student.sans.edu`
   - Expected: Accepted, email sent

**Pass Criteria:**
- [ ] Gmail/Yahoo/etc rejected
- [ ] Non-allowed .edu domains rejected
- [ ] Invalid email formats rejected
- [ ] Clear error message shows allowed domains
- [ ] No email sent for invalid domains
- [ ] No session created in DynamoDB
- [ ] Valid domain works as control

**Monitoring:**

CloudWatch should show:
```
[WARN] Invalid email domain: user@gmail.com, guild_id=704...
[INFO] Allowed domains: ['student.sans.edu', 'auburn.edu', 'test.edu']
```

Verify NO session created:
```bash
aws dynamodb scan \
  --table-name discord-verification-sessions \
  --filter-expression "email = :email" \
  --expression-attribute-values '{":email": {"S": "test.user@gmail.com"}}' \
  --region us-east-1
```

Expected: No items returned

---

#### Test 1.4: Wrong Verification Code

**Test ID:** `VERIFICATION-001`  
**Priority:** 1 (Critical)  
**Duration:** 5 minutes  

**Prerequisites:**
- Active verification session
- Verification email received

**Test Steps:**

1. **Start Fresh Verification**
   - Start verification process
   - Submit valid email
   - Receive verification code (but don't use it yet)

2. **First Wrong Attempt**
   - Click "Submit Code"
   - Enter: `000000` (wrong code)
   - Submit

   **Expected:**
   - Error message: "Incorrect code. You have 2 attempt(s) remaining."
   - Session still active
   - Can try again

3. **Second Wrong Attempt**
   - Click "Submit Code" again
   - Enter: `111111` (wrong code)
   - Submit

   **Expected:**
   - Error message: "Incorrect code. You have 1 attempt(s) remaining."
   - Session still active
   - Can try again

4. **Third Wrong Attempt (Lockout)**
   - Click "Submit Code" again
   - Enter: `222222` (wrong code)
   - Submit

   **Expected:**
   - Error message: "Incorrect code. Too many failed attempts. Please click 'Start Verification' to start over."
   - Session deleted from DynamoDB
   - "Submit Code" button disappears or becomes inactive
   - Must restart entire verification process

5. **Verify Lockout**
   - Try clicking "Submit Code" (if still visible)
   - Expected: Session not found error OR button inactive

6. **Restart Verification (After Lockout)**
   - Wait 60 seconds (rate limit)
   - Click "Start Verification"
   - Submit email again
   - Receive NEW verification code
   - Submit correct code
   - Expected: Verification succeeds

**Pass Criteria:**
- [ ] First 2 wrong attempts show remaining count
- [ ] Third wrong attempt triggers lockout
- [ ] Session deleted after 3 failures
- [ ] Clear error message explains next steps
- [ ] User can restart after cooldown
- [ ] New code works after restart
- [ ] Attempt counter resets on new session

**Configuration:**
```python
MAX_VERIFICATION_ATTEMPTS = 3  # From verification_logic.py
```

**Monitoring:**

CloudWatch should show:
```
[WARN] Incorrect verification code: attempt 1/3
[WARN] Incorrect verification code: attempt 2/3
[ERROR] Max verification attempts exceeded: 3/3
[INFO] Session deleted due to max attempts
```

DynamoDB verification:
```bash
# Check attempts increment
aws dynamodb get-item \
  --table-name discord-verification-sessions \
  --key '{"user_id": {"S": "YOUR_USER_ID"}, "guild_id": {"S": "704494754129510431"}}' \
  --region us-east-1

# After 3rd attempt, session should be gone
```

---

#### Test 1.5: Rate Limiting

**Test ID:** `SECURITY-001`  
**Priority:** 1 (Critical)  
**Duration:** 3 minutes  

**Prerequisites:**
- User in test server
- No active verification session

**Test Steps:**

1. **First Verification Attempt**
   - Note current time (e.g., 10:00:00)
   - Click "Start Verification"
   - Submit email
   - Expected: Success

2. **Immediate Second Attempt**
   - Immediately click "Start Verification" again
   - Expected:
     - Error message: "Please wait X seconds before starting a new verification."
     - X should be close to 60
     - No email sent
     - No modal shown

3. **Check Rate Limit Message**
   - Verify message shows seconds remaining
   - Example: "Please wait 58 seconds..."

4. **Wait and Retry**
   - Wait exactly 60 seconds from first attempt
   - Click "Start Verification"
   - Expected:
     - Modal appears
     - Can submit email
     - New verification starts

5. **Test Rate Limit is Per-User Per-Guild**
   - Complete verification in Guild A (test server)
   - Immediately try in Guild B (different server with bot)
   - Expected: Guild B allows verification (different guild_id)

**Pass Criteria:**
- [ ] First attempt succeeds
- [ ] Second immediate attempt blocked
- [ ] Error message shows seconds remaining
- [ ] After 60 seconds, can verify again
- [ ] Rate limit is per-user per-guild
- [ ] No email sent during rate limit

**Configuration:**
```python
RATE_LIMIT_SECONDS = 60  # From verification logic
```

**Monitoring:**

CloudWatch should show:
```
[WARN] Rate limit triggered: user_id=123..., seconds_remaining=58
```

DynamoDB check:
```bash
# Session should have created_at timestamp for rate limit check
aws dynamodb get-item \
  --table-name discord-verification-sessions \
  --key '{"user_id": {"S": "YOUR_USER_ID"}, "guild_id": {"S": "704494754129510431"}}' \
  --region us-east-1 \
  | jq '.Item.created_at'
```

---

#### Test 1.6: Email Delivery and Format

**Test ID:** `EMAIL-001`  
**Priority:** 1 (Critical)  
**Duration:** 5 minutes  

**Prerequisites:**
- Active verification session
- Access to email inbox

**Test Steps:**

1. **Start Verification and Submit Email**
   - Start verification
   - Submit: `yourname@student.sans.edu`

2. **Check Email Delivery Time**
   - Note submission time
   - Check inbox
   - Note arrival time
   - **Expected:** Email arrives within 30 seconds (target: <10 seconds)

3. **Verify Email Format**

   **Sender:**
   - From: `verificationcode.noreply@thedailydecrypt.com`
   - Display name: Should be professional
   - No "via" warnings

   **Subject:**
   - Contains "verification" or "code"
   - Clear and professional
   - Not marked as spam

   **Body:**
   - 6-digit numeric code clearly visible
   - Code format: `123456` (6 digits)
   - Professional formatting
   - Clear instructions
   - No broken HTML/formatting
   - Readable on mobile and desktop

   **Headers:**
   - DKIM-Signature present (domain authentication)
   - SPF pass
   - No spam warnings

4. **Test Multiple Email Deliveries**
   - Request 3 separate verifications (60s apart due to rate limit)
   - Each should receive different code
   - All should arrive within time limit

5. **Check Spam Folder (Should Be Empty)**
   - Verify no verification emails in spam
   - If in spam, check DKIM/SPF configuration

**Pass Criteria:**
- [ ] Email arrives within 30 seconds
- [ ] Sender is correct and verified
- [ ] Subject is professional
- [ ] 6-digit code clearly visible
- [ ] Body is well-formatted
- [ ] Not marked as spam
- [ ] DKIM signature present
- [ ] Readable on all devices
- [ ] Each verification gets unique code

**Monitoring:**

CloudWatch should show:
```
[INFO] Sending verification email to: y***@student.sans.edu
[INFO] SES MessageId: 01000123456789ab-cd...
[INFO] Verification code sent successfully
```

Check SES metrics:
```bash
# Check recent send statistics
aws ses get-send-statistics --region us-east-1

# Expected:
# - Recent sends: 1+
# - Bounces: 0
# - Complaints: 0
# - Rejects: 0
```

---

### Priority 2: Important Functionality (SHOULD PASS)

These tests validate important features and security.

---

#### Test 2.1: Code Expiration

**Test ID:** `EXPIRATION-001`  
**Priority:** 2 (Important)  
**Duration:** 16 minutes (or use time manipulation)  

**Prerequisites:**
- Active verification session
- Verification code received

**Test Steps:**

**Method 1: Real-Time Test (16 minutes)**

1. **Start Verification**
   - Start verification
   - Submit email
   - Receive code
   - Note exact time

2. **Wait 16 Minutes**
   - Do NOT submit code
   - Wait 16 minutes (code expires after 15 minutes)

3. **Submit Expired Code**
   - Click "Submit Code"
   - Enter the correct code from email
   - Submit

   **Expected:**
   - Error message: "Verification code has expired (15 minutes). Please click 'Start Verification' again."
   - Session deleted
   - Cannot reuse old code

**Method 2: Quick Test (Manual DynamoDB Manipulation)**

1. **Start Verification**
   - Start verification
   - Submit email
   - Receive code

2. **Get Session Data**
   ```bash
   aws dynamodb get-item \
     --table-name discord-verification-sessions \
     --key '{"user_id": {"S": "YOUR_USER_ID"}, "guild_id": {"S": "704494754129510431"}}' \
     --region us-east-1
   ```

3. **Update Expiration to Past**
   ```bash
   aws dynamodb update-item \
     --table-name discord-verification-sessions \
     --key '{"user_id": {"S": "YOUR_USER_ID"}, "guild_id": {"S": "704494754129510431"}}' \
     --update-expression "SET expires_at = :exp" \
     --expression-attribute-values '{":exp": {"S": "2025-01-01T00:00:00"}}' \
     --region us-east-1
   ```

4. **Submit Code**
   - In Discord, submit the code
   - Expected: Expiration error

5. **Restart and Verify New Code Works**
   - Wait 60 seconds
   - Start verification again
   - New code should work within 15 minutes

**Pass Criteria:**
- [ ] Code expires after exactly 15 minutes
- [ ] Clear expiration error message
- [ ] Session deleted after expiration
- [ ] Old code cannot be reused
- [ ] New verification creates new code
- [ ] New code works correctly

**Configuration:**
```python
CODE_EXPIRATION_MINUTES = 15  # From verification logic
```

**Monitoring:**

CloudWatch should show:
```
[ERROR] Verification code expired: expires_at=2025-..., current_time=2025-...
[INFO] Session deleted due to expiration
```

---

#### Test 2.2: Already Verified User

**Test ID:** `DUPLICATE-001`  
**Priority:** 2 (Important)  
**Duration:** 3 minutes  

**Prerequisites:**
- User has already completed verification
- User has "Verified Student" role

**Test Steps:**

1. **Test Role-Based Check**
   - User with "Verified Student" role clicks "Start Verification"
   - Expected: "You already have the verified role! No need to verify again."
   - No modal shown
   - No email sent

2. **Test Database Check**
   - Admin removes "Verified Student" role from user
   - User still has record in database
   - User clicks "Start Verification"
   - Expected: "You are already verified in this server!"

3. **Test Cross-Guild Independence**
   - User verified in Guild A
   - User joins Guild B (different server)
   - User should NOT have "Verified Student" in Guild B
   - User can verify in Guild B (independent verification)

**Pass Criteria:**
- [ ] User with role cannot re-verify
- [ ] User with database record cannot re-verify
- [ ] Appropriate messages for each case
- [ ] No email sent
- [ ] No session created
- [ ] Verification is guild-specific

**Monitoring:**

CloudWatch should show:
```
[INFO] User already has verified role: user_id=123..., guild_id=704...
```
OR
```
[INFO] User already verified in database: user_id=123..., guild_id=704...
```

---

#### Test 2.3: Concurrent Multi-User Testing

**Test ID:** `CONCURRENT-001`  
**Priority:** 2 (Important)  
**Duration:** 10 minutes  

**Prerequisites:**
- 2+ Discord accounts
- 2+ email addresses
- Both users lack "Verified Student" role

**Test Steps:**

1. **User 1 Starts Verification**
   - User 1 clicks "Start Verification"
   - Submits: `user1@student.sans.edu`
   - Receives code (don't submit yet)

2. **User 2 Starts Verification (While User 1 Active)**
   - User 2 clicks "Start Verification"
   - Submits: `user2@student.sans.edu`
   - Receives code (don't submit yet)

3. **Verify Session Independence**
   - Check both sessions exist in DynamoDB
   - Verify different verification codes
   - Verify different user_ids

4. **User 1 Submits Code**
   - User 1 submits correct code
   - Expected: User 1 gets role

5. **User 2 Submits Code**
   - User 2 submits correct code
   - Expected: User 2 gets role

6. **Verify Both Succeeded**
   - Check both users have "Verified Student" role
   - Check both have records in database
   - Check sessions were cleaned up

**Pass Criteria:**
- [ ] Both users can start verification concurrently
- [ ] Sessions don't interfere
- [ ] Different codes generated for each user
- [ ] Both emails delivered
- [ ] Both verifications succeed
- [ ] Both records saved
- [ ] Sessions cleaned up

**Monitoring:**

CloudWatch should show:
```
[INFO] Email verification started: user_id=111...
[INFO] Email verification started: user_id=222...
[INFO] Code verification successful: user_id=111...
[INFO] Code verification successful: user_id=222...
```

DynamoDB verification:
```bash
# Check both sessions exist (during testing)
aws dynamodb scan \
  --table-name discord-verification-sessions \
  --filter-expression "guild_id = :gid" \
  --expression-attribute-values '{":gid": {"S": "704494754129510431"}}' \
  --region us-east-1

# Should show 2 active sessions
```

---

#### Test 2.4: Permission Edge Cases

**Test ID:** `PERMISSIONS-001`  
**Priority:** 2 (Important)  
**Duration:** 10 minutes  

**Test Steps:**

**Scenario A: Bot Role Below Verified Role**

1. **Setup:**
   - Go to Server Settings > Roles
   - Move bot's role BELOW "Verified Student" in hierarchy
   - Save

2. **Test Verification:**
   - User completes verification
   - Submits correct code

   **Expected:**
   - Verification succeeds
   - Success message shown
   - BUT role assignment fails (silent or with error)
   - Error in CloudWatch: "Missing Permissions" or "403 Forbidden"

3. **Fix and Retry:**
   - Move bot role back ABOVE "Verified Student"
   - Admin manually assigns role OR user verifies again
   - Should work correctly

**Scenario B: Missing Manage Roles Permission**

1. **Setup:**
   - Server Settings > Roles > Bot's role
   - Disable "Manage Roles" permission
   - Save

2. **Test Verification:**
   - User completes verification
   - Expected: Same as Scenario A (role assignment fails)

3. **Fix:**
   - Re-enable "Manage Roles" permission

**Scenario C: Non-Admin Tries Setup**

1. **Test:**
   - Regular user (not admin) tries `/setup-email-verification`

   **Expected:**
   - Discord shows "You don't have permission" OR
   - Bot responds: "You need Administrator permissions to run this command."
   - No setup allowed

**Scenario D: Setup in DM**

1. **Test:**
   - User DMs bot
   - Tries `/setup-email-verification`

   **Expected:**
   - Command not shown in DM OR
   - Error: "This command can only be used in a server"

**Pass Criteria:**
- [ ] Permission errors handled gracefully
- [ ] Clear error messages
- [ ] Logs show authorization failures
- [ ] Non-admins cannot run setup
- [ ] Role hierarchy respected
- [ ] Required permissions enforced

**Monitoring:**

CloudWatch should show:
```
[ERROR] Failed to assign role: 403 Forbidden
[ERROR] Missing Permissions: Requires 'MANAGE_ROLES'
```
OR
```
[WARN] Authorization check failed: user=regular_user, permissions=0, admin=False
```

---

### Priority 3: Nice to Have (OPTIONAL)

These tests validate edge cases and cross-platform functionality.

---

#### Test 3.1: Cross-Platform Testing

**Test ID:** `PLATFORM-001`  
**Priority:** 3 (Optional)  
**Duration:** 15 minutes  

**Test Platforms:**
- Discord Desktop App (Windows/Mac/Linux)
- Discord Web Browser (Chrome, Firefox, Safari)
- Discord Mobile App (iOS/Android)

**For Each Platform, Test:**

1. **Button Interaction**
   - Click "Start Verification" button
   - Verify modal appears
   - Check modal is properly sized and positioned

2. **Email Input**
   - Type email address
   - Check keyboard layout (should show @ and .edu shortcuts on mobile)
   - Submit

3. **Code Input**
   - Click "Submit Code"
   - Check keyboard layout (should show numeric keyboard on mobile)
   - Enter code
   - Submit

4. **Message Rendering**
   - Verify success message displays correctly
   - Check emojis render
   - Check text is readable

**Mobile-Specific Checks:**
- [ ] Buttons are tap-friendly (not too small)
- [ ] Modal keyboard auto-appears
- [ ] Email keyboard shows relevant keys
- [ ] Code input shows numeric keyboard
- [ ] Long messages don't break layout
- [ ] Ephemeral messages visible
- [ ] No horizontal scrolling

**Desktop-Specific Checks:**
- [ ] Modals centered properly
- [ ] Tab navigation works
- [ ] Enter key submits forms
- [ ] Copy/paste works for codes

**Pass Criteria:**
- [ ] Consistent behavior across platforms
- [ ] No UI breaking or layout issues
- [ ] All modals functional
- [ ] Buttons clickable on all devices

---

#### Test 3.2: Email Address Edge Cases

**Test ID:** `EMAIL-EDGE-001`  
**Priority:** 3 (Optional)  
**Duration:** 5 minutes  

**Test Various Email Formats:**

1. **Email with Plus Tag**
   - Submit: `user+test@student.sans.edu`
   - Expected: ACCEPTED (standard email feature)

2. **Email with Dots**
   - Submit: `first.last@student.sans.edu`
   - Expected: ACCEPTED

3. **Email with Numbers**
   - Submit: `user123@student.sans.edu`
   - Expected: ACCEPTED

4. **Email with Hyphens**
   - Submit: `first-last@student.sans.edu`
   - Expected: ACCEPTED

5. **Case Variations**
   - Submit: `USER@STUDENT.SANS.EDU`
   - Expected: ACCEPTED (case-insensitive domain check)

6. **Subdomain**
   - Submit: `user@mail.student.sans.edu`
   - Expected: REJECTED (exact domain match required)

7. **Leading/Trailing Spaces**
   - Submit: ` user@student.sans.edu ` (with spaces)
   - Expected: ACCEPTED (should be trimmed) OR REJECTED

8. **Special Characters**
   - Submit: `user!@student.sans.edu`
   - Expected: REJECTED (invalid format)

**Pass Criteria:**
- [ ] Standard email variations accepted
- [ ] Invalid formats rejected
- [ ] Case-insensitive domain checking
- [ ] Clear error messages for rejections

---

#### Test 3.3: Duplicate Email Prevention

**Test ID:** `DUPLICATE-EMAIL-001`  
**Priority:** 3 (Optional)  
**Duration:** 5 minutes  

**Test Steps:**

1. **User 1 Verifies with Email**
   - User 1 completes verification
   - Email: `shared@student.sans.edu`
   - Gets "Verified Student" role

2. **User 2 Tries Same Email**
   - User 2 starts verification
   - Enters same email: `shared@student.sans.edu`
   - Submits

   **Expected (if implemented):**
   - Error: "This email has already been used for verification"
   - OR allows it (depends on implementation)

**Check Implementation:**
- Review code to see if duplicate email checking is implemented
- If not implemented, document as feature request

---

## Monitoring and Logs

### Real-Time Monitoring During Tests

**CloudWatch Logs Dashboard:**

Start this before all testing:

```bash
# Terminal 1: All logs
aws logs tail /aws/lambda/discord-verification-handler \
  --follow \
  --region us-east-1

# Terminal 2: Errors only
aws logs tail /aws/lambda/discord-verification-handler \
  --follow \
  --filter-pattern "ERROR" \
  --region us-east-1

# Terminal 3: Performance metrics
aws logs tail /aws/lambda/discord-verification-handler \
  --follow \
  --filter-pattern "REPORT" \
  --region us-east-1
```

---

### What to Look For in Logs

**Successful Verification Flow:**
```
START RequestId: abc123-def456-...
[INFO] Interaction received: type=3 (MESSAGE_COMPONENT)
[INFO] Button click: start_verification
[INFO] User: 123456789012345678, Guild: 704494754129510431
[INFO] Showing email modal
END RequestId: abc123-def456-...
REPORT RequestId: abc123-def456-... Duration: 234.56 ms Billed Duration: 235 ms Memory Size: 512 MB Max Memory Used: 128 MB

START RequestId: ghi789-jkl012-...
[INFO] Interaction received: type=5 (MODAL_SUBMIT)
[INFO] Modal: email_submission_modal
[INFO] Email verification started: user_id=123..., guild_id=704...
[INFO] Email: y***@student.sans.edu
[INFO] Sending verification email
[INFO] SES MessageId: 01000123456789ab-...
[INFO] Verification code sent successfully
END RequestId: ghi789-jkl012-...
REPORT RequestId: ghi789-jkl012-... Duration: 567.89 ms Billed Duration: 568 ms

START RequestId: mno345-pqr678-...
[INFO] Interaction received: type=5 (MODAL_SUBMIT)
[INFO] Modal: code_submission_modal
[INFO] Code verification attempt: user_id=123..., guild_id=704...
[INFO] Code verification successful
[INFO] Assigning role: role_id=849...
[INFO] Role assigned successfully
[INFO] Session deleted
[INFO] Verification record created
END RequestId: mno345-pqr678-...
REPORT RequestId: mno345-pqr678-... Duration: 432.10 ms Billed Duration: 433 ms
```

**Error Patterns to Watch:**

**Permission Error:**
```
[ERROR] Failed to assign role: 403 Forbidden
[ERROR] Missing Permissions: Requires 'MANAGE_ROLES'
```

**Rate Limit:**
```
[WARN] Rate limit triggered: user_id=123..., seconds_remaining=45
```

**Invalid Email:**
```
[WARN] Invalid email domain: user@gmail.com
[INFO] Allowed domains: ['student.sans.edu', 'auburn.edu', 'test.edu']
```

**Max Attempts:**
```
[WARN] Incorrect verification code: attempt 1/3
[WARN] Incorrect verification code: attempt 2/3
[ERROR] Max verification attempts exceeded: 3/3
[INFO] Session deleted due to max attempts
```

**Code Expiration:**
```
[ERROR] Verification code expired: expires_at=2025-12-09T10:00:00
[INFO] Session deleted due to expiration
```

---

### Performance Metrics

**Lambda Performance:**

```bash
# Get average duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=discord-verification-handler \
  --start-time 2025-12-09T00:00:00Z \
  --end-time 2025-12-09T23:59:59Z \
  --period 3600 \
  --statistics Average,Maximum \
  --region us-east-1
```

**Expected Performance:**
- Average duration: <500ms
- Maximum duration: <3000ms (Discord timeout)
- Cold start: <2000ms

**SES Metrics:**

```bash
# Check email statistics
aws ses get-send-statistics --region us-east-1

# Check quota usage
aws ses get-send-quota --region us-east-1
```

**Expected During Testing:**
- Sends: 10-50 (depending on tests run)
- Bounces: 0
- Complaints: 0
- Rejects: 0

---

### DynamoDB Monitoring

**Check Table Status:**

```bash
# Sessions table (should be mostly empty)
aws dynamodb scan \
  --table-name discord-verification-sessions \
  --select COUNT \
  --region us-east-1

# Expected: 0-2 (only during active verifications)

# Records table (should grow with each verification)
aws dynamodb scan \
  --table-name discord-verification-records \
  --select COUNT \
  --region us-east-1

# Expected: Increases with each successful verification

# Guild configs table
aws dynamodb scan \
  --table-name discord-guild-configs \
  --select COUNT \
  --region us-east-1

# Expected: 1+ (one per configured guild)
```

**Check Specific Records:**

```bash
# Get guild configuration
aws dynamodb get-item \
  --table-name discord-guild-configs \
  --key '{"guild_id": {"S": "704494754129510431"}}' \
  --region us-east-1

# Get active session (if exists)
aws dynamodb get-item \
  --table-name discord-verification-sessions \
  --key '{"user_id": {"S": "YOUR_USER_ID"}, "guild_id": {"S": "704494754129510431"}}' \
  --region us-east-1

# Scan verification records
aws dynamodb scan \
  --table-name discord-verification-records \
  --filter-expression "guild_id = :gid" \
  --expression-attribute-values '{":gid": {"S": "704494754129510431"}}' \
  --region us-east-1
```

---

### Security Logging Validation

**Check for PII Redaction:**

Search logs for email addresses:

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "@student.sans.edu" \
  --region us-east-1
```

**Expected:**
- Emails should appear as: `y***@student.sans.edu`
- Full email should NOT appear in logs
- Verification codes should NOT appear in logs

**Check Security Events:**

```bash
# Rate limit events
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "Rate limit" \
  --region us-east-1

# Max attempts events
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "Max attempts" \
  --region us-east-1

# Authorization failures
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "Authorization" \
  --region us-east-1
```

---

## Test Results Template

### Test Session Record

Use this template to document each testing session:

```markdown
# Testing Session - [Date]

## Environment
- Tester: [Your Name]
- Guild ID: 704494754129510431
- Lambda Version: [Check AWS Console]
- Duration: [Start Time] to [End Time]

## Tests Executed

### Priority 1 Tests
- [ ] Test 1.1: Admin Setup - PASS/FAIL
  - Notes: [Any issues or observations]
- [ ] Test 1.2: Happy Path Verification - PASS/FAIL
  - Email delivery time: X seconds
  - Notes: [Any issues or observations]
- [ ] Test 1.3: Invalid Email Domain - PASS/FAIL
- [ ] Test 1.4: Wrong Verification Code - PASS/FAIL
- [ ] Test 1.5: Rate Limiting - PASS/FAIL
- [ ] Test 1.6: Email Delivery and Format - PASS/FAIL

### Priority 2 Tests
- [ ] Test 2.1: Code Expiration - PASS/FAIL/SKIP
- [ ] Test 2.2: Already Verified User - PASS/FAIL/SKIP
- [ ] Test 2.3: Concurrent Multi-User - PASS/FAIL/SKIP
- [ ] Test 2.4: Permission Edge Cases - PASS/FAIL/SKIP

### Priority 3 Tests
- [ ] Test 3.1: Cross-Platform - PASS/FAIL/SKIP
- [ ] Test 3.2: Email Edge Cases - PASS/FAIL/SKIP
- [ ] Test 3.3: Duplicate Email - PASS/FAIL/SKIP

## Performance Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Button response time | <3s | Xs | PASS/FAIL |
| Email delivery time | <30s | Xs | PASS/FAIL |
| Code verification time | <3s | Xs | PASS/FAIL |
| Lambda avg duration | <500ms | Xms | PASS/FAIL |
| Lambda cold start | <2000ms | Xms | PASS/FAIL |

## Issues Found

### Issue 1: [Title]
- **Severity:** Critical/High/Medium/Low
- **Test:** [Test ID]
- **Description:** [What happened]
- **Expected:** [What should happen]
- **Actual:** [What actually happened]
- **Steps to Reproduce:**
  1. Step 1
  2. Step 2
- **Screenshots:** [Link or attach]
- **Logs:** [Relevant CloudWatch logs]

### Issue 2: [Title]
[Same format as Issue 1]

## Overall Assessment

**Total Tests Run:** X  
**Passed:** Y  
**Failed:** Z  
**Skipped:** W  

**Production Ready:** YES/NO  

**Recommendations:**
1. [Recommendation 1]
2. [Recommendation 2]

**Next Steps:**
1. [Next step 1]
2. [Next step 2]
```

---

### Quick Test Checklist

Use this for rapid validation:

```
Quick Test Checklist - [Date]

Pre-Testing:
[ ] Discord endpoint updated
[ ] CloudWatch logs running
[ ] AWS resources verified
[ ] Test accounts ready

Essential Tests (30 min):
[ ] Admin setup works
[ ] User can verify successfully
[ ] Invalid emails rejected
[ ] Wrong codes tracked (3 attempts)
[ ] Rate limiting works (60 sec)
[ ] Email arrives <30 sec

Success Criteria:
[ ] 3+ successful verifications
[ ] No Lambda errors
[ ] Roles assigned correctly
[ ] No PII in logs
[ ] Performance acceptable

Status: PASS / FAIL
Notes: [Quick notes]
```

---

## Troubleshooting

### Common Issues and Solutions

---

#### Issue: "Application did not respond"

**Symptoms:**
- User clicks button
- Discord shows "Application did not respond" after 3 seconds
- No modal appears

**Diagnosis:**

```bash
# Check Lambda execution time
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "REPORT" \
  --max-items 10 \
  --region us-east-1

# Check for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "ERROR" \
  --max-items 10 \
  --region us-east-1
```

**Solutions:**

1. **Lambda Timeout**
   - Check timeout setting (should be 30 seconds)
   - Increase if needed:
     ```bash
     aws lambda update-function-configuration \
       --function-name discord-verification-handler \
       --timeout 30 \
       --region us-east-1
     ```

2. **Cold Start**
   - First invocation may be slow (Lambda cold start)
   - Try again - subsequent calls should be faster
   - Consider provisioned concurrency for production

3. **DynamoDB Throttling**
   - Check CloudWatch for throttling metrics
   - Tables are on-demand, so unlikely
   - Verify IAM permissions

4. **Network Issues**
   - If Lambda is in VPC, ensure NAT Gateway configured
   - Check security group rules

---

#### Issue: Email Not Received

**Symptoms:**
- User submits email
- Success message shown in Discord
- No email arrives in inbox (even after 60+ seconds)

**Diagnosis:**

```bash
# Check SES send statistics
aws ses get-send-statistics --region us-east-1

# Check Lambda logs for SES errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "SES\|email\|MessageId" \
  --max-items 20 \
  --region us-east-1
```

**Solutions:**

1. **Check Spam Folder**
   - First place to check
   - If in spam, may need to improve DKIM/SPF

2. **Wrong FROM_EMAIL**
   - Verify Lambda environment variable:
     ```bash
     aws lambda get-function-configuration \
       --function-name discord-verification-handler \
       --query 'Environment.Variables.FROM_EMAIL' \
       --region us-east-1
     ```
   - Should be: `verificationcode.noreply@thedailydecrypt.com`

3. **SES Bounce/Complaint List**
   - Check if recipient is suppressed:
     ```bash
     aws sesv2 list-suppressed-destinations --region us-east-1
     ```

4. **Email Provider Blocking**
   - Some .edu email systems have strict filters
   - Try different email address
   - Contact email admin if persistent

5. **SES Region Mismatch**
   - Verify SES and Lambda in same region (us-east-1)

---

#### Issue: Role Not Assigned

**Symptoms:**
- Verification completes successfully
- Success message shown
- User does NOT receive "Verified Student" role

**Diagnosis:**

```bash
# Check Lambda logs for role assignment
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "assign_role\|Role assigned" \
  --max-items 10 \
  --region us-east-1
```

**Solutions:**

1. **Role Hierarchy (Most Common)**
   - Go to Server Settings > Roles
   - Bot's role MUST be ABOVE "Verified Student"
   - Drag bot role up in the list
   - Try verification again

2. **Missing Permission**
   - Verify bot has "Manage Roles" permission
   - Server Settings > Roles > Bot Role
   - Enable "Manage Roles"

3. **Wrong Role ID**
   - Check guild configuration:
     ```bash
     aws dynamodb get-item \
       --table-name discord-guild-configs \
       --key '{"guild_id": {"S": "704494754129510431"}}' \
       --region us-east-1
     ```
   - Verify role_id matches actual role

4. **Bot Token Issue**
   - Verify bot token in SSM:
     ```bash
     aws ssm get-parameter \
       --name /discord-bot/token \
       --with-decryption \
       --region us-east-1
     ```
   - If invalid, update and redeploy Lambda

5. **Discord API Rate Limit**
   - Check logs for "429 Too Many Requests"
   - Wait and try again
   - Should be rare for testing

---

#### Issue: Rate Limit Not Working

**Symptoms:**
- User can spam "Start Verification" button
- No "Please wait" message
- Multiple emails sent rapidly

**Diagnosis:**

```bash
# Check sessions table
aws dynamodb scan \
  --table-name discord-verification-sessions \
  --region us-east-1

# Check rate limit logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "Rate limit" \
  --max-items 10 \
  --region us-east-1
```

**Solutions:**

1. **Session Not Created**
   - Verify session is written to DynamoDB
   - Check IAM permissions for DynamoDB

2. **Timestamp Issue**
   - Check session has `created_at` field
   - Verify timestamp format is correct

3. **Logic Bug**
   - Check Lambda code version
   - May need to redeploy

4. **Different Guild**
   - Rate limit is per-user per-guild
   - Verify testing in same guild

---

#### Issue: Modal Not Appearing

**Symptoms:**
- User clicks button
- Nothing happens
- No modal window

**Diagnosis:**

```bash
# Check interaction response type
aws logs filter-log-events \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "Interaction received\|response" \
  --max-items 20 \
  --region us-east-1
```

**Solutions:**

1. **Response Type**
   - Verify Lambda returns type 9 (MODAL)
   - Check CloudWatch logs for response structure

2. **Response Time**
   - Must respond within 3 seconds
   - Check Lambda duration in logs

3. **JSON Format**
   - Verify response JSON is valid
   - Check for syntax errors in logs

4. **Discord Client Issue**
   - Try different Discord client (web, desktop, mobile)
   - Clear Discord cache
   - Restart Discord

---

#### Issue: Signature Verification Failures

**Symptoms:**
- All interactions return 401
- "Invalid signature" in logs
- Discord cannot verify endpoint

**Diagnosis:**

```bash
# Check public key
aws lambda get-function-configuration \
  --function-name discord-verification-handler \
  --query 'Environment.Variables.DISCORD_PUBLIC_KEY' \
  --region us-east-1
```

**Solutions:**

1. **Wrong Public Key**
   - Go to Discord Developer Portal > General Information
   - Copy PUBLIC KEY (64 hex characters)
   - Update Lambda:
     ```bash
     aws lambda update-function-configuration \
       --function-name discord-verification-handler \
       --environment Variables={DISCORD_PUBLIC_KEY=YOUR_CORRECT_KEY,...} \
       --region us-east-1
     ```

2. **Extra Whitespace**
   - Ensure no spaces or newlines in key
   - Key should be exactly 64 hex characters

3. **Wrong Environment Variable Name**
   - Must be: `DISCORD_PUBLIC_KEY`
   - Case-sensitive

---

#### Issue: Database Errors

**Symptoms:**
- "ResourceNotFoundException"
- "AccessDeniedException"
- Verification fails at various steps

**Diagnosis:**

```bash
# Verify tables exist
aws dynamodb list-tables --region us-east-1 | grep discord

# Check IAM permissions
aws iam get-role-policy \
  --role-name discord-verification-lambda-role \
  --policy-name discord-verification-lambda-policy \
  --region us-east-1
```

**Solutions:**

1. **Table Names**
   - Verify environment variables match actual tables:
     ```bash
     aws lambda get-function-configuration \
       --function-name discord-verification-handler \
       --query 'Environment.Variables' \
       --region us-east-1
     ```

2. **IAM Permissions**
   - Verify Lambda role has DynamoDB permissions
   - Should include: GetItem, PutItem, UpdateItem, DeleteItem, Query

3. **Region Mismatch**
   - Verify DynamoDB tables and Lambda in same region (us-east-1)

4. **Table Status**
   - Check tables are ACTIVE:
     ```bash
     aws dynamodb describe-table \
       --table-name discord-verification-sessions \
       --region us-east-1 \
       | jq '.Table.TableStatus'
     ```

---

### Emergency Procedures

#### Disable Bot Immediately

If critical issues are found:

1. **Remove Interactions Endpoint:**
   - Go to Discord Developer Portal
   - General Information > Interactions Endpoint URL
   - Clear the URL field
   - Click Save Changes
   - Bot will stop receiving interactions immediately

2. **Notify Users:**
   - Post message in Discord server
   - "Bot temporarily offline for maintenance"

#### Rollback Lambda

If new deployment is broken:

```bash
# List versions
aws lambda list-versions-by-function \
  --function-name discord-verification-handler \
  --region us-east-1

# Get previous version code
aws lambda get-function \
  --function-name discord-verification-handler \
  --qualifier VERSION_NUMBER \
  --region us-east-1

# Rollback to previous version
aws lambda update-function-code \
  --function-name discord-verification-handler \
  --s3-bucket YOUR_BACKUP_BUCKET \
  --s3-key previous-version.zip \
  --region us-east-1
```

#### Restore Guild Configuration

If configuration was corrupted:

```bash
# Restore from backup file
aws dynamodb put-item \
  --table-name discord-guild-configs \
  --item file://backup-guild-configs-20251208-214344.json \
  --region us-east-1
```

---

## Success Criteria

### Production Readiness Checklist

The bot is production-ready when ALL of these are met:

**Essential Functionality:**
- [ ] All Priority 1 tests pass (6/6)
- [ ] At least 5 successful user verifications completed
- [ ] Email delivery works consistently (<30 second average)
- [ ] Role assignment works 100% of the time
- [ ] No critical errors in CloudWatch logs
- [ ] Invalid emails rejected correctly
- [ ] Rate limiting enforced properly

**Security and Privacy:**
- [ ] No PII (full emails, codes) in logs
- [ ] Email addresses redacted: `y***@domain.edu`
- [ ] Rate limiting prevents abuse
- [ ] Max attempts (3) enforced
- [ ] Code expiration (15 min) works
- [ ] Discord signature verification working

**Performance:**
- [ ] Button response time <3 seconds (100% of tests)
- [ ] Email delivery time <30 seconds (average)
- [ ] Code verification <3 seconds
- [ ] Lambda cold start <5 seconds
- [ ] Lambda warm execution <1 second

**Reliability:**
- [ ] Concurrent users work without interference
- [ ] Sessions cleaned up after verification
- [ ] Database records persist correctly
- [ ] Error handling graceful and informative
- [ ] No data corruption or loss

**User Experience:**
- [ ] Setup wizard intuitive and complete
- [ ] Error messages clear and helpful
- [ ] Verification flow smooth (no confusing steps)
- [ ] Success messages encouraging
- [ ] Works on desktop and mobile

**Monitoring:**
- [ ] CloudWatch logs capture all events
- [ ] Errors logged with context
- [ ] Performance metrics tracked
- [ ] SES statistics available
- [ ] DynamoDB metrics monitored

---

### Performance Benchmarks

| Metric | Target | Acceptable | Poor | Your Result |
|--------|--------|------------|------|-------------|
| Button click → Modal | <1s | <3s | >3s | ___ |
| Email delivery | <10s | <30s | >30s | ___ |
| Code verification | <1s | <3s | >3s | ___ |
| Lambda cold start | <2s | <5s | >5s | ___ |
| Lambda warm exec | <500ms | <1s | >1s | ___ |
| Setup wizard | <30s | <60s | >60s | ___ |

---

### Reliability Metrics

**Success Rates (Minimum):**
- Verification completion rate: >95%
- Email delivery rate: >99%
- Role assignment rate: 100% (with correct permissions)
- Uptime: >99.9%

**Error Handling (Required):**
- All errors logged: 100%
- User-friendly error messages: 100%
- Graceful degradation: 100%
- No data loss on error: 100%

---

### Final Go/No-Go Decision

**GO for Production if:**
- All Priority 1 tests pass
- All security requirements met
- Performance within acceptable range
- No critical or high-severity bugs
- Monitoring and alerting configured

**NO-GO if:**
- Any Priority 1 test fails
- Critical security issue found
- Performance unacceptable (>3s response)
- Data loss or corruption possible
- High-severity bugs present

---

## Next Steps After Testing

### If All Tests Pass

1. **Document Results:**
   - Complete test results template
   - Save CloudWatch logs
   - Note any minor issues for future improvement

2. **Set Up Production Monitoring:**
   ```bash
   # Create CloudWatch alarm for errors
   aws cloudwatch put-metric-alarm \
     --alarm-name discord-bot-error-rate \
     --alarm-description "Alert on Lambda errors" \
     --metric-name Errors \
     --namespace AWS/Lambda \
     --statistic Sum \
     --period 300 \
     --threshold 5 \
     --comparison-operator GreaterThanThreshold \
     --evaluation-periods 1 \
     --dimensions Name=FunctionName,Value=discord-verification-handler \
     --region us-east-1

   # Create alarm for high duration
   aws cloudwatch put-metric-alarm \
     --alarm-name discord-bot-slow-response \
     --alarm-description "Alert on slow Lambda execution" \
     --metric-name Duration \
     --namespace AWS/Lambda \
     --statistic Average \
     --period 300 \
     --threshold 2000 \
     --comparison-operator GreaterThanThreshold \
     --evaluation-periods 2 \
     --dimensions Name=FunctionName,Value=discord-verification-handler \
     --region us-east-1
   ```

3. **Create CloudWatch Dashboard:**
   - Lambda invocations, errors, duration
   - DynamoDB read/write metrics
   - SES send statistics

4. **Schedule Regular Testing:**
   - Weekly: Quick smoke test (Test 1.2)
   - Monthly: Full Priority 1 test suite
   - After any code changes: Relevant test scenarios

5. **Expand to More Guilds:**
   - Invite bot to additional Discord servers
   - Test with different configurations
   - Monitor for scale issues

6. **Document for Users:**
   - Create user guide for server admins
   - FAQ for common questions
   - Support contact information

---

### If Tests Fail

1. **Document Failures:**
   - Use test results template
   - Include screenshots
   - Save relevant CloudWatch logs
   - Note exact steps to reproduce

2. **Create GitHub Issues:**
   - One issue per bug
   - Include reproduction steps
   - Link to test case
   - Severity and priority labels

3. **Fix Critical Issues First:**
   - Priority 1 failures block production
   - Fix and retest immediately
   - Document changes made

4. **Retest After Fixes:**
   - Run failed tests again
   - Run regression tests (ensure fixes didn't break other features)
   - Document new results

5. **Consider Rollback:**
   - If unfixable in short time
   - Restore previous working version
   - Plan fix for future deployment

---

## Appendices

### Appendix A: Test Data

**Test Guild Information:**
- Guild ID: `704494754129510431`
- Guild Name: [Your test server name]
- Channel ID (verification): `768351579773468672`
- Role ID (verified): `849471214711996486`

**Test Email Addresses:**
- Primary: `yourname@student.sans.edu`
- Secondary: `colleague@student.sans.edu`
- Invalid (for testing): `test@gmail.com`

**Bot Information:**
- Application ID: `1446567306170863686`
- Public Key: `fb86b839e3d052f72cb07bddb399a98e43d16c94ab48c9444a9c200ddd518169`
- Lambda Function: `discord-verification-handler`
- Function URL: `https://dmnw3lxadg36anjkjmkfbjegbi0vemfx.lambda-url.us-east-1.on.aws/`

---

### Appendix B: Quick Command Reference

**AWS CLI Commands:**

```bash
# CloudWatch Logs
aws logs tail /aws/lambda/discord-verification-handler --follow --region us-east-1
aws logs filter-log-events --log-group-name /aws/lambda/discord-verification-handler --filter-pattern "ERROR" --region us-east-1

# Lambda
aws lambda get-function --function-name discord-verification-handler --region us-east-1
aws lambda get-function-configuration --function-name discord-verification-handler --region us-east-1

# DynamoDB
aws dynamodb get-item --table-name discord-guild-configs --key '{"guild_id": {"S": "704494754129510431"}}' --region us-east-1
aws dynamodb scan --table-name discord-verification-sessions --select COUNT --region us-east-1
aws dynamodb scan --table-name discord-verification-records --select COUNT --region us-east-1

# SES
aws ses get-send-quota --region us-east-1
aws ses get-send-statistics --region us-east-1
aws sesv2 get-account --region us-east-1

# CloudWatch Metrics
aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Duration --dimensions Name=FunctionName,Value=discord-verification-handler --start-time 2025-12-09T00:00:00Z --end-time 2025-12-09T23:59:59Z --period 3600 --statistics Average,Maximum --region us-east-1
```

---

### Appendix C: Configuration Reference

**Lambda Environment Variables:**
```
DISCORD_PUBLIC_KEY=fb86b839e3d052f72cb07bddb399a98e43d16c94ab48c9444a9c200ddd518169
DYNAMODB_SESSIONS_TABLE=discord-verification-sessions
DYNAMODB_RECORDS_TABLE=discord-verification-records
DYNAMODB_GUILD_CONFIGS_TABLE=discord-guild-configs
FROM_EMAIL=verificationcode.noreply@thedailydecrypt.com
```

**Bot Configuration Constants:**
```python
MAX_VERIFICATION_ATTEMPTS = 3
CODE_LENGTH = 6
CODE_EXPIRATION_MINUTES = 15
RATE_LIMIT_SECONDS = 60
```

**Discord Permissions Required:**
- Manage Roles (268435456)
- View Channels (included in Manage Roles)
- Send Messages (included in Manage Roles)

---

### Appendix D: Useful Links

**Discord:**
- Developer Portal: https://discord.com/developers/applications
- Bot Invite (replace app ID): https://discord.com/oauth2/authorize?client_id=1446567306170863686&permissions=268435456&scope=bot%20applications.commands

**AWS Console:**
- Lambda Functions: https://console.aws.amazon.com/lambda
- DynamoDB Tables: https://console.aws.amazon.com/dynamodb
- CloudWatch Logs: https://console.aws.amazon.com/cloudwatch
- SES: https://console.aws.amazon.com/ses

**Documentation:**
- Discord API Docs: https://discord.com/developers/docs
- AWS Lambda Docs: https://docs.aws.amazon.com/lambda
- AWS SES Docs: https://docs.aws.amazon.com/ses

---

## Summary

This comprehensive testing guide covers:

- **Pre-testing setup** including Discord Developer Portal configuration
- **15 detailed test scenarios** organized by priority
- **Step-by-step instructions** with expected results and pass criteria
- **Real-time monitoring** with CloudWatch logs and metrics
- **Comprehensive troubleshooting** for common issues
- **Clear success criteria** for production readiness
- **Test results templates** for documentation

**Estimated Testing Time:**
- Essential tests (Priority 1): 45-60 minutes
- Full comprehensive testing: 2-3 hours

**Key Reminders:**
- Update Discord Interactions Endpoint URL FIRST
- Monitor CloudWatch logs during ALL tests
- SES is in production mode (no email verification needed)
- Bot role must be ABOVE verified role in hierarchy
- Document all issues with screenshots and logs

**Ready to Start Testing?**

1. Complete [Pre-Testing Setup](#pre-testing-setup)
2. Start [CloudWatch monitoring](#monitoring-and-logs)
3. Run [Priority 1 tests](#priority-1-critical-functionality-must-pass)
4. Document results using [test template](#test-results-template)
5. Review [success criteria](#success-criteria)

Good luck with your testing! The bot is ready for validation.

---

**Document Version:** 1.0  
**Last Updated:** December 9, 2025  
**Deployment:** Fresh deployment complete on December 8, 2025  
**Status:** Ready for testing
