# SES Compliance Deployment Checklist

Use this checklist to ensure all SES compliance features are properly deployed.

**Project:** Discord Email Verification Bot
**Date:** 2024-12-08
**Status:** Ready for Deployment

---

## Pre-Deployment

### Code Review
- [x] Suppression list module created (`lambda/ses_suppression_list.py`)
- [x] Notification handler created (`lambda/ses_notification_handler.py`)
- [x] Email service updated with suppression check (`lambda/ses_email.py`)
- [x] CloudWatch metrics integrated
- [x] All Python files pass syntax check
- [x] Code follows existing patterns

### Scripts
- [x] Deployment script created (`scripts/deploy-ses-compliance.sh`)
- [x] Table creation script created (`scripts/create-suppression-table.sh`)
- [x] Alarm creation script created (`scripts/create-ses-alarms.sh`)
- [x] DNS verification script created (`scripts/verify-dns.sh`)
- [x] All scripts are executable

### Documentation
- [x] Setup guide completed (`docs/SES_SETUP_GUIDE.md`)
- [x] Operations runbook completed (`docs/SES_OPERATIONS_RUNBOOK.md`)
- [x] Testing guide completed (`docs/SES_TESTING_GUIDE.md`)
- [x] IAM policy documented (`docs/iam-policy-ses-compliance.json`)
- [x] Implementation summary created
- [x] Quick reference created

---

## Deployment Steps

### 1. DNS Configuration (REQUIRED - Do First)

**Domain:** thedailydecrypt.com

- [ ] **Step 1.1:** Verify domain in AWS SES
  ```bash
  aws ses verify-domain-identity --domain thedailydecrypt.com
  # Copy verification token from output
  ```

- [ ] **Step 1.2:** Add DNS TXT record for SES verification
  ```
  Type: TXT
  Name: _amazonses.thedailydecrypt.com
  Value: <verification-token-from-step-1.1>
  TTL: 1800
  ```

- [ ] **Step 1.3:** Enable DKIM and get tokens
  ```bash
  aws ses set-identity-dkim-enabled --identity thedailydecrypt.com --dkim-enabled
  aws ses get-identity-dkim-attributes --identities thedailydecrypt.com
  # Copy 3 DKIM tokens from output
  ```

- [ ] **Step 1.4:** Add 3 DKIM CNAME records
  ```
  Type: CNAME
  Name: token1._domainkey.thedailydecrypt.com
  Value: token1.dkim.amazonses.com
  TTL: 1800

  (Repeat for token2 and token3)
  ```

- [ ] **Step 1.5:** Add SPF TXT record
  ```
  Type: TXT
  Name: thedailydecrypt.com
  Value: v=spf1 include:amazonses.com ~all
  TTL: 1800
  ```

- [ ] **Step 1.6:** Add DMARC TXT record
  ```
  Type: TXT
  Name: _dmarc.thedailydecrypt.com
  Value: v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@thedailydecrypt.com; fo=1; pct=100
  TTL: 1800
  ```

- [ ] **Step 1.7:** Verify DNS propagation (wait 1-2 hours)
  ```bash
  ./scripts/verify-dns.sh thedailydecrypt.com
  ```

- [ ] **Step 1.8:** Confirm domain verified in AWS
  ```bash
  aws ses get-identity-verification-attributes --identities thedailydecrypt.com
  # VerificationStatus should be "Success"
  ```

**Estimated Time:** 2-24 hours (DNS propagation)

---

### 2. Deploy SES Compliance Infrastructure

- [ ] **Step 2.1:** Run deployment script
  ```bash
  cd /home/offsetkeyz/claude_coding_projects/au-discord-bot
  ./scripts/deploy-ses-compliance.sh
  ```

- [ ] **Step 2.2:** Verify DynamoDB table created
  ```bash
  aws dynamodb describe-table --table-name ses-email-suppression-list
  ```

- [ ] **Step 2.3:** Verify SNS topic created
  ```bash
  aws sns list-topics | grep ses-bounce-complaint
  ```

- [ ] **Step 2.4:** Verify notification handler Lambda deployed
  ```bash
  aws lambda get-function --function-name ses-notification-handler
  ```

- [ ] **Step 2.5:** Verify SNS subscription active
  ```bash
  aws sns list-subscriptions | grep ses-notification-handler
  ```

- [ ] **Step 2.6:** Verify CloudWatch alarms created
  ```bash
  aws cloudwatch describe-alarms --alarm-name-prefix ses-
  # Should show 6 alarms
  ```

**Estimated Time:** 15-30 minutes

---

### 3. Update Main Lambda Function

