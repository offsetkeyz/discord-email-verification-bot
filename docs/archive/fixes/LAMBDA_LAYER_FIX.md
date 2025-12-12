# Lambda Layer GLIBC Compatibility Fix

## Issue Discovered

**Error:** Discord endpoint validation failed  
**Root Cause:** Lambda layer had GLIBC version mismatch  
**Symptom:** `Runtime.ImportModuleError: /lib64/libc.so.6: version GLIBC_2.33 not found`

### What Happened

The PyNaCl library was installed on the local development machine and included compiled native libraries (`.so` files) that were built against a newer version of GLIBC (2.33+). AWS Lambda's Python 3.11 runtime uses an older GLIBC version and couldn't load these libraries.

---

## Solution Applied

### 1. Rebuilt Lambda Layer with manylinux Wheels

Used pip's platform-specific installation to download pre-compiled wheels compatible with Lambda:

```bash
pip3 install \
    --platform manylinux2014_x86_64 \
    --target layer/python \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    -r lambda-requirements.txt
```

**Key flags:**
- `--platform manylinux2014_x86_64` - Downloads wheels compatible with Lambda's runtime
- `--only-binary=:all:` - Forces binary wheels (no source builds)
- `--python-version 3.11` - Matches Lambda runtime

### 2. Published New Layer Version

- **Old Layer:** Version 5 (GLIBC incompatible)
- **New Layer:** Version 6 (manylinux2014 compatible)

### 3. Updated Lambda Function

Updated Lambda to use the new compatible layer version.

---

## Verification

### Before Fix
```
[ERROR] Runtime.ImportModuleError: Unable to import module 'lambda_function': 
/lib64/libc.so.6: version `GLIBC_2.33' not found
```

### After Fix
```
INIT_START Runtime Version: python:3.11.v107
START RequestId: 80247f00-d395-4bb9-a629-f0e160030bb7
Received event: {"body": "{\"type\":1}", ...}
Duration: 2.05 ms	Init Duration: 801.83 ms
✓ No import errors
✓ Function executes successfully
✓ Signature validation working
```

---

## Current Status

**Lambda Function:** ✅ Active and working  
**Layer Version:** 6 (manylinux2014)  
**Runtime:** Python 3.11  
**Compatibility:** Lambda runtime compatible  
**Discord Endpoint:** Ready for verification  

**Function URL:** `https://dmnw3lxadg36anjkjmkfbjegbi0vemfx.lambda-url.us-east-1.on.aws/`

---

## How to Prevent This in Future

### Option 1: Always Use manylinux Wheels (Recommended)

Update `setup-aws.sh` to use the manylinux installation method:

```bash
# In setup-aws.sh, replace pip install line with:
pip3 install \
    --platform manylinux2014_x86_64 \
    --target layer/python \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    -r lambda-requirements.txt
```

### Option 2: Use Docker with Lambda Runtime Image

Build the layer inside a Docker container matching Lambda's environment:

```bash
docker run --rm \
  -v "$PWD":/var/task \
  public.ecr.aws/lambda/python:3.11 \
  pip install -r lambda-requirements.txt -t /var/task/layer/python
```

### Option 3: Use AWS SAM Build

AWS SAM automatically handles compatible dependencies:

```yaml
# template.yaml
Resources:
  DependenciesLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      LayerName: discord-bot-dependencies
      ContentUri: dependencies/
      CompatibleRuntimes:
        - python3.11
```

---

## Testing Lambda Function

### Test PING (Discord Verification)

```bash
aws lambda invoke \
  --function-name discord-verification-handler \
  --payload '{"body":"{\"type\":1}","headers":{"x-signature-ed25519":"test","x-signature-timestamp":"'$(date +%s)'"},"requestContext":{"http":{"method":"POST"}}}' \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  response.json
```

**Expected:** 401 Unauthorized (signature validation working)

### Monitor Logs

```bash
aws logs tail /aws/lambda/discord-verification-handler \
  --follow \
  --region us-east-1
```

---

## Next Steps

1. ✅ **Lambda layer fixed** - GLIBC compatibility resolved
2. ✅ **Function working** - Loads and executes successfully
3. ⏭️ **Update Discord Developer Portal** - Try endpoint verification again
4. ⏭️ **Test in Discord** - Follow DISCORD_TESTING_GUIDE.md

---

## Technical Details

### Dependencies Installed (Layer Version 6)

```
PyNaCl-1.6.1                (manylinux2014_x86_64)
requests-2.32.5             (py3-none-any)
certifi-2025.11.12          (py3-none-any)
cffi-2.0.0                  (manylinux2014_x86_64)
charset_normalizer-3.4.4    (manylinux2014_x86_64)
idna-3.11                   (py3-none-any)
urllib3-2.6.1               (py3-none-any)
pycparser-2.23              (py3-none-any)
```

### Layer ARN

```
arn:aws:lambda:us-east-1:425269986063:layer:discord-bot-dependencies:6
```

### Lambda Configuration

```
Runtime: python3.11
Memory: 512 MB
Timeout: 30 seconds
Handler: lambda_function.lambda_handler
```

---

**Issue Resolution:** COMPLETE  
**Lambda Status:** READY FOR DISCORD TESTING
