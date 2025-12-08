#!/bin/bash
# Verify DNS configuration for SES email authentication

if [ -z "$1" ]; then
    echo "Usage: $0 <domain>"
    echo "Example: $0 thedailydecrypt.com"
    exit 1
fi

DOMAIN=$1

echo "============================================"
echo "DNS Configuration Verification for: $DOMAIN"
echo "============================================"
echo ""

# Check SPF
echo "1. Checking SPF Record..."
SPF=$(dig +short TXT $DOMAIN | grep "v=spf1")
if [ -n "$SPF" ]; then
    echo "   ✓ SPF Record Found:"
    echo "     $SPF"
    if [[ $SPF == *"amazonses.com"* ]]; then
        echo "   ✓ Includes amazonses.com"
    else
        echo "   ✗ WARNING: Does not include amazonses.com"
        echo "     Add: include:amazonses.com"
    fi
else
    echo "   ✗ ERROR: No SPF record found"
    echo "     Add TXT record: v=spf1 include:amazonses.com ~all"
fi
echo ""

# Check DMARC
echo "2. Checking DMARC Record..."
DMARC=$(dig +short TXT _dmarc.$DOMAIN)
if [ -n "$DMARC" ]; then
    echo "   ✓ DMARC Record Found:"
    echo "     $DMARC"
    if [[ $DMARC == *"v=DMARC1"* ]]; then
        echo "   ✓ Valid DMARC record"
    else
        echo "   ✗ WARNING: Invalid DMARC format"
    fi
else
    echo "   ✗ ERROR: No DMARC record found"
    echo "     Add TXT record at _dmarc.$DOMAIN:"
    echo "     v=DMARC1; p=quarantine; rua=mailto:dmarc@$DOMAIN"
fi
echo ""

# Check SES verification token
echo "3. Checking SES Verification Token..."
SES_TOKEN=$(dig +short TXT _amazonses.$DOMAIN)
if [ -n "$SES_TOKEN" ]; then
    echo "   ✓ SES Verification Token Found:"
    echo "     $SES_TOKEN"
else
    echo "   ✗ No SES verification token found"
    echo "     Run: aws ses verify-domain-identity --domain $DOMAIN"
    echo "     Then add the returned token as TXT record at _amazonses.$DOMAIN"
fi
echo ""

# Check DKIM (requires AWS CLI to get tokens)
echo "4. Checking DKIM Records..."
if command -v aws &> /dev/null; then
    DKIM_TOKENS=$(aws ses get-identity-dkim-attributes --identities $DOMAIN --query "DkimAttributes.\"$DOMAIN\".DkimTokens" --output text 2>/dev/null)

    if [ -n "$DKIM_TOKENS" ]; then
        echo "   DKIM Tokens from AWS:"
        for TOKEN in $DKIM_TOKENS; do
            echo "   Checking: ${TOKEN}._domainkey.$DOMAIN"
            DKIM_VALUE=$(dig +short CNAME ${TOKEN}._domainkey.$DOMAIN)
            if [ -n "$DKIM_VALUE" ]; then
                echo "     ✓ Found: $DKIM_VALUE"
            else
                echo "     ✗ NOT FOUND"
                echo "       Add CNAME: ${TOKEN}._domainkey.$DOMAIN → ${TOKEN}.dkim.amazonses.com"
            fi
        done
    else
        echo "   ✗ No DKIM tokens found in AWS"
        echo "     Enable DKIM: aws ses set-identity-dkim-enabled --identity $DOMAIN --dkim-enabled"
    fi
else
    echo "   ⚠ AWS CLI not found - cannot check DKIM"
    echo "     Manually verify DKIM CNAME records exist"
fi
echo ""

# Check MX records (optional but good to know)
echo "5. Checking MX Records (informational)..."
MX=$(dig +short MX $DOMAIN)
if [ -n "$MX" ]; then
    echo "   MX Records:"
    echo "$MX" | sed 's/^/     /'
else
    echo "   No MX records found (not required for SES sending)"
fi
echo ""

# Summary
echo "============================================"
echo "Summary"
echo "============================================"
echo ""

ERRORS=0

if [ -z "$SPF" ] || [[ $SPF != *"amazonses.com"* ]]; then
    echo "❌ SPF configuration needs attention"
    ((ERRORS++))
else
    echo "✅ SPF configured correctly"
fi

if [ -z "$DMARC" ]; then
    echo "❌ DMARC configuration needs attention"
    ((ERRORS++))
else
    echo "✅ DMARC configured correctly"
fi

if [ -z "$SES_TOKEN" ]; then
    echo "⚠️  SES verification pending"
    ((ERRORS++))
else
    echo "✅ SES domain verification configured"
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "🎉 All critical DNS records are configured!"
    echo ""
    echo "Next steps:"
    echo "1. Wait 24-48 hours for DNS propagation"
    echo "2. Verify in AWS SES console: https://console.aws.amazon.com/ses/home#verified-senders-domain:"
    echo "3. Send test email"
else
    echo "⚠️  Found $ERRORS issue(s) that need attention"
    echo ""
    echo "Please fix the issues above and run this script again."
fi
echo ""
