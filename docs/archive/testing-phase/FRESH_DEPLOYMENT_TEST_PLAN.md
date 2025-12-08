# Fresh Deployment Testing Plan

## Overview

This plan guides you through testing the Discord Email Verification Bot from a completely fresh deployment. This validates that the entire setup process works correctly and is reproducible.

---

## Why Test from Scratch?

1. **Validates Setup Script** - Ensures `setup-aws.sh` works end-to-end
2. **Clean State** - No leftover test data that could mask issues
3. **Real User Experience** - Tests what admins will go through
4. **Proves Reproducibility** - Ensures deployment is repeatable
5. **Post-Merge Validation** - Tests recent SES compliance and security changes

---

## Total Time Estimate

- **Cleanup & Backup:** 10 minutes
- **Fresh Deployment:** 15-20 minutes
- **Discord Testing:** 30-60 minutes
- **Total:** ~1-1.5 hours

---

## Phase 1: Backup Current State (10 minutes)

### Step 1.1: Export Current Guild Configurations

```bash
# Export guild configs (if any exist)
aws dynamodb scan \
  --table-name discord-guild-configs \
  --region us-east-1 \
  --output json > backup-guild-configs.json

# Export verification records (optional - for historical data)
aws dynamodb scan \
  --table-name discord-verification-records \
  --region us-east-1 \
  --output json > backup-verification-records.json

echo "Backups saved to backup-*.json"
```

### Step 1.2: Save Current Configuration

```bash
# Save current SSM parameters
aws ssm get-parameters \
  --names "/discord-bot/token" \
          "/discord-bot/public-key" \
          "/discord-bot/app-id" \
  --with-decryption \
  --region us-east-1 \
  --output json > backup-ssm-params.json

echo "SSM parameters backed up"
```

### Step 1.3: Note Current Lambda URL

```bash
# Get current Lambda Function URL
aws lambda get-function-url-config \
  --function-name discord-verification-handler \
  --region us-east-1 2>/dev/null || echo "No Function URL configured"
```

**Save this URL** - you'll need to update it in Discord Developer Portal.

---

## Phase 2: Clean Up Resources (5 minutes)

### Step 2.1: Run Cleanup Script

```bash
# Make sure cleanup script is executable
chmod +x cleanup-aws.sh

# Run cleanup (will prompt for confirmation)
./cleanup-aws.sh
```

When prompted, type `yes` to confirm deletion.

### Step 2.2: Verify Cleanup

```bash
# Check Lambda function deleted
aws lambda get-function --function-name discord-verification-handler --region us-east-1 2>&1 | grep -q "ResourceNotFoundException" && echo "✓ Lambda deleted" || echo "✗ Lambda still exists"

# Check DynamoDB tables deleted
aws dynamodb describe-table --table-name discord-verification-sessions --region us-east-1 2>&1 | grep -q "ResourceNotFoundException" && echo "✓ Sessions table deleted" || echo "✗ Sessions table still exists"

# Check IAM role deleted
aws iam get-role --role-name discord-verification-lambda-role 2>&1 | grep -q "NoSuchEntity" && echo "✓ IAM role deleted" || echo "✗ IAM role still exists"

echo "Cleanup verification complete"
```

---

## Phase 3: Fresh Deployment (15-20 minutes)

### Step 3.1: Prepare Configuration

Before running setup, gather this information:

- [ ] Discord Bot Token (from Discord Developer Portal)
- [ ] Discord Public Key (from Discord Developer Portal)
- [ ] Discord Application ID (from Discord Developer Portal)
- [ ] Sender Email (e.g., `verificationcode.noreply@thedailydecrypt.com`)

### Step 3.2: Run Setup Script

```bash
# Run setup script
./setup-aws.sh
```

**The script will prompt for:**
1. Discord Bot Token
2. Discord Public Key
3. Discord Application ID
4. Sender Email Address

**What the script does:**
1. Creates 3 DynamoDB tables
2. Creates IAM role with permissions
3. Stores secrets in SSM Parameter Store
4. Packages and deploys Lambda function
5. Creates Lambda layer for dependencies
6. Configures Lambda environment variables
7. Sets up API Gateway (optional)

### Step 3.3: Verify Deployment

