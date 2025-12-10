# SES Sandbox Testing Guide
## Working with AWS SES Sandbox Mode

**Purpose:** Understand and work effectively with SES sandbox constraints during testing
**Last Updated:** 2025-12-08

---

## What is SES Sandbox Mode?

AWS Simple Email Service (SES) starts all new accounts in "sandbox mode" - a restricted environment designed to prevent spam and abuse while you test your email sending.

### Sandbox Restrictions

| Restriction | Sandbox Limit | Production Limit |
|-------------|---------------|------------------|
| Recipients | Only verified emails | Any email address |
| Daily sending quota | 200 emails/day | Starts at 50,000+/day |
| Sending rate | 1 email/second | Up to 100+/second |
| Bounce/complaint tracking | Limited | Full tracking |

---

## Key Implications for Testing

### 1. Email Verification Requirement (CRITICAL)

**The Rule:** You can ONLY send emails to addresses you've pre-verified in SES.

**What This Means:**
- Every tester's email MUST be verified before they test
- Can't test with random @university.edu emails
- Can't invite external users without verifying their emails first
- Perfect for controlled testing, limiting for broader testing

**Example Scenario:**
```
BAD (Will Fail):
1. User clicks "Start Verification"
2. Enters: randomstudent@auburn.edu
3. Bot tries to send email
4. SES REJECTS: "Email address is not verified"
5. User sees: "Failed to send verification email..."

GOOD (Will Work):
1. Admin pre-verifies: randomstudent@auburn.edu in SES
2. User clicks "Start Verification"
3. Enters: randomstudent@auburn.edu
4. SES ACCEPTS and sends email
5. User receives code successfully
```

---

## How to Verify Email Addresses

### Method 1: AWS CLI (Recommended)

```bash
# Verify a single email
aws ses verify-email-identity \
  --email-identity student@auburn.edu \
  --region us-east-1

# Verify multiple emails
for email in student1@auburn.edu student2@auburn.edu admin@auburn.edu; do
  aws ses verify-email-identity --email-identity $email --region us-east-1
done

# Check verification status
aws ses get-identity-verification-attributes \
  --identities student@auburn.edu \
  --region us-east-1
```

**What Happens:**
1. AWS sends verification email to the address
2. Recipient clicks verification link in email
3. Status changes from "Pending" to "Success"
4. Address is now usable (usually within 5 minutes)

### Method 2: AWS Console (GUI)

1. Go to: `https://console.aws.amazon.com/ses`
2. Click "Verified identities" in left menu
3. Click "Create identity"
4. Select "Email address"
5. Enter the email address
6. Click "Create identity"
7. Check the email inbox for verification email
8. Click the verification link

---

## Verification Email Details

### What the Verification Email Looks Like

```
From: no-reply@ses.amazonaws.com
Subject: Amazon SES Address Verification Request in region US East (N. Virginia)

Hello,

We received a request to use this email address with Amazon Simple Email Service...

Please click the following link to confirm that you are the owner of student@auburn.edu:

https://email.us-east-1.amazonaws.com/verify?token=LONG_TOKEN_HERE

If you did not request this verification, you can safely ignore this message.

Amazon Web Services
```

### Common Verification Issues

**Issue:** Verification email not received
**Solutions:**
- Check spam/junk folder
- Verify correct region (us-east-1)
- Some email providers block AWS verification emails - try different email
- University email systems may have strict filters - contact IT

**Issue:** Verification link expired
**Solutions:**
- Request new verification (deletes old, sends new)
- Links expire after 24 hours

**Issue:** "Already verified" but shows as Pending
**Solutions:**
- Wait 5-10 minutes for propagation
- Check correct region
- Delete and re-verify

---

## Checking Verification Status

### Quick Status Check

```bash
# Check single email
aws ses get-identity-verification-attributes \
  --identities student@auburn.edu \
  --region us-east-1

# Expected output (Success):
{
  "VerificationAttributes": {
    "student@auburn.edu": {
      "VerificationStatus": "Success"
    }
  }
}

# Expected output (Pending):
{
  "VerificationAttributes": {
    "student@auburn.edu": {
      "VerificationStatus": "Pending"
    }
  }
}
```

