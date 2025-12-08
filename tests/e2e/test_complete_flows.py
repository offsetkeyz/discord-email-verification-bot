"""
Phase 4A: End-to-End Complete Flow Tests.

These tests validate complete user journeys through the Discord Email Verification Bot:
- New user verification flows from button click to role assignment
- Admin setup workflows from command to configuration
- Multi-step error recovery scenarios
- Session expiration handling
- Rate limiting enforcement
- Cross-guild verification
- Domain validation
- Concurrent operations

All tests use the Lambda handler entry point and simulate realistic Discord interactions.
"""
import pytest
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from freezegun import freeze_time

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

# Import after path setup
from lambda_function import lambda_handler
from dynamodb_operations import (
    get_verification_session,
    is_user_verified,
    create_verification_session
)
from guild_config import save_guild_config, get_guild_config
from verification_logic import generate_code


# ==============================================================================
# Helper Functions
# ==============================================================================

def create_button_click_event(custom_id, user_id, guild_id):
    """Create API Gateway event for button click."""
    interaction = {
        'type': 3,  # MESSAGE_COMPONENT
        'data': {
            'custom_id': custom_id,
            'component_type': 2  # BUTTON
        },
        'member': {
            'user': {
                'id': user_id,
                'username': 'testuser'
            },
            'roles': []
        },
        'guild_id': guild_id
    }

    # Use current time for timestamp to pass verification window check
    timestamp = str(int(datetime.utcnow().timestamp()))

    return {
        'headers': {
            'x-signature-ed25519': 'mock_signature',
            'x-signature-timestamp': timestamp
        },
        'body': json.dumps(interaction)
    }


def create_email_modal_event(email, user_id, guild_id):
    """Create API Gateway event for email modal submission."""
    interaction = {
        'type': 5,  # MODAL_SUBMIT
        'data': {
            'custom_id': 'email_submission_modal',
            'components': [{
                'components': [{
                    'custom_id': 'edu_email',
                    'value': email
                }]
            }]
        },
        'member': {
            'user': {'id': user_id},
            'roles': []
        },
        'guild_id': guild_id
    }

    timestamp = str(int(datetime.utcnow().timestamp()))

    return {
        'headers': {
            'x-signature-ed25519': 'mock_signature',
            'x-signature-timestamp': timestamp
        },
        'body': json.dumps(interaction)
    }


def create_code_modal_event(code, user_id, guild_id):
    """Create API Gateway event for code modal submission."""
    interaction = {
        'type': 5,  # MODAL_SUBMIT
        'data': {
            'custom_id': 'code_submission_modal',
            'components': [{
                'components': [{
                    'custom_id': 'verification_code',
                    'value': code
                }]
            }]
        },
        'member': {
            'user': {'id': user_id},
            'roles': []
        },
        'guild_id': guild_id
    }

    timestamp = str(int(datetime.utcnow().timestamp()))

    return {
        'headers': {
            'x-signature-ed25519': 'mock_signature',
            'x-signature-timestamp': timestamp
        },
        'body': json.dumps(interaction)
    }


def create_setup_command_event(user_id, guild_id, is_admin=True):
    """Create API Gateway event for setup command."""
    permissions = str(0x8) if is_admin else str(0x10000000)  # ADMINISTRATOR or MANAGE_ROLES

    interaction = {
        'type': 2,  # APPLICATION_COMMAND
        'data': {
            'name': 'setup-email-verification',
            'type': 1
        },
        'member': {
            'user': {
                'id': user_id,
                'username': 'admin'
            },
            'permissions': permissions
        },
        'guild_id': guild_id
    }

    timestamp = str(int(datetime.utcnow().timestamp()))

    return {
        'headers': {
            'x-signature-ed25519': 'mock_signature',
            'x-signature-timestamp': timestamp
        },
        'body': json.dumps(interaction)
    }


# ==============================================================================
# Phase 4A.1: New User Verification Journey (3 tests)
# ==============================================================================