```bash
# Check Lambda function exists
aws lambda get-function \
  --function-name discord-verification-handler \
  --region us-east-1 \
  --query 'Configuration.FunctionArn' \
  --output text

# Check DynamoDB tables
aws dynamodb list-tables --region us-east-1 | grep discord-verification

# Check IAM role
aws iam get-role \
  --role-name discord-verification-lambda-role \
  --query 'Role.Arn' \
  --output text

# Get Lambda Function URL
FUNCTION_URL=$(aws lambda get-function-url-config \
  --function-name discord-verification-handler \
  --region us-east-1 \
  --query 'FunctionUrl' \
  --output text 2>/dev/null)

echo "Lambda Function URL: $FUNCTION_URL"
```

**Save the Function URL - you need to update Discord with this!**

---

## Phase 4: Update Discord Configuration (5 minutes)

### Step 4.1: Update Interaction Endpoint URL

1. Go to **Discord Developer Portal**: https://discord.com/developers/applications
2. Select your application
3. Go to **General Information**
4. Update **Interactions Endpoint URL** with your new Lambda Function URL
5. Click **Save Changes**

### Step 4.2: Verify Discord Connection

Discord will automatically send a PING to verify the endpoint. If the verification fails:

```bash
# Check Lambda logs for the PING interaction
aws logs tail /aws/lambda/discord-verification-handler \
  --since 5m \
  --region us-east-1 \
  --format short

# Look for: type=1 (PING) and verify response
```

### Step 4.3: Re-register Slash Commands (if needed)

If the `/setup-email-verification` command doesn't appear:

```bash
# Check if commands are registered
curl -X GET \
  -H "Authorization: Bot YOUR_BOT_TOKEN" \
  "https://discord.com/api/v10/applications/YOUR_APP_ID/commands"

# If empty, you may need to re-register commands
# (This is typically done via Discord Developer Portal or a separate registration script)
```

---

## Phase 5: Discord Server Testing (30-60 minutes)

Now follow your existing testing documentation:

### Quick Test (30 minutes)
Follow: `TESTING_QUICK_START.md`

**Essential Tests:**
1. ✅ Admin Setup Flow
2. ✅ Happy Path Verification
3. ✅ Invalid Email Domain
4. ✅ Wrong Code Attempts
5. ✅ Rate Limiting
6. ✅ Multi-User Testing

### Comprehensive Test (60 minutes)
Follow: `DISCORD_SERVER_TESTING_PLAN.md`

**All Priority 1 Scenarios:**
1. ✅ Admin setup flow
2. ✅ Happy path verification
3. ✅ Invalid domain rejection
4. ✅ Email delivery validation
5. ✅ Logging and monitoring

---

## Phase 6: Monitor During Testing

### Terminal 1: Watch Lambda Logs

```bash
aws logs tail /aws/lambda/discord-verification-handler \
  --follow \
  --region us-east-1 \
  --format short
```

### Terminal 2: Monitor SES Sending

```bash
# Check SES sending statistics
watch -n 30 'aws ses get-send-statistics --region us-east-1 | jq ".SendDataPoints | sort_by(.Timestamp) | .[-5:]"'
```

### Terminal 3: Monitor DynamoDB

```bash
# Check session count
watch -n 10 'aws dynamodb scan --table-name discord-verification-sessions --select COUNT --region us-east-1 --query "Count"'
```

---

## Success Criteria

### Setup Script Must:
- [ ] Complete without errors
- [ ] Create all 3 DynamoDB tables
- [ ] Create IAM role with correct permissions
- [ ] Deploy Lambda function successfully
- [ ] Store SSM parameters securely
- [ ] Provide Function URL at end

### Discord Integration Must:
- [ ] Accept PING from Discord (endpoint verification)
- [ ] Respond to button clicks < 3 seconds
- [ ] Send verification emails < 30 seconds
- [ ] Verify codes correctly
- [ ] Assign roles successfully
- [ ] Handle errors gracefully

### Security Must:
- [ ] No PII in CloudWatch logs
- [ ] Bot token stored in SSM (not env vars)
- [ ] Discord signature verification working
- [ ] Invalid requests return 401
- [ ] Rate limiting functional

---

## Troubleshooting

### Setup Script Fails

**Error: "Role already exists"**
```bash
# Delete old role manually
aws iam delete-role-policy --role-name discord-verification-lambda-role --policy-name discord-verification-policy
aws iam delete-role --role-name discord-verification-lambda-role
```