### List All Verified Emails

```bash
# List all verified identities
aws ses list-verified-email-addresses --region us-east-1

# Expected output:
{
  "VerifiedEmailAddresses": [
    "noreply@yourdomain.com",
    "student1@auburn.edu",
    "student2@auburn.edu"
  ]
}
```

---

## Testing Strategy in Sandbox Mode

### Recommended Test Email Setup

**Minimum Setup (1 tester):**
```bash
# Sender email (FROM address)
aws ses verify-email-identity --email-identity noreply@yourdomain.com --region us-east-1

# Your test email
aws ses verify-email-identity --email-identity yourname@auburn.edu --region us-east-1
```

**Multi-User Testing Setup (2-3 testers):**
```bash
# Sender
aws ses verify-email-identity --email-identity noreply@yourdomain.com --region us-east-1

# Tester 1
aws ses verify-email-identity --email-identity tester1@auburn.edu --region us-east-1

# Tester 2
aws ses verify-email-identity --email-identity tester2@auburn.edu --region us-east-1

# Tester 3 (mobile testing)
aws ses verify-email-identity --email-identity tester3@auburn.edu --region us-east-1
```

**Extended Testing Setup (5-10 testers):**
Create a list file and batch verify:

```bash
# Create emails.txt
cat > emails.txt << EOF
tester1@auburn.edu
tester2@auburn.edu
tester3@auburn.edu
tester4@auburn.edu
tester5@auburn.edu
EOF

# Batch verify
while read email; do
  aws ses verify-email-identity --email-identity $email --region us-east-1
  echo "Verification email sent to: $email"
done < emails.txt
```

---

## Monitoring SES Usage in Sandbox

### Check Daily Quota

```bash
# Check current quota usage
aws ses get-send-quota --region us-east-1

# Expected output:
{
  "Max24HourSend": 200.0,         # Maximum emails per 24 hours
  "MaxSendRate": 1.0,              # Maximum emails per second
  "SentLast24Hours": 15.0          # Emails sent in last 24 hours
}
```

**Important:** Track `SentLast24Hours` to avoid hitting the 200/day limit during testing.

### Monitor Sending Statistics

```bash
# Get detailed sending statistics
aws ses get-send-statistics --region us-east-1

# Sample output:
{
  "SendDataPoints": [
    {
      "Timestamp": "2025-12-08T15:00:00Z",
      "DeliveryAttempts": 5,
      "Bounces": 0,
      "Complaints": 0,
      "Rejects": 2              # Unverified email attempts
    }
  ]
}
```

**Watch for:**
- `Rejects`: Indicates attempts to send to unverified emails
- `Bounces`: Should be 0 (bad if > 0)
- `Complaints`: Should be 0 (very bad if > 0)

---

## Testing Unverified Email Rejection

It's useful to test that the bot handles SES rejections gracefully:

### Test Case: Unverified Email

**Purpose:** Verify error handling when user enters unverified email

**Steps:**
1. Start verification in Discord
2. Enter an unverified email (e.g., `random@auburn.edu`)
3. Submit

**Expected Bot Behavior:**
```
User sees in Discord:
"Failed to send verification email. This might be because:
• The email address is invalid
• Our email service is in sandbox mode and can't send to unverified addresses

Please contact a server administrator."
```

**Expected CloudWatch Logs:**
```
[ERROR] SES MessageRejected: Email address is not verified.
The following identities failed the check in region US-EAST-1:
random@auburn.edu
```

**Success Criteria:**
- Error handled gracefully
- User-friendly error message
- Session cleaned up (deleted from DynamoDB)
- Error logged to CloudWatch

---

## Moving from Sandbox to Production

### When to Move to Production

**Consider production access when:**
- Testing is complete and successful
- Ready to allow any .edu email (not just verified)
- Expect > 200 verifications per day
- Need faster sending rate (> 1/second)
- Launching to multiple Discord servers

