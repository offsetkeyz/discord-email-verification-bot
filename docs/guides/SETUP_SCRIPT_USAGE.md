# Setup Script Usage Guide

Quick reference for using the updated `setup-aws.sh` script.

---

## Quick Start (Interactive Mode)

```bash
# Run the script
./setup-aws.sh

# Follow prompts to enter:
# - Discord Bot Token
# - Discord Public Key
# - Discord Application ID
# - From Email Address
```

This is the default and recommended mode for manual deployments.

---

## Automated Mode (CI/CD)

```bash
# Set environment variables
export DISCORD_TOKEN="Bot.YOUR_TOKEN_HERE"
export DISCORD_PUBLIC_KEY="your_64_char_public_key"
export DISCORD_APP_ID="1234567890123456789"
export FROM_EMAIL="noreply@yourdomain.com"

# Run script (no prompts)
./setup-aws.sh
```

Perfect for CI/CD pipelines and automated deployments.

---

## Prerequisites

The script automatically checks for:

1. **AWS CLI** - Must be installed and configured
   ```bash
   aws configure
   # Or set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
   ```

2. **Python 3.11+** - Required for dependencies
   ```bash
   python3 --version
   ```

3. **zip command** - Optional (script uses Python fallback if missing)
   ```bash
   # Ubuntu/Debian
   sudo apt-get install zip

   # macOS
   brew install zip

   # Or skip - script uses Python's zipfile module
   ```

---

## SES Configuration Scenarios

The script intelligently handles different SES scenarios:

### Scenario 1: Domain Verified + Production Mode
```
✓ Domain thedailydecrypt.com is verified for sending
✓ SES account is in production mode
✓ Domain verified + production mode = no individual email verification needed
✓ Skipping individual email verification (not needed)
```
**Result:** No hang, no prompt, continues automatically

### Scenario 2: Domain Verified + Sandbox Mode
```
✓ Domain thedailydecrypt.com is verified for sending
⚠ SES account is in sandbox mode (can only send to verified addresses)
✓ Skipping individual email verification (not needed)
```
**Result:** No hang, shows sandbox warning, continues automatically

### Scenario 3: Unverified Domain
```
⚠ Domain newdomain.com is not verified
⚠ IMPORTANT: Check your email and click the verification link!
Press Enter after you've verified the email address...
```
**Result:** Prompts for email verification (only when actually needed)

### Scenario 4: Non-Interactive Mode (Unverified)
```
⚠ Domain newdomain.com is not verified
⚠ Non-interactive mode: Skipping email verification prompt
⚠ Make sure to verify noreply@newdomain.com before using the bot
```
**Result:** Skips prompt, shows warning, continues

---

## Environment Variables Reference

### Required Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Bot token from Discord Developer Portal | `Bot.MTQ0N...` |
| `DISCORD_PUBLIC_KEY` | Public key from Discord Developer Portal | `fb86b839e3d052f7...` |
| `DISCORD_APP_ID` | Application ID from Discord Developer Portal | `1446567306170863686` |
| `FROM_EMAIL` | Email address to send verification codes from | `noreply@domain.com` |

### AWS Configuration (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_REGION` | AWS region for deployment | From `aws configure` or `us-east-1` |
| `AWS_PROFILE` | AWS CLI profile to use | `default` |

---

## Example: GitHub Actions Workflow

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Deploy to AWS
        env:
          DISCORD_TOKEN: ${{ secrets.DISCORD_TOKEN }}
          DISCORD_PUBLIC_KEY: ${{ secrets.DISCORD_PUBLIC_KEY }}
          DISCORD_APP_ID: ${{ secrets.DISCORD_APP_ID }}
          FROM_EMAIL: ${{ secrets.FROM_EMAIL }}
        run: ./setup-aws.sh
