# SES Operations Runbook

Operational procedures for maintaining AWS SES email delivery for the Discord Email Verification Bot.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Weekly Reviews](#weekly-reviews)
3. [Incident Response](#incident-response)
4. [Common Issues](#common-issues)
5. [Escalation Procedures](#escalation-procedures)
6. [Maintenance Tasks](#maintenance-tasks)

---

## Daily Operations

### Morning Health Check (5 minutes)

**Frequency:** Every business day

**Procedure:**

1. **Check CloudWatch Alarms**
   ```bash
   aws cloudwatch describe-alarms \
       --alarm-names ses-high-bounce-rate-CRITICAL ses-high-complaint-rate-CRITICAL \
       --query 'MetricAlarms[*].[AlarmName,StateValue]' \
       --output table
   ```

   **Expected:** All alarms in "OK" state

2. **Review Yesterday's Metrics**
   ```bash
   # Emails sent yesterday
   aws cloudwatch get-metric-statistics \
       --namespace DiscordBot/SES \
       --metric-name EmailsSent \
       --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
       --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
       --period 86400 \
       --statistics Sum

   # Check failures
   aws cloudwatch get-metric-statistics \
       --namespace DiscordBot/SES \
       --metric-name EmailsFailed \
       --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
       --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
       --period 86400 \
       --statistics Sum
   ```

3. **Check SES Reputation**
   ```bash
   aws ses get-account-sending-enabled
   # Should return: {"Enabled": true}
   ```

4. **Review Suppression List Growth**
   ```bash
   aws dynamodb scan \
       --table-name ses-email-suppression-list \
       --select COUNT
   ```

   **Action Required If:**
   - Count increased by >10 in one day → Investigate bounce source
   - Any complaints added → Review email content/sending practices

### Metrics to Monitor

| Metric | Warning Threshold | Critical Threshold | Action |
|--------|------------------|-------------------|---------|
| Bounce Rate | >3% | >5% | Investigate bounce sources |
| Complaint Rate | >0.05% | >0.1% | Review email content |
| Send Failures | >5% | >10% | Check Lambda logs |
| Suppressed Emails | >5/day | >20/day | Validate email sources |

---

## Weekly Reviews

### Monday Weekly Review (30 minutes)

**Frequency:** Every Monday

**Procedure:**

1. **Generate Weekly Report**

   Create a weekly report covering:
   - Total emails sent
   - Bounce rate
   - Complaint rate
   - Failure rate
   - Suppression list additions

2. **Review Bounce Details**
   ```bash
   # Get all bounces from past week
   aws dynamodb scan \
       --table-name ses-email-suppression-list \
       --filter-expression "reason = :reason AND added_at > :timestamp" \
       --expression-attribute-values '{
           ":reason": {"S": "bounce"},
           ":timestamp": {"N": "'$(date -u -d '7 days ago' +%s)'"}
       }'
   ```

   **Analyze:**
   - Common domains with bounces
   - Permanent vs transient bounce ratio
   - Patterns in bounce timing

3. **Review Complaint Details**
   ```bash
   # Get all complaints from past week
   aws dynamodb scan \
       --table-name ses-email-suppression-list \
       --filter-expression "reason = :reason AND added_at > :timestamp" \
       --expression-attribute-values '{
           ":reason": {"S": "complaint"},
           ":timestamp": {"N": "'$(date -u -d '7 days ago' +%s)'"}
       }'
   ```

   **Action Required If:**
   - More than 2 complaints in a week → Review email content
   - Complaints from same domain → Contact domain admin

4. **Check Send Quota Utilization**
   ```bash
   aws ses get-send-quota
   ```

   Calculate daily average usage:
   ```
   Average = SentLast24Hours / (Daily Quota)
   ```

   **Action Required If:**
   - Average >70% → Request quota increase
   - Approaching MaxSendRate → Implement throttling

5. **Review CloudWatch Logs for Errors**
   ```bash
   aws logs filter-log-events \
       --log-group-name /aws/lambda/discord-verification-handler \
       --start-time $(date -u -d '7 days ago' +%s)000 \
       --filter-pattern "ERROR"
   ```

---

## Incident Response

### HIGH BOUNCE RATE ALARM

**Severity:** CRITICAL (risk of AWS suspension)

**Response Time:** Immediate (within 15 minutes)

**Procedure:**

1. **Acknowledge Alert**
   - Note the time and bounce rate from alarm
   - Check if rate is still elevated or was temporary spike

2. **Stop Email Sending (if rate >10%)**
   ```bash
   # Disable main Lambda (emergency only)
   aws lambda update-function-configuration \
       --function-name discord-verification-handler \
       --environment Variables="{EMERGENCY_DISABLE_EMAIL=true,...}"
   ```

3. **Investigate Root Cause**

   Check recent bounces:
   ```bash
   aws dynamodb scan \
       --table-name ses-email-suppression-list \
       --filter-expression "reason = :reason AND added_at > :timestamp" \
       --expression-attribute-values '{
           ":reason": {"S": "bounce"},
           ":timestamp": {"N": "'$(date -u -d '2 hours ago' +%s)'"}
       }'
   ```

   **Common Causes:**
   - Invalid email list imported
   - University changed email format
   - Domain blocking verification emails

4. **Remediation**

   Based on cause:
   - **Invalid emails:** Add domain validation rules
   - **Format change:** Update validation regex
   - **Domain blocking:** Contact domain admin, adjust email content

5. **Resume Email Sending**
   ```bash
   # Re-enable after fixing root cause
   aws lambda update-function-configuration \
       --function-name discord-verification-handler \
       --environment Variables="{...remove EMERGENCY_DISABLE_EMAIL...}"
   ```

6. **Document Incident**
   - Record in incident log
   - Update runbook if new scenario
   - Share learnings with team

### HIGH COMPLAINT RATE ALARM

**Severity:** CRITICAL (risk of AWS suspension)

**Response Time:** Immediate (within 15 minutes)

**Procedure:**

1. **Acknowledge Alert**
   - Note complaint rate from alarm
   - Review recent complaints

2. **Analyze Complaint Source**
   ```bash
   aws dynamodb scan \
       --table-name ses-email-suppression-list \
       --filter-expression "reason = :reason AND added_at > :timestamp" \
       --expression-attribute-values '{
           ":reason": {"S": "complaint"},
           ":timestamp": {"N": "'$(date -u -d '24 hours ago' +%s)'"}
       }'
   ```

3. **Review Email Content**

   Check recent email template changes:
   - Subject line (avoid spam triggers)
   - Body content
   - From address clarity
   - Unsubscribe process (if applicable)

4. **Immediate Actions**
   - Revert to previous email template if recently changed
   - Add clearer sender identification
   - Review Discord bot messaging about emails

5. **Contact AWS Support**

   If complaint rate >0.2%:
   ```bash
   # Open support case
   aws support create-case \
       --subject "SES Complaint Rate Investigation" \
       --service-code "ses" \
       --category-code "other" \
       --communication-body "We are investigating elevated complaint rate..."
   ```

6. **Long-term Prevention**
   - Add email preference management
   - Implement better user education in Discord
   - Review email frequency limits

### ACCOUNT SUSPENDED

**Severity:** CRITICAL (service outage)

**Response Time:** Immediate

**Procedure:**

1. **Confirm Suspension**
   ```bash
   aws ses get-account-sending-enabled
   # Returns: {"Enabled": false}
   ```

2. **Activate Backup Communication**
   - Update Discord bot to show "Email verification temporarily unavailable"
   - Consider alternative verification methods if available

3. **Open AWS Support Case**

   Required information:
   - Account ID
   - Suspension notification details
   - Bounce/complaint rates from past 7 days
   - Corrective actions taken

   ```bash
   aws support create-case \
       --subject "SES Account Suspension - Request Reinstatement" \
       --service-code "ses" \
       --severity-code "urgent" \
       --category-code "other" \
       --communication-body "Our SES account has been suspended..."
   ```

4. **Gather Evidence**
   - Export bounce/complaint data
   - Screenshot CloudWatch metrics
   - Document suppression list implementation
   - Prepare mitigation plan

5. **Implement Permanent Fixes**

   Before reinstatement:
   - Clean all email lists
   - Enhance validation
   - Implement additional rate limiting
   - Add email preview/confirmation step

6. **Request Reinstatement**
   - Provide detailed mitigation plan to AWS
   - Demonstrate implemented safeguards
   - Commit to enhanced monitoring

---

## Common Issues

### Issue: Emails Going to Spam

**Symptoms:**
- Users report not receiving emails
- Emails found in spam folder

**Diagnosis:**
```bash
# Check SPF/DKIM/DMARC
dig TXT yourdomain.com
dig CNAME dkimtoken._domainkey.yourdomain.com
dig TXT _dmarc.yourdomain.com

# Test email with mail-tester.com
```

**Resolution:**
1. Verify all DNS records are correct
2. Check email content for spam triggers
3. Ensure consistent From address
4. Monitor reputation with Google Postmaster Tools
5. Consider warming up new domain gradually

### Issue: Transient Bounces

**Symptoms:**
- Temporary bounce notifications
- Mailbox full errors

**Diagnosis:**
Check bounce subtypes in DynamoDB details field

**Resolution:**
- Don't add transient bounces to permanent suppression
- Implement retry logic with exponential backoff
- Consider user notification for persistent transient failures

### Issue: Suppression List Growing Rapidly

**Symptoms:**
- Daily suppression additions >20
- Increasing number of suppressed send attempts

**Diagnosis:**
```bash
# Analyze suppression reasons
aws dynamodb scan \
    --table-name ses-email-suppression-list \
    --projection-expression "email, reason, bounce_type, details"
```

**Resolution:**
1. Review email source validation
2. Check for stale email lists
3. Implement email verification before adding to system
4. Consider double opt-in for email addresses

### Issue: Send Rate Limiting

**Symptoms:**
- 429 errors from SES
- "Maximum sending rate exceeded" errors

**Diagnosis:**
```bash
aws ses get-send-quota
# Check MaxSendRate vs actual send rate
```

**Resolution:**
1. Implement token bucket rate limiting in Lambda
2. Add send queue with controlled processing rate
3. Request higher sending rate from AWS
4. Distribute sends over time instead of bursts

---

## Escalation Procedures

### Level 1: On-Call Engineer
**Response Time:** 15 minutes
**Handles:**
- CloudWatch alarm investigations
- Routine bounce/complaint reviews
- Performance issues

### Level 2: Senior Engineer
**Response Time:** 1 hour
**Handles:**
- High bounce/complaint rates
- Infrastructure issues
- Configuration changes

### Level 3: AWS Support
**Response Time:** 4 hours (business) / 1 hour (urgent)
**Handles:**
- Account suspensions
- Quota increase requests
- Technical AWS issues

**Contact:**
```bash
aws support create-case \
    --subject "..." \
    --service-code "ses" \
    --severity-code "urgent" \
    --category-code "other"
```

---

## Maintenance Tasks

### Monthly Tasks

1. **Review Suppression List**
   - Export full list
   - Identify patterns
   - Remove test/invalid entries
   - Document trends

2. **Update Documentation**
   - Review runbook accuracy
   - Add new scenarios encountered
   - Update contact information

3. **Security Review**
   - Rotate AWS credentials if applicable
   - Review IAM policies
   - Check for unused permissions

### Quarterly Tasks

1. **Disaster Recovery Test**
   - Test Lambda restore from backup
   - Verify suppression list backup
   - Test failover procedures

2. **Capacity Planning**
   - Review growth trends
   - Project quota needs
   - Plan infrastructure scaling

3. **Cost Optimization**
   - Review SES costs
   - Optimize CloudWatch retention
   - Check for unused resources

---

## Emergency Contacts

| Role | Contact | Availability |
|------|---------|--------------|
| On-Call Engineer | Slack: #oncall | 24/7 |
| Senior Engineer | email@company.com | Business hours |
| AWS Support | AWS Console | 24/7 (Premium) |

## Useful Commands Reference

```bash
# Check SES reputation
aws ses get-account-sending-enabled

# View sending quota
aws ses get-send-quota

# List CloudWatch alarms
aws cloudwatch describe-alarms --alarm-name-prefix ses-

# Check suppression count
aws dynamodb scan --table-name ses-email-suppression-list --select COUNT

# Tail Lambda logs
aws logs tail /aws/lambda/discord-verification-handler --follow

# Get recent bounces
aws dynamodb query \
    --table-name ses-email-suppression-list \
    --index-name reason-index \
    --key-condition-expression "reason = :r" \
    --expression-attribute-values '{":r": {"S": "bounce"}}'

# Remove from suppression (admin action)
aws dynamodb delete-item \
    --table-name ses-email-suppression-list \
    --key '{"email": {"S": "user@example.edu"}, "reason": {"S": "bounce"}}'
```

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2024-12-08 | Initial runbook creation | Backend Developer |

---

**Next Review Date:** 2025-01-08

**Document Owner:** Backend Team

**Last Updated:** 2024-12-08