**Production benefits:**
- Send to ANY email address (no verification required)
- Higher daily quota (starts at 50,000/day)
- Higher sending rate (up to 100/second)
- Better deliverability metrics

### How to Request Production Access

**Step 1: Prepare Your Request**

You'll need to explain:
- What you're sending (verification codes for Discord bot)
- Who you're sending to (university students)
- How you handle bounces/complaints
- Expected sending volume

**Step 2: Submit Request**

**Via AWS Console:**
1. Go to: `https://console.aws.amazon.com/ses`
2. Click "Account dashboard" in left menu
3. Under "Sending limits", click "Request production access"
4. Fill out the form:

```
Use Case Description (Example):
"We operate a Discord bot that sends email verification codes to
university students (.edu domains). Users voluntarily enter their
email to receive a one-time verification code. We implement:
- Rate limiting (1 verification per user per hour)
- Email validation (only .edu domains)
- Bounce/complaint handling
- User opt-out on first email

Estimated volume: 50-100 emails/day during testing, up to 500/day
at full launch. No marketing emails - only transactional verification."

Email Types: Transactional
Bounce/Complaint Handling: "We monitor bounces and complaints via
CloudWatch and will disable sending to any addresses that bounce
or complain."
```

**Via AWS CLI:**
```bash
aws sesv2 put-account-details \
  --production-access-enabled \
  --mail-type TRANSACTIONAL \
  --website-url https://github.com/yourusername/discord-bot \
  --use-case-description "Transactional verification codes for Discord bot users" \
  --region us-east-1
```

**Step 3: Wait for Approval**

- Typical response time: 24-48 hours
- AWS may request additional information
- Check email for AWS Support messages

**Step 4: After Approval**

```bash
# Verify production access enabled
aws sesv2 get-account --region us-east-1

# Expected:
{
  "ProductionAccessEnabled": true,
  "SendingEnabled": true,
  "EnforcementStatus": "HEALTHY"
}
```

**No code changes needed!** Bot continues working as-is, just with no verification requirement.

---

## Sandbox Testing Best Practices

### 1. Pre-Verify Before Inviting Testers

**Bad Process:**
1. Invite testers to Discord
2. Tell them to start verification
3. They fail because emails unverified
4. Frustration and confusion

**Good Process:**
1. Collect tester emails ahead of time
2. Verify all emails in SES
3. Wait for verification confirmations
4. Then invite testers to Discord
5. Testing proceeds smoothly

### 2. Document Verified Emails

Keep a list of verified test emails:

```bash
# Create verified-emails.md
cat > verified-emails.md << EOF
# Verified Test Emails

## Primary Testers
- john.doe@auburn.edu (verified 2025-12-08)
- jane.smith@auburn.edu (verified 2025-12-08)

## Secondary Testers
- bob.test@auburn.edu (verified 2025-12-08)

## Admin Emails
- admin@yourdomain.com (verified 2025-12-08)
EOF
```

### 3. Monitor Quota Usage

**Daily Quota Check Script:**
```bash
#!/bin/bash
# check-ses-quota.sh

QUOTA=$(aws ses get-send-quota --region us-east-1)
SENT=$(echo $QUOTA | jq -r '.SentLast24Hours')
MAX=$(echo $QUOTA | jq -r '.Max24HourSend')
REMAINING=$(echo "$MAX - $SENT" | bc)

echo "SES Quota Status:"
echo "Sent today: $SENT / $MAX"
echo "Remaining: $REMAINING"

if (( $(echo "$REMAINING < 20" | bc -l) )); then
  echo "WARNING: Low quota remaining!"
fi
```

Run before each test session:
```bash
chmod +x check-ses-quota.sh
./check-ses-quota.sh
```

### 4. Test Invalid Email Handling

Always test that unverified emails are handled properly:

**Test Checklist:**
- [ ] Unverified email shows user-friendly error
- [ ] Error is logged to CloudWatch
- [ ] Session is cleaned up
- [ ] User can retry with verified email

### 5. Clean Up Old Verifications

Remove test email verifications you no longer need:

