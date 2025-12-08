# Deployment Tests - Quick Reference

This directory contains comprehensive deployment validation tests for the Discord Email Verification Bot.

## Overview

- **Total Tests:** 60
- **Test Files:** 2 (test_infrastructure.py, test_configuration.py)
- **Execution Time:** ~5 seconds
- **Pass Rate:** 100%

## Test Categories

### test_infrastructure.py (29 tests)
Validates AWS infrastructure and Lambda packaging:
- Lambda package validation (5 tests)
- AWS service dependencies (5 tests)
- IAM permission requirements (5 tests)
- Lambda configuration (5 tests)
- DynamoDB table structure (5 tests)
- Network configuration (3 tests)
- Summary test (1 test)

### test_configuration.py (31 tests)
Validates environment variables, logging, and deployment readiness:
- Environment variable validation (7 tests)
- SSM Parameter Store configuration (4 tests)
- Logging configuration (4 tests)
- Error handling configuration (3 tests)
- Discord configuration (4 tests)
- Deployment smoke tests (5 tests)
- Configuration validation functions (3 tests)
- Summary test (1 test)

## Quick Commands

### Run All Deployment Tests
```bash
cd /home/offsetkeyz/claude_coding_projects/au-discord-bot
pytest tests/deployment/ -v
```

### Run Smoke Tests Only (Quick Validation)
```bash
pytest tests/deployment/ -v -m smoke
```
**7 critical tests in <2 seconds**

### Run Infrastructure Tests
```bash
pytest tests/deployment/test_infrastructure.py -v
```

### Run Configuration Tests
```bash
pytest tests/deployment/test_configuration.py -v
```

### Run Specific Test Categories
```bash
# Infrastructure tests only
pytest tests/deployment/ -v -m infrastructure

# Configuration tests only
pytest tests/deployment/ -v -m configuration

# All deployment tests
pytest tests/deployment/ -v -m deployment
```

## Test Markers

- `@pytest.mark.deployment` - All deployment tests
- `@pytest.mark.infrastructure` - Infrastructure validation
- `@pytest.mark.configuration` - Configuration validation
- `@pytest.mark.smoke` - Critical path smoke tests

## Expected Output

### Success (All Tests Passing)
```
======================== 60 passed in 5.58s ========================
```

### Smoke Tests Success
```
======================== 7 passed in 1.50s =========================
```

## Interpreting Failures

Each test includes:
1. **Clear failure message** - What failed
2. **Expected behavior** - What should happen
3. **Actual behavior** - What actually happened
4. **Remediation guidance** - How to fix it

### Example Failure
```
AssertionError: DISCORD_PUBLIC_KEY must be 64 characters (got 32)
```
**Fix:** Set DISCORD_PUBLIC_KEY environment variable to 64 hex characters from Discord Developer Portal.

## Pre-Deployment Checklist

Before deploying to AWS Lambda:

1. ✓ Run all deployment tests
   ```bash
   pytest tests/deployment/ -v
   ```

2. ✓ Run smoke tests
   ```bash
   pytest tests/deployment/ -v -m smoke
   ```

3. ✓ Review `DEPLOYMENT_CHECKLIST.md`

4. ✓ Verify all environment variables set

5. ✓ Confirm AWS infrastructure created

## Common Issues

### "Missing environment variable"
**Cause:** Required env var not set
**Fix:** Check `tests/conftest.py` for required vars (set in `set_test_environment` fixture)

### "Signature verification failed"
**Cause:** Invalid DISCORD_PUBLIC_KEY
**Fix:** Ensure 64 hex characters from Discord Developer Portal

### "DynamoDB table schema mismatch"
**Cause:** Table schema doesn't match code expectations
**Fix:** Review test expectations and update table schema

### "Import errors"
**Cause:** Missing dependencies
**Fix:** Install requirements: `pip install -r requirements.txt`

## CI/CD Integration

### GitHub Actions
```yaml
- name: Run Deployment Tests
  run: |
    source venv/bin/activate
    pytest tests/deployment/ -v --tb=short

- name: Run Smoke Tests
  run: |
    source venv/bin/activate
    pytest tests/deployment/ -v -m smoke
```

### Pre-Commit Hook
```bash
#!/bin/bash
pytest tests/deployment/ -v -m smoke || exit 1
```

## Test Coverage

Deployment tests focus on **configuration validation**, not application logic.

Expected coverage:
- **lambda_function.py:** ~28% (entry point validation)
- **discord_interactions.py:** ~71% (signature verification)
- **logging_utils.py:** ~59% (PII sanitization)

Application logic is covered by:
- Phase 2D: Unit tests (handlers, setup wizard)
- Phase 2E: Security and validation tests
- Phase 3A: Integration tests

## Files in This Directory

- `test_infrastructure.py` - Infrastructure validation tests
- `test_configuration.py` - Configuration validation tests
- `__init__.py` - Package marker
- `README.md` - This file

## Related Documentation

- `../../DEPLOYMENT_CHECKLIST.md` - Complete deployment guide
- `../../PHASE_4B_DEPLOYMENT_TESTS_REPORT.md` - Detailed test report
- `../conftest.py` - Shared test fixtures

## Support

For issues or questions:
1. Review test failure messages
2. Check `DEPLOYMENT_CHECKLIST.md`
3. Run specific failing test with verbose output:
   ```bash
   pytest tests/deployment/test_infrastructure.py::TestClass::test_name -vv
   ```

## Version History

- **v1.0** (2025-12-08) - Initial deployment test suite (60 tests)
  - Infrastructure validation (29 tests)
  - Configuration validation (31 tests)
  - 100% pass rate
  - Ready for production deployment

---

**Last Updated:** 2025-12-08
**Status:** Production Ready ✓
**Tests:** 60 passing
**Execution Time:** ~5 seconds