```

---

## Example: GitLab CI Pipeline

```yaml
deploy:
  stage: deploy
  image: python:3.11

  before_script:
    - apt-get update && apt-get install -y awscli
    - aws configure set aws_access_key_id $AWS_ACCESS_KEY_ID
    - aws configure set aws_secret_access_key $AWS_SECRET_ACCESS_KEY
    - aws configure set region us-east-1

  script:
    - export DISCORD_TOKEN="$DISCORD_TOKEN"
    - export DISCORD_PUBLIC_KEY="$DISCORD_PUBLIC_KEY"
    - export DISCORD_APP_ID="$DISCORD_APP_ID"
    - export FROM_EMAIL="$FROM_EMAIL"
    - chmod +x setup-aws.sh
    - ./setup-aws.sh

  only:
    - main
```

---

## Troubleshooting

### Issue: "zip command not found"
**Solution:** Script automatically uses Python's zipfile module. No action needed.
```
⚠ zip command not found. Will use Python's zipfile module as fallback.
```

### Issue: "AWS_REGION reserved variable error"
**Solution:** Fixed in this version. AWS_REGION is no longer set as Lambda environment variable.
```
# Old behavior (broken):
InvalidParameterValueException: Reserved keys used in this request: AWS_REGION

# New behavior (works):
Lambda automatically provides AWS_REGION via runtime
```

### Issue: Script hangs at SES verification
**Solution:** Fixed in this version. Script checks domain verification status first.
```
# If domain verified + production mode:
✓ Skipping individual email verification (not needed)

# If truly needs verification:
⚠ Check your email and click the verification link!
Press Enter after you've verified...
```

### Issue: "AWS credentials not configured"
**Solution:** Run `aws configure` or set AWS environment variables
```bash
# Option 1: Configure AWS CLI
aws configure

# Option 2: Set environment variables
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_REGION="us-east-1"
```

---

## Resources Created

The script creates these AWS resources:

### DynamoDB Tables
- `discord-verification-sessions` (with TTL)
- `discord-verification-records` (with GSI)
- `discord-guild-configs`

### Lambda Resources
- Function: `discord-verification-handler`
- Layer: `discord-bot-dependencies` (PyNaCl, requests)
- Function URL: `https://xxxxx.lambda-url.us-east-1.on.aws/`

### IAM
- Role: `discord-verification-lambda-role`
- Inline policy: `discord-verification-lambda-policy`

### SSM Parameters
- `/discord-bot/token` (SecureString)
- `/discord-bot/public-key` (String)
- `/discord-bot/app-id` (String)

---

## After Deployment

1. **Update Discord Developer Portal**
   ```
   Go to: https://discord.com/developers/applications
   Your App > General Information
   Set "Interactions Endpoint URL" to:
   https://xxxxx.lambda-url.us-east-1.on.aws/
   ```

2. **Verify Endpoint**
   - Discord automatically sends PING request
   - Should get green checkmark

3. **Test in Discord Server**
   - Run `/setup-email-verification`
   - Configure guild settings
   - Test verification flow

4. **Monitor Logs**
   ```bash
   aws logs tail /aws/lambda/discord-verification-handler --follow
   ```

---

## Cleanup

To remove all resources:
```bash
./cleanup-aws.sh
```

This deletes:
- Lambda function and layer
- DynamoDB tables
- IAM role and policies
- SSM parameters

**Note:** Does NOT delete SES configurations (domain/email verifications)

---

## Support

- **Issues:** Check `SETUP_SCRIPT_FIXES.md` for known issues and solutions
- **Testing:** See `TESTING_QUICK_START.md` for comprehensive testing
- **Deployment:** See `FRESH_DEPLOYMENT_SUCCESS.md` for deployment example

---

## Changelog

### Version 2.0 (December 9, 2025)
- ✅ Fixed SES verification hang
- ✅ Removed AWS_REGION from Lambda environment
- ✅ Added Python zipfile fallback
- ✅ Added environment variable support
- ✅ Added non-interactive mode
- ✅ Improved error messages
- ✅ Added backward compatibility

### Version 1.0 (Original)
- Initial release
- Basic interactive deployment
- Required zip command
- Always prompted for SES verification