```bash
# Remove a verified email
aws ses delete-identity --identity old-test@auburn.edu --region us-east-1

# CAREFUL: This removes ability to send to this address
# Only do this for emails you no longer need to test with
```

---

## Troubleshooting SES in Sandbox

### Problem: Email Rejected

**Symptoms:**
```
CloudWatch Logs:
[ERROR] MessageRejected: Email address is not verified.
```

**Solution:**
```bash
# Verify the email
aws ses verify-email-identity --email-identity student@auburn.edu --region us-east-1

# Check status
aws ses get-identity-verification-attributes \
  --identities student@auburn.edu \
  --region us-east-1

# Wait for "Success" status
```

---

### Problem: Verification Email Not Arriving

**Solutions:**
1. Check spam folder
2. Verify correct region (us-east-1)
3. Try different email provider
4. Check university email filters
5. Request new verification:
   ```bash
   # Delete old identity
   aws ses delete-identity --identity student@auburn.edu --region us-east-1

   # Create new
   aws ses verify-email-identity --email-identity student@auburn.edu --region us-east-1
   ```

---

### Problem: Hit Daily Quota

**Symptoms:**
```
Error: Daily message quota exceeded
SentLast24Hours: 200.0
```

**Solutions:**
1. **Wait 24 hours** for quota reset
2. **Request production access** (higher quota)
3. **Optimize tests** to use fewer emails:
   - Reuse test sessions
   - Test with fewer users
   - Focus on critical paths

---

### Problem: Wrong Region

**Symptoms:**
- Emails not sending
- Can't see verified identities
- Quota shows 0

**Solution:**
```bash
# Check which region Lambda is in
aws lambda get-function-configuration \
  --function-name discord-verification-handler \
  --query 'Environment.Variables.AWS_REGION'

# Verify emails in the SAME region
aws ses verify-email-identity \
  --email-identity test@auburn.edu \
  --region us-east-1  # Match Lambda region

# Update FROM_EMAIL environment variable if needed
aws lambda update-function-configuration \
  --function-name discord-verification-handler \
  --environment Variables={FROM_EMAIL=verified@domain.com,...}
```

---

## SES Sandbox Cheat Sheet

### Quick Commands

```bash
# Verify email
aws ses verify-email-identity --email-identity EMAIL --region us-east-1

# Check status
aws ses get-identity-verification-attributes --identities EMAIL --region us-east-1

# List all verified
aws ses list-verified-email-addresses --region us-east-1

# Check quota
aws ses get-send-quota --region us-east-1

# Check statistics
aws ses get-send-statistics --region us-east-1

# Delete identity
aws ses delete-identity --identity EMAIL --region us-east-1
```

### Expected Outputs

**Success:**
```json
{
  "VerificationAttributes": {
    "student@auburn.edu": {
      "VerificationStatus": "Success"
    }
  }
}
```

**Pending:**
```json
{
  "VerificationAttributes": {
    "student@auburn.edu": {
      "VerificationStatus": "Pending"
    }
  }
}
```

**Quota:**
```json
{
  "Max24HourSend": 200.0,
  "MaxSendRate": 1.0,
  "SentLast24Hours": 15.0
}
```

---

## Summary

**Key Takeaways:**
1. Sandbox mode requires pre-verified recipient emails
2. Maximum 200 emails per day in sandbox
3. Verify test emails BEFORE testing begins
4. Monitor quota usage during testing
5. Test unverified email rejection for proper error handling
6. Production access removes verification requirement

**Testing Workflow:**
1. Collect test emails from testers
2. Verify all emails in SES
3. Wait for verification confirmations
4. Begin Discord bot testing
5. Monitor quota and statistics
6. Document any rejections or issues

**When to Go Production:**
- After successful sandbox testing
- When ready to scale beyond 200/day
- When need to support any .edu email

---

**For more testing details, see:**
- `TESTING_QUICK_START.md` - Essential tests
- `DISCORD_SERVER_TESTING_PLAN.md` - Comprehensive test scenarios
- `DEPLOYMENT_CHECKLIST.md` - Production deployment steps
