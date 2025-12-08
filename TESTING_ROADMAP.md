# Testing Roadmap - Discord Email Verification Bot

**Project:** Discord Email Verification Bot
**Last Updated:** 2025-12-07
**Current Phase:** Phase 2C (Unit Tests - AWS Services)
**Overall Progress:** 52.02% code coverage (463/890 statements)

---

## Overview

This document outlines the comprehensive testing strategy for the Discord email verification bot. The testing effort is organized into 4 major phases with multiple sub-phases, progressing from unit tests through integration tests to end-to-end testing.

### Goals

- **Phase 1 (COMPLETE):** Establish testing infrastructure and tooling
- **Phase 2 (IN PROGRESS):** Achieve 85%+ unit test coverage across all modules
- **Phase 3 (PENDING):** Validate integration between components
- **Phase 4 (PENDING):** End-to-end and deployment validation

### Success Criteria

- ✅ All tests pass consistently
- ✅ 90%+ overall code coverage
- ✅ 100% coverage on security-critical modules
- ✅ All integration flows validated
- ✅ CI/CD pipeline green
- ✅ Documentation complete

---

## Phase Breakdown

### Phase 1: Testing Infrastructure ✅ COMPLETE

**Status:** COMPLETE
**Duration:** Completed
**Coverage Impact:** Foundation established

#### Deliverables
- ✅ pytest configuration (`pytest.ini`)
- ✅ Coverage configuration (`.coveragerc`)
- ✅ CI/CD pipeline (`.github/workflows/test.yml`)
- ✅ Test fixtures and helpers (`tests/conftest.py`)
- ✅ Discord payload library (`tests/fixtures/discord_payloads.py`)
- ✅ Directory structure (unit/, integration/, e2e/, deployment/)
- ✅ Development dependencies (`requirements-dev.txt`)

#### Files Created
- `pytest.ini` - Test configuration
- `.coveragerc` - Coverage measurement settings
- `.github/workflows/test.yml` - CI/CD pipeline
- `tests/conftest.py` - Central fixtures (384 lines)
- `tests/fixtures/discord_payloads.py` - Test data (521 lines)
- `requirements-dev.txt` - 17 development dependencies

---

### Phase 2A: Unit Tests - Core Logic ✅ COMPLETE

**Status:** COMPLETE
**Duration:** Completed
**Coverage:** 100% on target module

#### Deliverables
- ✅ `tests/unit/test_verification_logic.py` (381 lines, 54 tests)

#### Test Coverage
| Module | Statements | Coverage | Tests |
|--------|-----------|----------|-------|
| `verification_logic.py` | 16 | 100% | 54 |

#### Test Categories
- ✅ Code generation (7 tests)
- ✅ Email validation (33 tests)
- ✅ Code format validation (13 tests)
- ✅ Integration workflows (4 tests)
- ✅ Security testing (injection prevention)

---

### Phase 2B: Unit Tests - Discord Integration ✅ COMPLETE

**Status:** COMPLETE
**Duration:** Completed
**Coverage:** 100% on target modules

#### Deliverables
- ✅ `tests/unit/test_discord_interactions.py` (comprehensive signature verification tests)
- ✅ `tests/unit/test_discord_api.py` (role assignment and member info tests)

#### Test Coverage
| Module | Statements | Coverage | Tests |
|--------|-----------|----------|-------|
| `discord_interactions.py` | 61 | 100% | 15+ |
| `discord_api.py` | 36 | 100% | 12+ |

#### Test Categories
- ✅ Signature verification (missing headers, invalid signatures, replay attacks)
- ✅ Role assignment (success, not found, errors)
- ✅ Member info retrieval
- ✅ API error handling

---

### Phase 2C: Unit Tests - AWS Services 🔄 IN PROGRESS

**Status:** 87% COMPLETE
**Duration:** In progress
**Target Coverage:** 85%+ on AWS service modules

#### Deliverables
- ✅ `tests/unit/test_dynamodb_operations.py` (87% complete)
- ⏳ `tests/unit/test_ses_email.py` (PENDING)
- ⏳ `tests/unit/test_ssm_utils.py` (PENDING)
- ⏳ `tests/unit/test_guild_config.py` (PENDING)