- [ ] **Step 3.1:** Get current Lambda configuration
  ```bash
  aws lambda get-function-configuration --function-name discord-verification-handler \
      --query 'Environment.Variables' --output json > lambda-env-backup.json
  ```

- [ ] **Step 3.2:** Add suppression list environment variable
  ```bash
  # Manually merge or use AWS Console to add:
  SUPPRESSION_LIST_TABLE=ses-email-suppression-list
  ```

- [ ] **Step 3.3:** Update Lambda IAM role with DynamoDB permissions
  ```bash
  # Get role name
  ROLE_NAME=$(aws lambda get-function --function-name discord-verification-handler \
      --query 'Configuration.Role' --output text | cut -d'/' -f2)

  # Add policy (using docs/iam-policy-ses-compliance.json)
  aws iam put-role-policy \
      --role-name $ROLE_NAME \
      --policy-name SESComplianceAccess \
      --policy-document file://docs/iam-policy-ses-compliance.json
  ```

- [ ] **Step 3.4:** Redeploy main Lambda with updated code
  ```bash
  # Package lambda directory
  cd lambda
  zip -r ../lambda-deployment.zip .
  cd ..

  # Update function
  aws lambda update-function-code \
      --function-name discord-verification-handler \
      --zip-file fileb://lambda-deployment.zip
  ```

- [ ] **Step 3.5:** Verify Lambda updated
  ```bash
  aws lambda get-function-configuration --function-name discord-verification-handler \
      --query 'Environment.Variables.SUPPRESSION_LIST_TABLE'
  # Should return: ses-email-suppression-list
  ```

**Estimated Time:** 10-15 minutes

---

### 4. Testing

#### Unit Tests
- [ ] **Step 4.1:** Run suppression list tests
  ```bash
  pytest tests/test_ses_suppression.py -v
  ```

- [ ] **Step 4.2:** Run email integration tests
  ```bash
  pytest tests/test_ses_email_integration.py -v
  ```

#### AWS Simulator Tests
- [ ] **Step 4.3:** Test bounce handling
  ```bash
  aws ses send-email \
      --from verificationcode.noreply@thedailydecrypt.com \
      --destination ToAddresses=bounce@simulator.amazonses.com \
      --message "Subject={Data=Bounce Test},Body={Text={Data=Testing bounce handling}}"

  # Wait 60 seconds, then check:
  aws dynamodb get-item \
      --table-name ses-email-suppression-list \
      --key '{"email": {"S": "bounce@simulator.amazonses.com"}, "reason": {"S": "bounce"}}'
  # Should return Item with bounce details
  ```

- [ ] **Step 4.4:** Test complaint handling
  ```bash
  aws ses send-email \
      --from verificationcode.noreply@thedailydecrypt.com \
      --destination ToAddresses=complaint@simulator.amazonses.com \
      --message "Subject={Data=Complaint Test},Body={Text={Data=Testing complaint handling}}"

  # Wait 60 seconds, then check:
  aws dynamodb get-item \
      --table-name ses-email-suppression-list \
      --key '{"email": {"S": "complaint@simulator.amazonses.com"}, "reason": {"S": "complaint"}}'
  # Should return Item with complaint details
  ```

- [ ] **Step 4.5:** Test suppression list blocks emails
  ```bash
  # Try to send to previously bounced address - should be blocked
  # Check Lambda logs for "Email ... is on suppression list - not sending"
  aws logs tail /aws/lambda/discord-verification-handler --follow
  ```

#### CloudWatch Validation
- [ ] **Step 4.6:** Verify metrics are published
  ```bash
  aws cloudwatch list-metrics --namespace DiscordBot/SES
  # Should show: EmailsSent, EmailsFailed, EmailsSuppressed
  ```

- [ ] **Step 4.7:** Check alarm status
  ```bash
  aws cloudwatch describe-alarms --alarm-name-prefix ses- \
      --query 'MetricAlarms[*].[AlarmName,StateValue]' --output table
  # All should be "OK" or "INSUFFICIENT_DATA"
  ```

#### End-to-End Test
- [ ] **Step 4.8:** Send real verification email via Discord bot
- [ ] **Step 4.9:** Verify email received and formatted correctly
- [ ] **Step 4.10:** Check CloudWatch metrics incremented

**Estimated Time:** 30-45 minutes

---

### 5. Monitoring Setup

- [ ] **Step 5.1:** Create SNS topic for alerts
  ```bash
  aws sns create-topic --name ses-alerts
  ALERT_TOPIC=$(aws sns list-topics --query "Topics[?contains(TopicArn, 'ses-alerts')].TopicArn" --output text)
  ```

