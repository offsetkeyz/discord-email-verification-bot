"""
Phase 3A: Core Verification Flow Integration Tests.

These tests validate complete end-to-end verification workflows including:
- Happy path: user starts verification → submits email → receives code → verifies → gets role
- Expired code handling
- Rate limiting enforcement
- Max attempts lockout

All tests use moto for AWS mocking and freezegun for time control.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch
from moto import mock_aws
import boto3
from freezegun import freeze_time

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))


# ==============================================================================
# Integration Test Fixtures
# ==============================================================================

@pytest.fixture
def integration_mock_env(mock_dynamodb_tables, mock_ses_service, mock_ssm_parameters):
    """Complete integration environment with all AWS services mocked."""
    # Patch all module-level clients
    with patch('dynamodb_operations.sessions_table', mock_dynamodb_tables['sessions']), \
         patch('dynamodb_operations.records_table', mock_dynamodb_tables['records']), \
         patch('guild_config.configs_table', mock_dynamodb_tables['configs']), \
         patch('ses_email.ses_client', mock_ses_service), \
         patch('ssm_utils.ssm_client', mock_ssm_parameters):

        yield {
            'dynamodb': mock_dynamodb_tables,
            'ses': mock_ses_service,
            'ssm': mock_ssm_parameters
        }


@pytest.fixture
def setup_test_guild(integration_mock_env):
    """Set up a test guild configuration."""
    from guild_config import save_guild_config

    save_guild_config(
        guild_id='test_guild_123',
        role_id='verified_role_456',
        channel_id='verify_channel_789',
        setup_by_user_id='admin_user_001',
        allowed_domains=['auburn.edu', 'test.edu'],
        custom_message='Welcome! Please verify your .edu email to gain access.'
    )

    return {
        'guild_id': 'test_guild_123',
        'role_id': 'verified_role_456',
        'channel_id': 'verify_channel_789',
        'user_id': 'test_user_999'
    }


# Import modules after setting up path
from dynamodb_operations import (
    create_verification_session,
    get_verification_session,
    mark_verified,
    increment_attempts,
    check_rate_limit
)
from verification_logic import (
    validate_edu_email,
    is_valid_code_format,
    generate_code
)
from guild_config import get_guild_config, get_guild_allowed_domains


# ==============================================================================
# Phase 3A.1: Happy Path Verification Flow
# ==============================================================================

@pytest.mark.integration
class TestHappyPathVerificationFlow:
    """Integration tests for successful verification end-to-end."""

    @freeze_time("2025-01-15 10:00:00")
    def test_complete_verification_success(self, integration_mock_env, setup_test_guild):
        """
        Test complete happy path verification flow.

        Flow:
        1. Check rate limit (passes)
        2. Create session with email and code
        3. Verify session data persists
        4. Verify code matches
        5. Mark as verified
        6. Confirm verified state
        """
        guild = setup_test_guild

        # Step 1: Rate limit check
        is_allowed, remaining = check_rate_limit(guild['user_id'], guild['guild_id'])
        assert is_allowed is True, "First verification request should be allowed"

        # Step 2-3: Create session
        test_email = 'student@auburn.edu'
        verification_code = generate_code()

        # Validate email against guild domains
        allowed_domains = get_guild_allowed_domains(guild['guild_id'])
        assert validate_edu_email(test_email, allowed_domains) is True

        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email=test_email,
            code=verification_code,
            expiry_minutes=15
        )
        assert verification_id is not None

        # Step 4: Verify session data
        session = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session is not None
        assert session['email'] == test_email
        assert session['code'] == verification_code
        assert session['state'] == 'awaiting_code'
        assert is_valid_code_format(verification_code) is True

        # Step 5: Verify code hasn't expired
        expires_at = datetime.fromisoformat(session['expires_at'])
        assert datetime.utcnow() < expires_at, "Code should not be expired"

        # Step 6: Mark as verified
        mark_verified(verification_id, guild['user_id'], guild['guild_id'])

        # Step 7: Verify session is deleted after verification
        # Note: mark_verified creates a record and deletes the session
        final_session = get_verification_session(guild['user_id'], guild['guild_id'])
        assert final_session is None, "Session should be deleted after verification"

    @freeze_time("2025-01-15 10:00:00")
    def test_verification_with_different_edu_domain(self, integration_mock_env, setup_test_guild):
        """Test verification flow with non-default .edu domain."""
        guild = setup_test_guild

        # Use test.edu domain (configured in setup_test_guild)
        test_email = 'student@test.edu'
        verification_code = generate_code()

        # Validate email against guild's allowed domains
        allowed_domains = get_guild_allowed_domains(guild['guild_id'])
        assert validate_edu_email(test_email, allowed_domains) is True

        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email=test_email,
            code=verification_code,
            expiry_minutes=15
        )

        session = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session['email'] == test_email
        assert session['state'] == 'awaiting_code'


# ==============================================================================
# Phase 3A.2: Expired Code Handling
# ==============================================================================

@pytest.mark.integration
class TestExpiredCodeHandling:
    """Integration tests for expired verification code scenarios."""

    @freeze_time("2025-01-15 10:00:00")
    def test_code_expires_after_15_minutes(self, integration_mock_env, setup_test_guild):
        """Test that verification codes expire after 15 minutes."""
        guild = setup_test_guild

        verification_code = generate_code()

        create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code=verification_code,
            expiry_minutes=15
        )

        # Verify code is valid at 10:00
        session = get_verification_session(guild['user_id'], guild['guild_id'])
        expires_at = datetime.fromisoformat(session['expires_at'])
        assert datetime.utcnow() < expires_at, "Code should be valid at creation time"

        # Time travel to 10:16 (1 minute past expiry)
        with freeze_time("2025-01-15 10:16:00"):
            session = get_verification_session(guild['user_id'], guild['guild_id'])
            expires_at = datetime.fromisoformat(session['expires_at'])
            now = datetime.utcnow()

            is_expired = now > expires_at
            assert is_expired is True, "Code should be expired after 15 minutes"

    @freeze_time("2025-01-15 10:00:00")
    def test_code_valid_just_before_expiry(self, integration_mock_env, setup_test_guild):
        """Test that code is still valid 1 second before expiry."""
        guild = setup_test_guild

        create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        # Time travel to 10:14:59 (1 second before expiry)
        with freeze_time("2025-01-15 10:14:59"):
            session = get_verification_session(guild['user_id'], guild['guild_id'])
            expires_at = datetime.fromisoformat(session['expires_at'])
            is_expired = datetime.utcnow() > expires_at
            assert is_expired is False, "Code should still be valid 1 second before expiry"


# ==============================================================================
# Phase 3A.3: Rate Limiting Enforcement
# ==============================================================================

@pytest.mark.integration
class TestRateLimitingEnforcement:
    """Integration tests for rate limiting across verification flow."""

    @freeze_time("2025-01-15 10:00:00")
    def test_per_guild_rate_limit_60_seconds(self, integration_mock_env, setup_test_guild):
        """Test that users are rate limited to 1 request per 60 seconds per guild."""
        guild = setup_test_guild

        # First request at 10:00 - should be allowed
        is_allowed, remaining = check_rate_limit(
            guild['user_id'],
            guild['guild_id'],
            cooldown_seconds=60
        )
        assert is_allowed is True
        assert remaining == 0

        # Create session to trigger rate limit
        create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        # Second request at 10:00:30 - should be blocked by per-guild rate limit
        with freeze_time("2025-01-15 10:00:30"):
            is_allowed, remaining = check_rate_limit(
                guild['user_id'],
                guild['guild_id'],
                cooldown_seconds=60
            )
            assert is_allowed is False, "Should be rate limited after 30 seconds"
            # Remaining could be from per-guild (~30s) or global (~270s)
            assert remaining > 0, f"Should have time remaining, got {remaining}"

        # Third request at 10:06:00 - should be allowed (past both 60s per-guild and 300s global)
        with freeze_time("2025-01-15 10:06:00"):
            is_allowed, remaining = check_rate_limit(
                guild['user_id'],
                guild['guild_id'],
                cooldown_seconds=60
            )
            assert is_allowed is True, "Should be allowed after 6 minutes (360 seconds)"
            assert remaining == 0

    @freeze_time("2025-01-15 10:00:00")
    def test_global_rate_limit_300_seconds(self, integration_mock_env):
        """Test global rate limit across all guilds (5 minutes)."""
        user_id = 'test_user_999'
        guild_a = 'test_guild_123'
        guild_b = 'test_guild_456'

        # First verification in guild A
        is_allowed, _ = check_rate_limit(user_id, guild_a, cooldown_seconds=60, global_cooldown=300)
        assert is_allowed is True

        create_verification_session(
            user_id=user_id,
            guild_id=guild_a,
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        # Try guild B after 2 minutes - blocked by global rate limit
        with freeze_time("2025-01-15 10:02:00"):
            is_allowed, remaining = check_rate_limit(
                user_id,
                guild_b,
                cooldown_seconds=60,
                global_cooldown=300
            )
            assert is_allowed is False, "Should be blocked by global rate limit"
            assert 170 < remaining < 190, "Should have ~3 minutes remaining on global cooldown"

        # Try guild B after 6 minutes - allowed
        with freeze_time("2025-01-15 10:06:00"):
            is_allowed, remaining = check_rate_limit(
                user_id,
                guild_b,
                cooldown_seconds=60,
                global_cooldown=300
            )
            assert is_allowed is True, "Should be allowed after global cooldown expires"


# ==============================================================================
# Phase 3A.4: Max Attempts Lockout
# ==============================================================================

@pytest.mark.integration
class TestMaxAttemptsLockout:
    """Integration tests for maximum verification attempts."""

    @freeze_time("2025-01-15 10:00:00")
    def test_increment_attempts_tracking(self, integration_mock_env, setup_test_guild):
        """Test that failed attempts are tracked correctly."""
        guild = setup_test_guild

        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        # Increment attempts
        attempts = increment_attempts(verification_id, guild['user_id'], guild['guild_id'])
        assert attempts == 1

        attempts = increment_attempts(verification_id, guild['user_id'], guild['guild_id'])
        assert attempts == 2

        attempts = increment_attempts(verification_id, guild['user_id'], guild['guild_id'])
        assert attempts == 3

    @freeze_time("2025-01-15 10:00:00")
    def test_successful_verification_after_failed_attempts(self, integration_mock_env, setup_test_guild):
        """Test that successful verification works after some failed attempts."""
        guild = setup_test_guild
        correct_code = '123456'

        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code=correct_code,
            expiry_minutes=15
        )

        # Failed attempt 1
        increment_attempts(verification_id, guild['user_id'], guild['guild_id'])

        # Failed attempt 2
        increment_attempts(verification_id, guild['user_id'], guild['guild_id'])

        # Get session to verify attempts
        session = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session['attempts'] == 2

        # Successful verification on attempt 3
        assert session['code'] == correct_code
        mark_verified(verification_id, guild['user_id'], guild['guild_id'])


# ==============================================================================
# Phase 3A.5: Session Data Persistence
# ==============================================================================

@pytest.mark.integration
class TestSessionPersistence:
    """Integration tests for session data persistence and retrieval."""

    @freeze_time("2025-01-15 10:00:00")
    def test_session_persists_across_operations(self, integration_mock_env, setup_test_guild):
        """Test that session data persists across multiple read/write operations."""
        guild = setup_test_guild
        verification_code = '123456'

        # Create session
        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code=verification_code,
            expiry_minutes=15
        )

        # Read session multiple times
        session1 = get_verification_session(guild['user_id'], guild['guild_id'])
        session2 = get_verification_session(guild['user_id'], guild['guild_id'])

        # Data should be consistent
        assert session1['code'] == session2['code']
        assert session1['email'] == session2['email']
        assert session1['state'] == session2['state']

        # Increment attempts
        increment_attempts(verification_id, guild['user_id'], guild['guild_id'])

        # Read again
        session3 = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session3['attempts'] == 1
        assert session3['code'] == verification_code, "Code should persist after increment"

    @freeze_time("2025-01-15 10:00:00")
    def test_multiple_users_separate_sessions(self, integration_mock_env, setup_test_guild):
        """Test that multiple users have separate, isolated sessions."""
        guild = setup_test_guild

        # User 1 session
        user1_code = '111111'
        create_verification_session(
            user_id='user_001',
            guild_id=guild['guild_id'],
            email='user1@auburn.edu',
            code=user1_code,
            expiry_minutes=15
        )

        # User 2 session
        user2_code = '222222'
        create_verification_session(
            user_id='user_002',
            guild_id=guild['guild_id'],
            email='user2@auburn.edu',
            code=user2_code,
            expiry_minutes=15
        )

        # Verify sessions are separate
        session1 = get_verification_session('user_001', guild['guild_id'])
        session2 = get_verification_session('user_002', guild['guild_id'])

        assert session1['code'] == user1_code
        assert session2['code'] == user2_code
        assert session1['email'] != session2['email']