#### Test Coverage (Projected)
| Module | Statements | Current | Target |
|--------|-----------|---------|--------|
| `dynamodb_operations.py` | 138 | 87% | 90% |
| `ses_email.py` | 22 | 0% | 85% |
| `ssm_utils.py` | 11 | 0% | 90% |
| `guild_config.py` | 55 | 0% | 85% |

#### Remaining Work
1. Complete `test_dynamodb_operations.py` (13% remaining)
2. Create `test_ses_email.py` (~15-20 tests)
3. Create `test_ssm_utils.py` (~8-10 tests)
4. Create `test_guild_config.py` (~12-15 tests)

**Estimated Time:** 3-4 hours

---

### Phase 2D: Unit Tests - Request Handlers ⏳ PENDING

**Status:** NOT STARTED
**Duration:** Estimated 4-6 hours
**Target Coverage:** 85%+ on handler modules

#### Deliverables
- ⏳ `tests/unit/test_handlers.py` (verification flow handlers)
- ⏳ `tests/unit/test_setup_handler.py` (admin setup handlers)

#### Test Coverage (Projected)
| Module | Statements | Current | Target |
|--------|-----------|---------|--------|
| `handlers.py` | 105 | 0% | 85% |
| `setup_handler.py` | 259 | 0% | 85% |

#### Test Categories (Planned)
- Button interaction handling
- Modal submission processing
- Email verification flow
- Role assignment logic
- Admin setup wizard
- Configuration validation
- Error handling

**Dependencies:** Phase 2C completion

---

### Phase 2E: Unit Tests - Lambda Entry Point ⏳ PENDING

**Status:** NOT STARTED
**Duration:** Estimated 3-4 hours
**Target Coverage:** 85%+ on lambda_function.py

#### Deliverables
- ⏳ `tests/unit/test_lambda_function.py` (routing and orchestration)

#### Test Coverage (Projected)
| Module | Statements | Current | Target |
|--------|-----------|---------|--------|
| `lambda_function.py` | 63 | 0% | 85% |

#### Test Categories (Planned)
- Request routing (PING, commands, components, modals)
- Signature verification integration
- Error handling and logging
- Response formatting
- Unknown interaction types
- Malformed requests

**Dependencies:** Phase 2D completion

---

### Phase 2F: Unit Tests - Utility Modules ⏳ PENDING

**Status:** NOT STARTED
**Duration:** Estimated 2-3 hours
**Target Coverage:** 85%+ on utility modules

#### Deliverables
- ⏳ `tests/unit/test_logging_utils.py` (PII sanitization)
- ⏳ `tests/unit/test_validation_utils.py` (input validation)

#### Test Coverage (Projected)
| Module | Statements | Current | Target |
|--------|-----------|---------|--------|
| `logging_utils.py` | 44 | 0% | 90% |
| `validation_utils.py` | 80 | 0% | 90% |

#### Test Categories (Planned)
- Email redaction in logs
- Token sanitization
- Discord ID validation
- Custom ID parsing
- Message URL validation
- Input length validation
- Injection prevention

**Dependencies:** Phase 2E completion

---

### Phase 3A: Integration Tests - Core Flows ✅ COMPLETE

**Status:** COMPLETE
**Duration:** Completed 2025-12-08
**Target:** Complete verification and setup flows

#### Deliverables
- ✅ `tests/integration/test_verification_flow.py` (457 lines, 10 tests, 100% passing)

#### Test Scenarios (Implemented)
- ✅ Complete verification flow (email → code → role → session deletion)
- ✅ Verification with different .edu domains (multi-domain support)
- ✅ Code expiration after 15 minutes
- ✅ Code validation just before expiry (boundary condition)
- ✅ Per-guild rate limiting (60 second cooldown)
- ✅ Global rate limiting (300 second cooldown across all guilds)
- ✅ Failed attempt increment tracking
- ✅ Successful verification after failed attempts
- ✅ Session data persistence across operations
- ✅ Multi-user session isolation