- [ ] **Step 5.2:** Subscribe email to alerts topic
  ```bash
  aws sns subscribe \
      --topic-arn $ALERT_TOPIC \
      --protocol email \
      --notification-endpoint your-team-email@example.com
  # Check email and confirm subscription
  ```

- [ ] **Step 5.3:** Update alarms to send to SNS topic
  ```bash
  # Update each critical alarm
  aws cloudwatch put-metric-alarm \
      --alarm-name ses-high-bounce-rate-CRITICAL \
      --alarm-actions $ALERT_TOPIC \
      ... (other parameters)
  ```

- [ ] **Step 5.4:** Create CloudWatch dashboard (optional)
  ```bash
  # Create dashboard in AWS Console or via CLI
  # Add widgets for bounce rate, complaint rate, emails sent
  ```

- [ ] **Step 5.5:** Set up daily monitoring schedule
  - Add to team calendar: Daily SES health check (5 min)
  - Add to team calendar: Weekly SES review (30 min)

**Estimated Time:** 20-30 minutes

---

### 6. Production Access (if in Sandbox Mode)

- [ ] **Step 6.1:** Check current SES status
  ```bash
  aws ses get-send-quota
  # If Max24HourSend is 200, you're in sandbox mode
  ```

- [ ] **Step 6.2:** Request production access
  - Go to: https://console.aws.amazon.com/ses/home?region=us-east-1#/account
  - Click "Request Production Access"
  - Use template from `docs/SES_SETUP_GUIDE.md`

- [ ] **Step 6.3:** Wait for AWS approval (24-48 hours)

- [ ] **Step 6.4:** Verify production access granted
  ```bash
  aws ses get-send-quota
  # Max24HourSend should be 50,000+
  ```

**Estimated Time:** 24-48 hours (AWS review time)

---

## Post-Deployment

### Verification
- [ ] All CloudWatch alarms in "OK" state
- [ ] Test email successfully sent and received
- [ ] Bounce handling verified with simulator
- [ ] Complaint handling verified with simulator
- [ ] Suppression list prevents re-sends
- [ ] CloudWatch metrics appearing correctly
- [ ] SNS alerts configured and tested
- [ ] Team has access to monitoring dashboards

### Documentation
- [ ] Team trained on operations runbook
- [ ] Escalation procedures documented
- [ ] Emergency contacts updated
- [ ] Deployment documented in project wiki

### Ongoing Operations
- [ ] Daily health check scheduled
- [ ] Weekly review meeting scheduled
- [ ] Incident response plan reviewed
- [ ] Backup procedures documented

---

## Rollback Plan

If issues occur during deployment:

### Rollback Lambda Changes
```bash
# Restore previous Lambda code
aws lambda update-function-code \
    --function-name discord-verification-handler \
    --zip-file fileb://lambda-deployment-backup.zip

# Restore previous environment
aws lambda update-function-configuration \
    --function-name discord-verification-handler \
    --environment file://lambda-env-backup.json
```

### Remove New Resources (if needed)
```bash
# Delete notification handler
aws lambda delete-function --function-name ses-notification-handler

# Delete SNS topic
aws sns delete-topic --topic-arn <SNS_TOPIC_ARN>

# Delete DynamoDB table (careful!)
aws dynamodb delete-table --table-name ses-email-suppression-list

# Delete CloudWatch alarms
aws cloudwatch delete-alarms --alarm-names ses-high-bounce-rate-CRITICAL ses-high-complaint-rate-CRITICAL ...
```

---

## Success Criteria

Deployment is successful when:

1. All DNS records verified with green checkmarks
2. All AWS resources created without errors
3. Bounce/complaint simulator tests pass
4. CloudWatch metrics publishing correctly
5. Alarms configured and monitoring
6. Team familiar with operations procedures
7. Production access granted (if applicable)

---

## Support

- **Setup Issues:** Review `docs/SES_SETUP_GUIDE.md`
- **Testing Issues:** Review `docs/SES_TESTING_GUIDE.md`
- **Operational Issues:** Review `docs/SES_OPERATIONS_RUNBOOK.md`
- **AWS Support:** Create case via AWS Console

---

## Sign-Off

- [ ] Backend Developer: Implementation complete
- [ ] DevOps Engineer: Infrastructure deployed
- [ ] QA Engineer: Testing passed
- [ ] Project Manager: Approved for production

---

**Deployment Date:** _____________
**Deployed By:** _____________
**Production Ready:** [ ] Yes [ ] No
**Notes:**

---

**Last Updated:** 2024-12-08
**Document Version:** 1.0