**Error: "Table already exists"**
```bash
# Delete old tables
aws dynamodb delete-table --table-name discord-verification-sessions --region us-east-1
aws dynamodb delete-table --table-name discord-verification-records --region us-east-1
aws dynamodb delete-table --table-name discord-guild-configs --region us-east-1
# Wait 30 seconds, then re-run setup
```

### Discord Endpoint Verification Fails

**Check Lambda logs:**
```bash
aws logs tail /aws/lambda/discord-verification-handler --since 10m --region us-east-1
```

**Common causes:**
- Wrong public key in SSM
- Lambda timeout too short
- Lambda doesn't have internet access
- Function URL not accessible

### Emails Not Sending

**Check SES status:**
```bash
# Verify domain is verified
aws sesv2 get-email-identity --email-identity thedailydecrypt.com --region us-east-1 | grep VerifiedForSendingStatus

# Check quota
aws sesv2 get-account --region us-east-1 | jq '.SendQuota'
```

**Common causes:**
- Domain not verified in SES
- SES quota exceeded
- Lambda doesn't have SES permissions
- Wrong FROM_EMAIL in environment variables

---

## Rollback Plan

If fresh deployment fails and you need to rollback:

### Option 1: Re-run Cleanup and Try Again

```bash
./cleanup-aws.sh
# Fix any issues
./setup-aws.sh
```

### Option 2: Restore from Backup (if needed)

```bash
# Restore guild configs
aws dynamodb batch-write-item --request-items file://backup-guild-configs.json --region us-east-1

# Restore SSM parameters
# (Extract from backup-ssm-params.json and put manually)
```

---

## Post-Testing Checklist

After successful testing:

- [ ] Document any issues found
- [ ] Update setup script if bugs discovered
- [ ] Verify all test scenarios passed
- [ ] Check CloudWatch logs for errors
- [ ] Confirm no PII in logs
- [ ] Validate performance metrics
- [ ] Update documentation if needed
- [ ] Plan production rollout

---

## Expected Results

### Setup Script Output

```
==> Checking prerequisites...
[INFO] All prerequisites met!
[INFO] AWS Account: 123456789012
[INFO] AWS Region: us-east-1

==> Creating DynamoDB tables...
[INFO] Created table: discord-verification-sessions
[INFO] Created table: discord-verification-records
[INFO] Created table: discord-guild-configs

==> Creating IAM role...
[INFO] Created role: discord-verification-lambda-role

==> Storing secrets in SSM...
[INFO] Stored bot token in SSM
[INFO] Stored public key in SSM
[INFO] Stored app ID in SSM

==> Deploying Lambda function...
[INFO] Packaged Lambda function
[INFO] Created Lambda function
[INFO] Function URL: https://xxxxxxxxxx.lambda-url.us-east-1.on.aws/

==> Deployment complete!
```

### Discord Test Results

All these should work:
- ✅ `/setup-email-verification` command accessible to admins
- ✅ Setup wizard completes successfully
- ✅ Verification button appears in configured channel
- ✅ Email modal accepts valid .edu emails
- ✅ Verification emails deliver within 30 seconds
- ✅ Code verification works correctly
- ✅ Role assignment successful
- ✅ Already-verified users blocked appropriately
- ✅ Rate limiting enforces 60-second cooldown
- ✅ Multiple users can verify concurrently

---

## Next Steps After Successful Testing

1. **Production Deployment**
   - Update production Discord server
   - Monitor closely for first week
   - Set up CloudWatch alarms

2. **Documentation**
   - Document any changes made
   - Update setup instructions
   - Create admin guide

3. **Monitoring**
   - Set up CloudWatch dashboards
   - Configure alarms for errors
   - Monitor SES reputation

4. **Backup Strategy**
   - Schedule DynamoDB backups
   - Document recovery procedures
   - Test restore process

---

## Summary

This fresh deployment test validates:
- ✅ Setup script works end-to-end
- ✅ All AWS resources created correctly
- ✅ Discord integration functions properly
- ✅ Security measures in place
- ✅ Performance meets requirements
- ✅ Deployment is reproducible

**Estimated Total Time:** 1-1.5 hours

**Result:** Confidence in production deployment!