#### Test Coverage
| Test Class | Tests | Status |
|-----------|-------|--------|
| `TestHappyPathVerificationFlow` | 2 | ✅ Passing |
| `TestExpiredCodeHandling` | 2 | ✅ Passing |
| `TestRateLimitingEnforcement` | 2 | ✅ Passing |
| `TestMaxAttemptsLockout` | 2 | ✅ Passing |
| `TestSessionPersistence` | 2 | ✅ Passing |
| **TOTAL** | **10** | **✅ 100%** |

#### Technical Implementation
- Uses `moto` for AWS service mocking (DynamoDB, SES, SSM)
- Uses `freezegun` for precise time control in tests
- Integration test fixtures properly mock all AWS services
- Tests validate realistic user workflows with end-to-end scenarios
- Fixed import: `generate_code()` vs `generate_verification_code()`
- Properly tests session deletion after successful verification
- Accounts for both per-guild and global rate limit interactions

**Dependencies:** None (standalone integration tests)

---

### Phase 3B: Integration Tests - Error Paths ⏳ PENDING

**Status:** NOT STARTED
**Duration:** Estimated 4-6 hours
**Target:** Validate error handling across components

#### Deliverables
- ⏳ `tests/integration/test_error_scenarios.py` (new)
- ⏳ `tests/integration/test_edge_cases.py` (new)

#### Test Scenarios (Planned)
- DynamoDB failures
- SES quota exceeded
- Discord API timeouts
- Invalid configurations
- Race conditions
- Concurrent requests
- Network failures

**Dependencies:** Phase 3A completion

---

### Phase 4A: End-to-End Tests ⏳ PENDING

**Status:** NOT STARTED
**Duration:** Estimated 8-10 hours
**Target:** Full system validation

#### Deliverables
- ⏳ `tests/e2e/test_complete_flows.py` (new)
- ⏳ `tests/e2e/test_multi_user_scenarios.py` (new)

#### Test Scenarios (Planned)
- New user verification journey
- Admin setup workflow
- Multi-user concurrent verification
- Cross-guild scenarios
- Performance testing
- Load testing

**Dependencies:** Phase 3B completion

---

### Phase 4B: Deployment Tests ⏳ PENDING

**Status:** NOT STARTED
**Duration:** Estimated 4-6 hours
**Target:** Production readiness validation

#### Deliverables
- ⏳ `tests/deployment/test_infrastructure.py` (new)
- ⏳ `tests/deployment/test_configuration.py` (new)

#### Test Scenarios (Planned)
- Lambda packaging validation
- Environment variable checks
- IAM permission validation
- DynamoDB table structure
- CloudWatch logging
- Deployment smoke tests

**Dependencies:** Phase 4A completion

---

## Overall Timeline

| Phase | Status | Estimated Hours | Start | End |
|-------|--------|----------------|-------|-----|
| Phase 1 | ✅ Complete | - | - | Completed |
| Phase 2A | ✅ Complete | - | - | Completed |
| Phase 2B | ✅ Complete | - | - | Completed |
| Phase 2C | 🔄 In Progress | 3-4 | In Progress | TBD |
| Phase 2D | ⏳ Pending | 4-6 | TBD | TBD |
| Phase 2E | ⏳ Pending | 3-4 | TBD | TBD |
| Phase 2F | ⏳ Pending | 2-3 | TBD | TBD |
| Phase 3A | ⏳ Pending | 6-8 | TBD | TBD |
| Phase 3B | ⏳ Pending | 4-6 | TBD | TBD |
| Phase 4A | ⏳ Pending | 8-10 | TBD | TBD |
| Phase 4B | ⏳ Pending | 4-6 | TBD | TBD |

**Total Remaining Effort:** 27-35 hours

---

## Coverage Progress

### Current Coverage: 52.02%

| Module | Statements | Tested | Coverage | Status |
|--------|-----------|--------|----------|--------|
| `verification_logic.py` | 16 | 16 | 100% | ✅ Complete |
| `discord_interactions.py` | 61 | 61 | 100% | ✅ Complete |
| `discord_api.py` | 36 | 36 | 100% | ✅ Complete |
| `dynamodb_operations.py` | 138 | 120 | 87% | 🔄 In Progress |
| `ses_email.py` | 22 | 0 | 0% | ⏳ Pending |
| `ssm_utils.py` | 11 | 0 | 0% | ⏳ Pending |
| `guild_config.py` | 55 | 0 | 0% | ⏳ Pending |
| `handlers.py` | 105 | 0 | 0% | ⏳ Pending |
| `setup_handler.py` | 259 | 0 | 0% | ⏳ Pending |
| `lambda_function.py` | 63 | 0 | 0% | ⏳ Pending |
| `logging_utils.py` | 44 | 0 | 0% | ⏳ Pending |
| `validation_utils.py` | 80 | 0 | 0% | ⏳ Pending |
| **TOTAL** | **890** | **463** | **52.02%** | **Phase 2C** |