@pytest.mark.e2e
class TestNewUserVerificationJourney:
    """Test complete user verification flows from button click to role assignment."""

    @freeze_time("2025-01-15 10:00:00")
    def test_complete_happy_path_verification(self, integration_mock_env, setup_test_guild, lambda_context):
        """
        Test complete verification flow: button -> email -> code -> role.

        Flow:
        1. User clicks "Start Verification" button
        2. Modal appears with email input
        3. User submits email (student@auburn.edu)
        4. Email sent with verification code
        5. User submits code
        6. System validates and assigns role
        7. Session deleted, record created
        """
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True) as mock_assign, \
             patch('handlers.send_verification_email', return_value=True) as mock_email, \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Step 1: Click "Start Verification" button
            button_event = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            response1 = lambda_handler(button_event, lambda_context)

            assert response1['statusCode'] == 200
            body1 = json.loads(response1['body'])
            assert body1['type'] == 9  # MODAL
            assert 'email_submission_modal' in body1['data']['custom_id']

            # Step 2: Submit email
            email_event = create_email_modal_event('student@auburn.edu', guild['user_id'], guild['guild_id'])
            response2 = lambda_handler(email_event, lambda_context)

            assert response2['statusCode'] == 200
            assert mock_email.called

            # Verify session created
            session = get_verification_session(guild['user_id'], guild['guild_id'])
            assert session is not None
            assert session['email'] == 'student@auburn.edu'
            assert session['state'] == 'awaiting_code'
            code = session['code']

            # Step 3: Submit correct code
            code_event = create_code_modal_event(code, guild['user_id'], guild['guild_id'])
            response3 = lambda_handler(code_event, lambda_context)

            assert response3['statusCode'] == 200
            body3 = json.loads(response3['body'])
            assert '<�' in body3['data']['content'] or 'Verification complete' in body3['data']['content']

            # Verify role assigned
            assert mock_assign.called

            # Verify session deleted
            final_session = get_verification_session(guild['user_id'], guild['guild_id'])
            assert final_session is None

            # Verify record created
            assert is_user_verified(guild['user_id'], guild['guild_id']) is True

    @freeze_time("2025-01-15 10:00:00")
    def test_verification_with_alternate_domain(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test verification with configured alternate domain (test.edu)."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True) as mock_email, \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Start verification
            button_event = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            response1 = lambda_handler(button_event, lambda_context)
            assert response1['statusCode'] == 200

            # Submit test.edu email (configured in setup_test_guild)
            email_event = create_email_modal_event('student@test.edu', guild['user_id'], guild['guild_id'])
            response2 = lambda_handler(email_event, lambda_context)

            assert response2['statusCode'] == 200
            assert mock_email.called

            # Get code and verify
            session = get_verification_session(guild['user_id'], guild['guild_id'])
            assert session['email'] == 'student@test.edu'

            code_event = create_code_modal_event(session['code'], guild['user_id'], guild['guild_id'])
            response3 = lambda_handler(code_event, lambda_context)

            assert response3['statusCode'] == 200
            assert is_user_verified(guild['user_id'], guild['guild_id']) is True

    @freeze_time("2025-01-15 10:00:00")
    def test_already_verified_user_cannot_reverify(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test that already-verified users cannot start verification again."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Try to start verification when already has role
            button_event = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            response = lambda_handler(button_event, lambda_context)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert '✅' in body['data']['content']
            assert 'already have the verified role' in body['data']['content']


# ==============================================================================
# Phase 4A.2: Admin Setup Workflow (3 tests)
# ==============================================================================

@pytest.mark.e2e
class TestAdminSetupWorkflow:
    """Test complete admin setup flow from command to configuration."""

    def test_admin_can_run_setup_command(self, integration_mock_env, lambda_context):
        """Test that admin can initiate setup command."""
        with patch('lambda_function.verify_discord_signature', return_value=True):
            setup_event = create_setup_command_event('admin_123', 'guild_456', is_admin=True)
            response = lambda_handler(setup_event, lambda_context)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['type'] == 4  # CHANNEL_MESSAGE_WITH_SOURCE
            assert 'setup' in body['data']['content'].lower() or 'role' in body['data']['content'].lower()

    def test_non_admin_cannot_run_setup_command(self, integration_mock_env, lambda_context):
        """Test that non-admin users are blocked from setup."""
        with patch('lambda_function.verify_discord_signature', return_value=True):
            setup_event = create_setup_command_event('user_123', 'guild_456', is_admin=False)
            response = lambda_handler(setup_event, lambda_context)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            # Should show permission error
            assert 'permission' in body['data']['content'].lower() or 'admin' in body['data']['content'].lower()

    def test_guild_config_persists_after_setup(self, integration_mock_env, lambda_context):
        """Test that guild configuration is saved correctly."""
        guild_id = 'test_guild_789'

        # Manually save config (simulating complete setup flow)
        save_guild_config(
            guild_id=guild_id,
            role_id='role_999',
            channel_id='channel_888',
            setup_by_user_id='admin_123',
            allowed_domains=['test.edu'],
            custom_message='Test message'
        )

        # Retrieve and verify
        config = get_guild_config(guild_id)
        assert config is not None
        assert config['role_id'] == 'role_999'
        assert config['channel_id'] == 'channel_888'
        assert 'test.edu' in config['allowed_domains']


# ==============================================================================
# Phase 4A.3: Multi-Step Error Recovery (3 tests)
# ==============================================================================

@pytest.mark.e2e
class TestMultiStepErrorRecovery:
    """Test error recovery scenarios where users make mistakes and retry."""

    @freeze_time("2025-01-15 10:00:00")
    def test_user_retries_after_wrong_code(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test user can retry after entering wrong code (within max attempts)."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Start verification and submit email
            button_event = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            lambda_handler(button_event, lambda_context)

            email_event = create_email_modal_event('student@auburn.edu', guild['user_id'], guild['guild_id'])
            lambda_handler(email_event, lambda_context)

            session = get_verification_session(guild['user_id'], guild['guild_id'])
            correct_code = session['code']

            # Attempt 1: Wrong code
            wrong_code_event = create_code_modal_event('999999', guild['user_id'], guild['guild_id'])
            response1 = lambda_handler(wrong_code_event, lambda_context)

            body1 = json.loads(response1['body'])
            assert 'Incorrect code' in body1['data']['content']
            assert 'attempt' in body1['data']['content'].lower()

            # Session should still exist
            session = get_verification_session(guild['user_id'], guild['guild_id'])
            assert session is not None
            assert session['attempts'] == 1

            # Attempt 2: Correct code
            correct_code_event = create_code_modal_event(correct_code, guild['user_id'], guild['guild_id'])
            response2 = lambda_handler(correct_code_event, lambda_context)

            body2 = json.loads(response2['body'])
            assert '🎉' in body2['data']['content']
            assert is_user_verified(guild['user_id'], guild['guild_id']) is True

    @freeze_time("2025-01-15 10:00:00")
    def test_user_locked_out_after_max_attempts(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test user locked out after 5 failed code attempts."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Start and submit email
            button_event = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            lambda_handler(button_event, lambda_context)

            email_event = create_email_modal_event('student@auburn.edu', guild['user_id'], guild['guild_id'])
            lambda_handler(email_event, lambda_context)

            # Submit wrong code 3 times (MAX_VERIFICATION_ATTEMPTS = 3)
            for i in range(3):
                wrong_code_event = create_code_modal_event('999999', guild['user_id'], guild['guild_id'])
                response = lambda_handler(wrong_code_event, lambda_context)

                if i == 2:  # Third (last) attempt
                    body = json.loads(response['body'])
                    assert 'Too many failed attempts' in body['data']['content'] or 'start over' in body['data']['content']

            # Session should be deleted after max attempts
            session = get_verification_session(guild['user_id'], guild['guild_id'])
            assert session is None

    @freeze_time("2025-01-15 10:00:00")
    def test_user_restarts_after_invalid_email(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test user can restart verification after submitting invalid email."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Attempt 1: Invalid email domain
            button_event = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            lambda_handler(button_event, lambda_context)

            invalid_email_event = create_email_modal_event('student@gmail.com', guild['user_id'], guild['guild_id'])
            response1 = lambda_handler(invalid_email_event, lambda_context)

            body1 = json.loads(response1['body'])
            assert '❌' in body1['data']['content']
            assert 'valid email' in body1['data']['content'].lower() or 'allowed domain' in body1['data']['content'].lower()

            # Attempt 2: Valid email (after rate limit cooldown)
            with freeze_time("2025-01-15 10:02:00"):  # 2 minutes later
                button_event2 = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
                lambda_handler(button_event2, lambda_context)

                valid_email_event = create_email_modal_event('student@auburn.edu', guild['user_id'], guild['guild_id'])
                response2 = lambda_handler(valid_email_event, lambda_context)

                body2 = json.loads(response2['body'])
                assert '	' in body2['data']['content'] or 'sent' in body2['data']['content'].lower()


# ==============================================================================
# Phase 4A.4: Session Expiration Flow (2 tests)
# ==============================================================================

@pytest.mark.e2e
class TestSessionExpirationFlow:
    """Test handling of expired verification sessions."""

    @freeze_time("2025-01-15 10:00:00")
    def test_code_expires_after_15_minutes(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test that verification code expires after 15 minutes."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Start and submit email
            button_event = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            lambda_handler(button_event, lambda_context)

            email_event = create_email_modal_event('student@auburn.edu', guild['user_id'], guild['guild_id'])
            lambda_handler(email_event, lambda_context)

            session = get_verification_session(guild['user_id'], guild['guild_id'])
            code = session['code']

            # Time travel to 16 minutes later
            with freeze_time("2025-01-15 10:16:00"):
                code_event = create_code_modal_event(code, guild['user_id'], guild['guild_id'])
                response = lambda_handler(code_event, lambda_context)

                body = json.loads(response['body'])
                assert '❌' in body['data']['content']
                assert 'expired' in body['data']['content'].lower()

    @freeze_time("2025-01-15 10:00:00")
    def test_user_requests_new_code_after_expiration(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test user can get new code after previous one expires."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # First attempt - let it expire
            button_event = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            lambda_handler(button_event, lambda_context)

            email_event = create_email_modal_event('student@auburn.edu', guild['user_id'], guild['guild_id'])
            lambda_handler(email_event, lambda_context)

            # Time travel past expiration and beyond global rate limit
            with freeze_time("2025-01-15 10:20:00"):  # 20 minutes later
                # Start new verification
                button_event2 = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
                lambda_handler(button_event2, lambda_context)

                email_event2 = create_email_modal_event('student@auburn.edu', guild['user_id'], guild['guild_id'])
                lambda_handler(email_event2, lambda_context)

                # Get new code and verify
                session = get_verification_session(guild['user_id'], guild['guild_id'])
                assert session is not None

                code_event = create_code_modal_event(session['code'], guild['user_id'], guild['guild_id'])
                response = lambda_handler(code_event, lambda_context)

                body = json.loads(response['body'])
            assert '🎉' in body['data']['content']


# ==============================================================================
# Phase 4A.5: Rate Limiting Flow (2 tests)
# ==============================================================================

@pytest.mark.e2e
class TestRateLimitingFlow:
    """Test rate limiting enforcement across verification attempts."""

    @freeze_time("2025-01-15 10:00:00")
    def test_user_rate_limited_within_60_seconds(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test user blocked from starting new verification within 60 seconds."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # First request at 10:00
            button_event1 = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            response1 = lambda_handler(button_event1, lambda_context)
            assert response1['statusCode'] == 200

            email_event = create_email_modal_event('student@auburn.edu', guild['user_id'], guild['guild_id'])
            lambda_handler(email_event, lambda_context)

            # Second request at 10:00:30 (30 seconds later)
            with freeze_time("2025-01-15 10:00:30"):
                button_event2 = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
                response2 = lambda_handler(button_event2, lambda_context)

                body2 = json.loads(response2['body'])
            assert '⏱️' in body2['data']['content']

    @freeze_time("2025-01-15 10:00:00")
    def test_user_allowed_after_rate_limit_expires(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test user can verify again after rate limit expires."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # First request
            button_event1 = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            lambda_handler(button_event1, lambda_context)

            email_event1 = create_email_modal_event('student@auburn.edu', guild['user_id'], guild['guild_id'])
            lambda_handler(email_event1, lambda_context)

            # Second request after 6 minutes (past both 60s per-guild and 300s global)
            with freeze_time("2025-01-15 10:06:00"):
                button_event2 = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
                response2 = lambda_handler(button_event2, lambda_context)

                body2 = json.loads(response2['body'])
                # Should show modal, not rate limit message
                assert body2['type'] == 9  # MODAL


# ==============================================================================
# Phase 4A.6: Cross-Guild Verification (2 tests)
# ==============================================================================

@pytest.mark.e2e
class TestCrossGuildVerification:
    """Test verification status across multiple guilds."""

    @freeze_time("2025-01-15 10:00:00")
    def test_user_verified_in_guild_a_not_in_guild_b(self, integration_mock_env, lambda_context):
        """Test that verification is guild-specific."""
        user_id = 'user_123'
        guild_a = 'guild_aaa'
        guild_b = 'guild_bbb'

        # Setup both guilds
        save_guild_config(guild_a, 'role_a', 'channel_a', 'admin_1', ['auburn.edu'], 'Message A')
        save_guild_config(guild_b, 'role_b', 'channel_b', 'admin_2', ['auburn.edu'], 'Message B')

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Verify in Guild A
            button_event_a = create_button_click_event('start_verification', user_id, guild_a)
            lambda_handler(button_event_a, lambda_context)

            email_event_a = create_email_modal_event('student@auburn.edu', user_id, guild_a)
            lambda_handler(email_event_a, lambda_context)

            session_a = get_verification_session(user_id, guild_a)
            code_event_a = create_code_modal_event(session_a['code'], user_id, guild_a)
            lambda_handler(code_event_a, lambda_context)

            # Verify user verified in Guild A
            assert is_user_verified(user_id, guild_a) is True

            # Verify user NOT verified in Guild B
            assert is_user_verified(user_id, guild_b) is False

    @freeze_time("2025-01-15 10:00:00")
    def test_user_can_verify_in_multiple_guilds(self, integration_mock_env, lambda_context):
        """Test user can complete verification in multiple guilds."""
        user_id = 'user_456'
        guild_a = 'guild_xxx'
        guild_b = 'guild_yyy'

        # Setup both guilds
        save_guild_config(guild_a, 'role_a', 'channel_a', 'admin_1', ['test.edu'], 'Message A')
        save_guild_config(guild_b, 'role_b', 'channel_b', 'admin_2', ['test.edu'], 'Message B')

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Verify in Guild A
            button_event_a = create_button_click_event('start_verification', user_id, guild_a)
            lambda_handler(button_event_a, lambda_context)
            email_event_a = create_email_modal_event('student@test.edu', user_id, guild_a)
            lambda_handler(email_event_a, lambda_context)
            session_a = get_verification_session(user_id, guild_a)
            code_event_a = create_code_modal_event(session_a['code'], user_id, guild_a)
            lambda_handler(code_event_a, lambda_context)

            # Verify in Guild B (after rate limit)
            with freeze_time("2025-01-15 10:06:00"):
                button_event_b = create_button_click_event('start_verification', user_id, guild_b)
                lambda_handler(button_event_b, lambda_context)
                email_event_b = create_email_modal_event('student@test.edu', user_id, guild_b)
                lambda_handler(email_event_b, lambda_context)
                session_b = get_verification_session(user_id, guild_b)
                code_event_b = create_code_modal_event(session_b['code'], user_id, guild_b)
                lambda_handler(code_event_b, lambda_context)

            # Both should be verified
            assert is_user_verified(user_id, guild_a) is True
            assert is_user_verified(user_id, guild_b) is True


# ==============================================================================
# Phase 4A.7: Domain Validation Flow (2 tests)
# ==============================================================================

@pytest.mark.e2e
class TestDomainValidationFlow:
    """Test email domain validation and rejection."""

    @freeze_time("2025-01-15 10:00:00")
    def test_disallowed_domain_rejected(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test that non-allowed email domains are rejected."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            button_event = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            lambda_handler(button_event, lambda_context)

            # Try with gmail.com (not allowed)
            email_event = create_email_modal_event('student@gmail.com', guild['user_id'], guild['guild_id'])
            response = lambda_handler(email_event, lambda_context)

            body = json.loads(response['body'])
            assert '❌' in body['data']['content']
            assert 'valid email' in body['data']['content'].lower() or 'allowed domain' in body['data']['content'].lower()

            # Verify no session created
            session = get_verification_session(guild['user_id'], guild['guild_id'])
            assert session is None

    @freeze_time("2025-01-15 10:00:00")
    def test_allowed_domain_accepted(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test that allowed email domains are accepted."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            button_event = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            lambda_handler(button_event, lambda_context)

            # Try with auburn.edu (allowed)
            email_event = create_email_modal_event('student@auburn.edu', guild['user_id'], guild['guild_id'])
            response = lambda_handler(email_event, lambda_context)

            body = json.loads(response['body'])
            assert '	' in body['data']['content'] or 'sent' in body['data']['content'].lower()

            # Verify session created
            session = get_verification_session(guild['user_id'], guild['guild_id'])
            assert session is not None
            assert session['email'] == 'student@auburn.edu'


# ==============================================================================
# Phase 4A.8: Concurrent Operations (2 tests)
# ==============================================================================

@pytest.mark.e2e
class TestConcurrentOperations:
    """Test handling of concurrent user operations."""

    @freeze_time("2025-01-15 10:00:00")
    def test_user_cannot_have_multiple_sessions_same_guild(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test that starting new verification overwrites previous session."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Start first verification
            button_event1 = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
            lambda_handler(button_event1, lambda_context)

            email_event1 = create_email_modal_event('student1@auburn.edu', guild['user_id'], guild['guild_id'])
            lambda_handler(email_event1, lambda_context)

            session1 = get_verification_session(guild['user_id'], guild['guild_id'])
            code1 = session1['code']

            # Start second verification (after rate limit)
            with freeze_time("2025-01-15 10:06:00"):
                button_event2 = create_button_click_event('start_verification', guild['user_id'], guild['guild_id'])
                lambda_handler(button_event2, lambda_context)

                email_event2 = create_email_modal_event('student2@auburn.edu', guild['user_id'], guild['guild_id'])
                lambda_handler(email_event2, lambda_context)

                session2 = get_verification_session(guild['user_id'], guild['guild_id'])

                # Session should be new one
                assert session2['email'] == 'student2@auburn.edu'
                assert session2['code'] != code1

    @freeze_time("2025-01-15 10:00:00")
    def test_different_users_concurrent_verifications(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test multiple users can verify simultaneously without interference."""
        guild = setup_test_guild
        user1 = 'user_001'
        user2 = 'user_002'

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # User 1 starts verification
            button_event1 = create_button_click_event('start_verification', user1, guild['guild_id'])
            lambda_handler(button_event1, lambda_context)
            email_event1 = create_email_modal_event('user1@auburn.edu', user1, guild['guild_id'])
            lambda_handler(email_event1, lambda_context)

            # User 2 starts verification (concurrent)
            button_event2 = create_button_click_event('start_verification', user2, guild['guild_id'])
            lambda_handler(button_event2, lambda_context)
            email_event2 = create_email_modal_event('user2@auburn.edu', user2, guild['guild_id'])
            lambda_handler(email_event2, lambda_context)

            # Both should have separate sessions
            session1 = get_verification_session(user1, guild['guild_id'])
            session2 = get_verification_session(user2, guild['guild_id'])

            assert session1 is not None
            assert session2 is not None
            assert session1['email'] == 'user1@auburn.edu'
            assert session2['email'] == 'user2@auburn.edu'
            assert session1['code'] != session2['code']

            # Both complete verification
            code_event1 = create_code_modal_event(session1['code'], user1, guild['guild_id'])
            lambda_handler(code_event1, lambda_context)

            code_event2 = create_code_modal_event(session2['code'], user2, guild['guild_id'])
            lambda_handler(code_event2, lambda_context)

            # Both should be verified
            assert is_user_verified(user1, guild['guild_id']) is True
            assert is_user_verified(user2, guild['guild_id']) is True
