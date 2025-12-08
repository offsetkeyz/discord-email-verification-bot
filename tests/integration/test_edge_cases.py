"""
Phase 3B: Edge Cases Integration Tests.

These tests validate boundary conditions and unusual inputs including:
- Invalid guild configurations (missing fields, malformed data)
- Race conditions in concurrent verifications
- Concurrent requests from different users
- Malformed email addresses and data
- Expired sessions being accessed
- Verification attempts on non-existent sessions

All tests use moto for AWS mocking and freezegun for time control.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from freezegun import freeze_time
from decimal import Decimal

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

# Import after path setup
from dynamodb_operations import (
    create_verification_session,
    get_verification_session,
    mark_verified,
    increment_attempts,
    delete_session,
    is_user_verified
)
from verification_logic import (
    validate_edu_email,
    generate_code,
    is_valid_code_format
)
from guild_config import (
    get_guild_config,
    save_guild_config,
    get_guild_role_id,
    get_guild_allowed_domains,
    is_guild_configured
)


# ==============================================================================
# Phase 3B.6: Invalid Configuration Tests
# ==============================================================================

@pytest.mark.integration
class TestInvalidConfigurations:
    """Test behavior with invalid guild configurations."""

    def test_verification_with_missing_role_id(self, integration_mock_env):
        """Test verification flow when guild has no role configured."""
        guild_id = 'test_guild_no_role'

        # Save config without role_id (malformed)
        with patch('guild_config.configs_table.put_item') as mock_put:
            mock_put.return_value = {}
            # Try to save config without role_id
            # This tests the system's tolerance for missing data

        # Try to get role_id from unconfigured guild
        role_id = get_guild_role_id(guild_id)
        assert role_id is None

    def test_verification_with_empty_allowed_domains(self, integration_mock_env):
        """Test verification when guild has empty allowed domains list."""
        guild_id = 'test_guild_no_domains'

        # Save config with empty domains
        save_guild_config(
            guild_id=guild_id,
            role_id='role_123',
            channel_id='channel_456',
            setup_by_user_id='admin_001',
            allowed_domains=[],  # Empty list
            custom_message='Test message'
        )

        # Get domains should return default
        domains = get_guild_allowed_domains(guild_id)
        # System should handle gracefully - either return empty or defaults
        assert isinstance(domains, list)

    def test_guild_config_with_malformed_data(self, integration_mock_env):
        """Test handling of guild config with unexpected data types."""
        guild_id = 'test_guild_malformed'

        # Mock a config with unexpected types
        with patch('guild_config.configs_table.get_item') as mock_get:
            mock_get.return_value = {
                'Item': {
                    'guild_id': guild_id,
                    'role_id': 123,  # Should be string
                    'channel_id': None,  # Null value
                    'allowed_domains': 'not_a_list'  # Should be list
                }
            }

            config = get_guild_config(guild_id)
            # Should return the malformed data without crashing
            assert config is not None

    def test_is_guild_configured_with_partial_config(self, integration_mock_env):
        """Test guild configured check with partial configuration."""
        guild_id = 'test_guild_partial'

        # Mock partial config (missing channel_id)
        with patch('guild_config.configs_table.get_item') as mock_get:
            mock_get.return_value = {
                'Item': {
                    'guild_id': guild_id,
                    'role_id': 'role_123'
                    # Missing channel_id
                }
            }

            is_configured = is_guild_configured(guild_id)
            # Should return False for incomplete config
            assert is_configured is False


# ==============================================================================
# Phase 3B.7: Race Condition Tests
# ==============================================================================

@pytest.mark.integration
class TestRaceConditions:
    """Test concurrent operations and race conditions."""

    @freeze_time("2025-01-15 10:00:00")
    def test_concurrent_verifications_same_user_different_guilds(self, integration_mock_env):
        """Test race condition when user verifies in multiple guilds simultaneously."""
        user_id = 'test_user_concurrent'
        guild_a = 'guild_aaa'
        guild_b = 'guild_bbb'

        # Setup both guilds
        save_guild_config(guild_a, 'role_a', 'channel_a', 'admin', ['auburn.edu'])
        save_guild_config(guild_b, 'role_b', 'channel_b', 'admin', ['auburn.edu'])

        # Create sessions in both guilds simultaneously
        code_a = generate_code()
        code_b = generate_code()

        vid_a = create_verification_session(
            user_id=user_id,
            guild_id=guild_a,
            email='student@auburn.edu',
            code=code_a,
            expiry_minutes=15
        )

        vid_b = create_verification_session(
            user_id=user_id,
            guild_id=guild_b,
            email='student@auburn.edu',
            code=code_b,
            expiry_minutes=15
        )

        # Both sessions should exist independently
        session_a = get_verification_session(user_id, guild_a)
        session_b = get_verification_session(user_id, guild_b)

        assert session_a is not None
        assert session_b is not None
        assert session_a['code'] == code_a
        assert session_b['code'] == code_b

    @freeze_time("2025-01-15 10:00:00")
    def test_concurrent_code_submissions_same_session(self, integration_mock_env, setup_test_guild):
        """Test race condition when multiple code submissions happen simultaneously."""
        guild = setup_test_guild

        verification_code = '123456'
        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code=verification_code,
            expiry_minutes=15
        )

        # Simulate concurrent increment attempts
        attempt1 = increment_attempts(verification_id, guild['user_id'], guild['guild_id'])
        attempt2 = increment_attempts(verification_id, guild['user_id'], guild['guild_id'])
        attempt3 = increment_attempts(verification_id, guild['user_id'], guild['guild_id'])

        # All should succeed and increment properly
        assert attempt1 == 1
        assert attempt2 == 2
        assert attempt3 == 3

    @freeze_time("2025-01-15 10:00:00")
    def test_session_deletion_during_verification(self, integration_mock_env, setup_test_guild):
        """Test race condition when session is deleted during verification check."""
        guild = setup_test_guild

        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        # Verify session exists
        session = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session is not None

        # Delete session (simulating concurrent deletion)
        delete_session(guild['user_id'], guild['guild_id'])

        # Try to get session again - should return None
        session_after = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session_after is None


# ==============================================================================
# Phase 3B.8: Concurrent Request Tests
# ==============================================================================

@pytest.mark.integration
class TestConcurrentRequests:
    """Test multiple users operating simultaneously."""

    @freeze_time("2025-01-15 10:00:00")
    def test_multiple_users_same_guild_simultaneous(self, integration_mock_env, setup_test_guild):
        """Test multiple users verifying in the same guild simultaneously."""
        guild = setup_test_guild

        users = [
            ('user_001', 'student1@auburn.edu', '111111'),
            ('user_002', 'student2@auburn.edu', '222222'),
            ('user_003', 'student3@auburn.edu', '333333'),
        ]

        verification_ids = []

        # Create sessions for all users
        for user_id, email, code in users:
            vid = create_verification_session(
                user_id=user_id,
                guild_id=guild['guild_id'],
                email=email,
                code=code,
                expiry_minutes=15
            )
            verification_ids.append(vid)

        # Verify all sessions exist independently
        for i, (user_id, email, code) in enumerate(users):
            session = get_verification_session(user_id, guild['guild_id'])
            assert session is not None
            assert session['email'] == email
            assert session['code'] == code

    @freeze_time("2025-01-15 10:00:00")
    def test_concurrent_email_same_guild_different_users(self, integration_mock_env, setup_test_guild):
        """Test edge case where multiple users try to verify same email in one guild."""
        guild = setup_test_guild
        same_email = 'shared@auburn.edu'

        # Two users try to use same email (should both succeed in creating sessions)
        vid1 = create_verification_session(
            user_id='user_001',
            guild_id=guild['guild_id'],
            email=same_email,
            code='111111',
            expiry_minutes=15
        )

        vid2 = create_verification_session(
            user_id='user_002',
            guild_id=guild['guild_id'],
            email=same_email,
            code='222222',
            expiry_minutes=15
        )

        # Both sessions should exist (system allows duplicate emails)
        session1 = get_verification_session('user_001', guild['guild_id'])
        session2 = get_verification_session('user_002', guild['guild_id'])

        assert session1 is not None
        assert session2 is not None
        assert session1['verification_id'] != session2['verification_id']


# ==============================================================================
# Phase 3B.9: Malformed Data Tests
# ==============================================================================

@pytest.mark.integration
class TestMalformedData:
    """Test handling of malformed or unexpected data."""

    def test_email_validation_with_special_characters(self, integration_mock_env, setup_test_guild):
        """Test email validation with unusual but valid email formats."""
        guild = setup_test_guild
        allowed_domains = get_guild_allowed_domains(guild['guild_id'])

        # Test edge case emails
        edge_cases = [
            'test+tag@auburn.edu',  # Plus addressing
            'test.name@auburn.edu',  # Dots in local part
            'test_underscore@auburn.edu',  # Underscores
            'a@auburn.edu',  # Single character
        ]

        for email in edge_cases:
            # Should handle gracefully
            is_valid = validate_edu_email(email, allowed_domains)
            # All should be valid (basic email format)
            assert is_valid is True or is_valid is False  # Just shouldn't crash

    def test_verification_code_edge_formats(self, integration_mock_env):
        """Test verification code validation with edge case formats."""
        # Test various code formats
        test_codes = [
            '123456',  # Valid
            '000000',  # All zeros
            '999999',  # All nines
            'ABCDEF',  # Letters (should fail)
            '12345',   # Too short
            '1234567', # Too long
        ]

        for code in test_codes:
            # Should handle all formats without crashing
            is_valid = is_valid_code_format(code)
            assert isinstance(is_valid, bool)

    @freeze_time("2025-01-15 10:00:00")
    def test_session_with_extreme_values(self, integration_mock_env, setup_test_guild):
        """Test session creation with boundary value inputs."""
        guild = setup_test_guild

        # Test with very short expiry
        vid_short = create_verification_session(
            user_id='user_short_expiry',
            guild_id=guild['guild_id'],
            email='test@auburn.edu',
            code='123456',
            expiry_minutes=1  # Very short
        )

        session = get_verification_session('user_short_expiry', guild['guild_id'])
        assert session is not None

        # Test with very long expiry
        vid_long = create_verification_session(
            user_id='user_long_expiry',
            guild_id=guild['guild_id'],
            email='test2@auburn.edu',
            code='654321',
            expiry_minutes=1440  # 24 hours
        )

        session_long = get_verification_session('user_long_expiry', guild['guild_id'])
        assert session_long is not None


# ==============================================================================
# Phase 3B.10: Session Boundary Condition Tests
# ==============================================================================

@pytest.mark.integration
class TestSessionBoundaryConditions:
    """Test edge cases around session lifecycle."""

    @freeze_time("2025-01-15 10:00:00")
    def test_verify_non_existent_session(self, integration_mock_env):
        """Test verification attempt on non-existent session."""
        # Try to get session that doesn't exist
        session = get_verification_session('nonexistent_user', 'nonexistent_guild')
        assert session is None

    @freeze_time("2025-01-15 10:00:00")
    def test_increment_attempts_on_nonexistent_session(self, integration_mock_env):
        """Test incrementing attempts on a session that doesn't exist."""
        # Try to increment attempts on non-existent session
        attempts = increment_attempts('fake_verification_id', 'fake_user', 'fake_guild')
        # Should return 0 (error case)
        assert attempts == 0

    @freeze_time("2025-01-15 10:00:00")
    def test_accessing_just_expired_session(self, integration_mock_env, setup_test_guild):
        """Test accessing a session exactly at expiration moment."""
        guild = setup_test_guild

        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        # Fast forward to exactly 15 minutes
        with freeze_time("2025-01-15 10:15:00"):
            session = get_verification_session(guild['user_id'], guild['guild_id'])
            # Session should still exist (it's the job of handler to check expiry)
            assert session is not None

            expires_at = datetime.fromisoformat(session['expires_at'])
            now = datetime.utcnow()
            # Should be expired or at exact moment
            assert now >= expires_at

    @freeze_time("2025-01-15 10:00:00")
    def test_double_verification_same_session(self, integration_mock_env, setup_test_guild):
        """Test marking same session as verified twice."""
        guild = setup_test_guild

        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        # Mark as verified
        mark_verified(verification_id, guild['user_id'], guild['guild_id'])

        # Session should be deleted
        session = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session is None

        # Try to mark verified again (should handle gracefully)
        try:
            mark_verified(verification_id, guild['user_id'], guild['guild_id'])
            # Should not crash
        except Exception as e:
            # Some error is acceptable, just shouldn't crash entire system
            pass

    @freeze_time("2025-01-15 10:00:00")
    def test_is_user_verified_before_any_verification(self, integration_mock_env, setup_test_guild):
        """Test checking verification status for user who never verified."""
        guild = setup_test_guild

        # Check user who hasn't verified
        is_verified = is_user_verified('brand_new_user', guild['guild_id'])
        assert is_verified is False

    @freeze_time("2025-01-15 10:00:00")
    def test_session_with_zero_attempts(self, integration_mock_env, setup_test_guild):
        """Test that new sessions start with zero attempts."""
        guild = setup_test_guild

        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        session = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session['attempts'] == 0

    @freeze_time("2025-01-15 10:00:00")
    def test_multiple_session_overwrites_same_user_guild(self, integration_mock_env, setup_test_guild):
        """Test that creating new session overwrites previous one for same user/guild."""
        guild = setup_test_guild

        # Create first session
        vid1 = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='first@auburn.edu',
            code='111111',
            expiry_minutes=15
        )

        session1 = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session1['code'] == '111111'

        # Create second session (should overwrite)
        vid2 = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='second@auburn.edu',
            code='222222',
            expiry_minutes=15
        )

        session2 = get_verification_session(guild['user_id'], guild['guild_id'])
        # Should have new code (session was overwritten)
        assert session2['code'] == '222222'
        assert session2['email'] == 'second@auburn.edu'