### Coverage Goals

- **Phase 2 Completion:** 85%+ coverage
- **Phase 3 Completion:** 87%+ coverage
- **Phase 4 Completion:** 90%+ coverage
- **Security Modules:** 100% coverage (verification_logic, discord_interactions, validation_utils, logging_utils)

---

## Test Execution

### Running Tests Locally

```bash
# Run all tests
pytest

# Run specific phase
pytest tests/unit/  # Unit tests
pytest tests/integration/  # Integration tests
pytest tests/e2e/  # E2E tests

# Run with coverage
pytest --cov=lambda --cov-report=html

# Run specific test file
pytest tests/unit/test_verification_logic.py

# Run with markers
pytest -m unit  # Only unit tests
pytest -m "not slow"  # Skip slow tests
pytest -m security  # Only security tests
```

### CI/CD Pipeline

Tests run automatically on:
- Pull requests
- Pushes to main
- Manual workflow dispatch

**CI Configuration:** `.github/workflows/test.yml`

**Coverage Requirements:**
- Minimum: 10% (Phase 1-2C)
- Target: 90% (Phase 4 completion)

---

## Contributing to Testing

### Adding New Tests

1. **Choose the right location:**
   - `tests/unit/` - Fast, isolated tests for single functions
   - `tests/integration/` - Multi-component interaction tests
   - `tests/e2e/` - Full system flow tests
   - `tests/deployment/` - Infrastructure validation

2. **Use existing fixtures:**
   - See `tests/conftest.py` for available fixtures
   - AWS mocking: `mock_dynamodb_table`, `mock_ses`, `mock_ssm`
   - Discord mocking: `mock_discord_api`
   - Test data: `tests/fixtures/discord_payloads.py`

3. **Follow naming conventions:**
   - File: `test_<module_name>.py`
   - Class: `Test<Feature>`
   - Function: `test_<scenario>`

4. **Add appropriate markers:**
   ```python
   @pytest.mark.unit
   @pytest.mark.security
   def test_injection_prevention():
       ...
   ```

### Test Quality Standards

- ✅ Clear, descriptive test names
- ✅ Arrange-Act-Assert pattern
- ✅ One assertion per test (preferred)
- ✅ Edge cases and error paths covered
- ✅ Security scenarios included
- ✅ Docstrings for complex tests
- ✅ Fast execution (< 1s for unit tests)

---

## Known Issues

### Current Blockers

1. **CI Configuration** - Coverage threshold properly set to 10%, current coverage is 52.02% (passing)

### Future Considerations

1. **Mutation Testing** - Consider adding mutmut or cosmic-ray
2. **Performance Testing** - Add load tests for high-volume scenarios
3. **Contract Testing** - Validate Discord API contract compatibility
4. **Chaos Engineering** - Test resilience to AWS service failures

---

## References

- **Testing Infrastructure:** `tests/conftest.py`
- **Test Configuration:** `pytest.ini`, `.coveragerc`
- **CI/CD Pipeline:** `.github/workflows/test.yml`
- **Development Dependencies:** `requirements-dev.txt`
- **Security Documentation:** `SECURITY.md`
- **Security Fixes:** `SECURITY_FIXES_SUMMARY.md`

---

## Changelog

- **2025-12-07:** Created comprehensive testing roadmap
- **Phase 1:** Testing infrastructure established
- **Phase 2A:** Core logic tests completed (100% coverage)
- **Phase 2B:** Discord integration tests completed (100% coverage)
- **Phase 2C:** AWS services tests in progress (87% on DynamoDB)
- **2025-12-08:** Phase 3A integration tests completed (10 tests, 100% passing)

---

**Next Update:** After Phase 3B completion
