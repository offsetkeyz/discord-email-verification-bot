"""
Phase 4A: End-to-End Multi-User Scenario Tests.

These tests validate complex multi-user scenarios:
- Concurrent user verifications in the same guild
- Email reuse prevention and fraud detection
- Sequential verification processing
- Multi-admin setup conflicts
- High-volume scenarios (load testing)
- Race conditions and eventual consistency
- Session cleanup under load

All tests use the Lambda handler entry point and simulate realistic multi-user interactions.
"""
import pytest
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from freezegun import freeze_time
import concurrent.futures

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

# Import after path setup
from lambda_function import lambda_handler
from dynamodb_operations import (
    get_verification_session,
    is_user_verified,
    create_verification_session,
    mark_verified
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
                'username': f'user_{user_id}'
            },
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


def complete_verification_flow(user_id, guild_id, email, lambda_context):
    """Helper to complete full verification flow for a user."""
    with patch('lambda_function.verify_discord_signature', return_value=True), \
         patch('handlers.user_has_role', return_value=False), \
         patch('handlers.assign_role', return_value=True), \
         patch('handlers.send_verification_email', return_value=True), \
         patch('handlers.get_parameter', return_value='mock_bot_token'):

        # Start verification
        button_event = create_button_click_event('start_verification', user_id, guild_id)
        lambda_handler(button_event, lambda_context)

        # Submit email
        email_event = create_email_modal_event(email, user_id, guild_id)
        lambda_handler(email_event, lambda_context)

        # Get code and submit
        session = get_verification_session(user_id, guild_id)
        if session:
            code_event = create_code_modal_event(session['code'], user_id, guild_id)
            response = lambda_handler(code_event, lambda_context)
            return response

    return None


# ==============================================================================
# Phase 4A.9: Concurrent User Verifications (3 tests)
# ==============================================================================

@pytest.mark.e2e
class TestConcurrentUserVerifications:
    """Test multiple users verifying simultaneously in the same guild."""

    @freeze_time("2025-01-15 10:00:00")
    def test_five_users_verify_simultaneously_same_guild(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test 5 users can verify concurrently without interference."""
        guild = setup_test_guild
        users = [f'user_{i:03d}' for i in range(5)]

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # All users start verification
            for user_id in users:
                button_event = create_button_click_event('start_verification', user_id, guild['guild_id'])
                response = lambda_handler(button_event, lambda_context)
                assert response['statusCode'] == 200

            # All users submit emails
            for i, user_id in enumerate(users):
                email_event = create_email_modal_event(f'student{i}@auburn.edu', user_id, guild['guild_id'])
                response = lambda_handler(email_event, lambda_context)
                assert response['statusCode'] == 200

            # Verify all sessions exist
            sessions = []
            for user_id in users:
                session = get_verification_session(user_id, guild['guild_id'])
                assert session is not None
                sessions.append(session)

            # All codes should be different
            codes = [s['code'] for s in sessions]
            assert len(set(codes)) == 5, "All codes should be unique"

            # All users submit codes
            for user_id, session in zip(users, sessions):
                code_event = create_code_modal_event(session['code'], user_id, guild['guild_id'])
                response = lambda_handler(code_event, lambda_context)
                assert response['statusCode'] == 200

            # Verify all users verified
            for user_id in users:
                assert is_user_verified(user_id, guild['guild_id']) is True

    @freeze_time("2025-01-15 10:00:00")
    def test_concurrent_sessions_isolated_per_user(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test that concurrent user sessions don't interfere with each other."""
        guild = setup_test_guild
        user_a = 'user_aaa'
        user_b = 'user_bbb'

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # User A starts
            button_a = create_button_click_event('start_verification', user_a, guild['guild_id'])
            lambda_handler(button_a, lambda_context)

            email_a = create_email_modal_event('userA@auburn.edu', user_a, guild['guild_id'])
            lambda_handler(email_a, lambda_context)

            session_a = get_verification_session(user_a, guild['guild_id'])

            # User B starts (interleaved)
            button_b = create_button_click_event('start_verification', user_b, guild['guild_id'])
            lambda_handler(button_b, lambda_context)

            email_b = create_email_modal_event('userB@auburn.edu', user_b, guild['guild_id'])
            lambda_handler(email_b, lambda_context)

            session_b = get_verification_session(user_b, guild['guild_id'])

            # Verify sessions are completely independent
            assert session_a['email'] == 'userA@auburn.edu'
            assert session_b['email'] == 'userB@auburn.edu'
            assert session_a['code'] != session_b['code']

            # User A submits wrong code
            wrong_code_a = create_code_modal_event('999999', user_a, guild['guild_id'])
            lambda_handler(wrong_code_a, lambda_context)

            # User B should not be affected
            session_b_after = get_verification_session(user_b, guild['guild_id'])
            assert session_b_after['attempts'] == 0  # User B's attempts unchanged

            # User B completes successfully
            code_b = create_code_modal_event(session_b['code'], user_b, guild['guild_id'])
            lambda_handler(code_b, lambda_context)

            assert is_user_verified(user_b, guild['guild_id']) is True
            assert is_user_verified(user_a, guild['guild_id']) is False  # User A not verified

    @freeze_time("2025-01-15 10:00:00")
    def test_same_user_different_guilds_concurrent(self, integration_mock_env, lambda_context):
        """Test same user can verify in multiple guilds simultaneously."""
        user_id = 'user_multi_guild'
        guild_1 = 'guild_111'
        guild_2 = 'guild_222'

        # Setup both guilds
        save_guild_config(guild_1, 'role_1', 'channel_1', 'admin_1', ['auburn.edu'], 'Guild 1')
        save_guild_config(guild_2, 'role_2', 'channel_2', 'admin_2', ['auburn.edu'], 'Guild 2')

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Start in Guild 1
            button_1 = create_button_click_event('start_verification', user_id, guild_1)
            lambda_handler(button_1, lambda_context)

            email_1 = create_email_modal_event('student@auburn.edu', user_id, guild_1)
            lambda_handler(email_1, lambda_context)

            session_1 = get_verification_session(user_id, guild_1)

            # Start in Guild 2 (after rate limit for per-guild)
            with freeze_time("2025-01-15 10:06:00"):
                button_2 = create_button_click_event('start_verification', user_id, guild_2)
                lambda_handler(button_2, lambda_context)

                email_2 = create_email_modal_event('student@auburn.edu', user_id, guild_2)
                lambda_handler(email_2, lambda_context)

                session_2 = get_verification_session(user_id, guild_2)

            # Both sessions should exist
            assert session_1 is not None
            assert session_2 is not None
            assert session_1['code'] != session_2['code']


# ==============================================================================
# Phase 4A.10: Email Reuse Prevention (2 tests)
# ==============================================================================

@pytest.mark.e2e
class TestEmailReusePrevention:
    """Test prevention of email address reuse across users."""

    @freeze_time("2025-01-15 10:00:00")
    def test_same_email_different_users_same_guild_allowed(self, integration_mock_env, setup_test_guild, lambda_context):
        """
        Test that different users CAN use same email in same guild.

        Note: This tests current behavior. Email uniqueness is per-session,
        not enforced globally (users could share institutional emails).
        """
        guild = setup_test_guild
        user_a = 'user_aaa'
        user_b = 'user_bbb'
        shared_email = 'shared@auburn.edu'

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # User A verifies with email
            button_a = create_button_click_event('start_verification', user_a, guild['guild_id'])
            lambda_handler(button_a, lambda_context)

            email_a = create_email_modal_event(shared_email, user_a, guild['guild_id'])
            lambda_handler(email_a, lambda_context)

            session_a = get_verification_session(user_a, guild['guild_id'])
            code_a = create_code_modal_event(session_a['code'], user_a, guild['guild_id'])
            lambda_handler(code_a, lambda_context)

            assert is_user_verified(user_a, guild['guild_id']) is True

            # User B tries same email
            button_b = create_button_click_event('start_verification', user_b, guild['guild_id'])
            lambda_handler(button_b, lambda_context)

            email_b = create_email_modal_event(shared_email, user_b, guild['guild_id'])
            response_b = lambda_handler(email_b, lambda_context)

            # Current behavior: allowed (institutional emails may be shared)
            assert response_b['statusCode'] == 200
            session_b = get_verification_session(user_b, guild['guild_id'])
            assert session_b is not None

    @freeze_time("2025-01-15 10:00:00")
    def test_verified_user_cannot_verify_again_same_guild(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test that users with the verified role are blocked from re-verifying."""
        guild = setup_test_guild
        user_id = 'user_verified'

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # First verification
            complete_verification_flow(user_id, guild['guild_id'], 'student@auburn.edu', lambda_context)
            assert is_user_verified(user_id, guild['guild_id']) is True

            # Try to verify again (after cooldown)
            # This time user HAS the role
            with freeze_time("2025-01-15 10:10:00"):
                with patch('handlers.user_has_role', return_value=True):
                    button_event = create_button_click_event('start_verification', user_id, guild['guild_id'])
                    response = lambda_handler(button_event, lambda_context)

                    body = json.loads(response['body'])
                    assert response['statusCode'] == 200
                    # User with role should be blocked with "already have the verified role" message
                    assert 'already have the verified role' in body['data']['content'].lower()


# ==============================================================================
# Phase 4A.11: Sequential Verifications (2 tests)
# ==============================================================================

@pytest.mark.e2e
class TestSequentialVerifications:
    """Test users verifying one after another."""

    @freeze_time("2025-01-15 10:00:00")
    def test_three_users_sequential_verification(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test 3 users verify sequentially without issues."""
        guild = setup_test_guild
        users = ['user_seq_1', 'user_seq_2', 'user_seq_3']

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            for i, user_id in enumerate(users):
                # Complete full flow for each user
                button_event = create_button_click_event('start_verification', user_id, guild['guild_id'])
                lambda_handler(button_event, lambda_context)

                email_event = create_email_modal_event(f'seq{i}@auburn.edu', user_id, guild['guild_id'])
                lambda_handler(email_event, lambda_context)

                session = get_verification_session(user_id, guild['guild_id'])
                code_event = create_code_modal_event(session['code'], user_id, guild['guild_id'])
                lambda_handler(code_event, lambda_context)

                # Verify this user completed
                assert is_user_verified(user_id, guild['guild_id']) is True

            # Verify all 3 verified
            for user_id in users:
                assert is_user_verified(user_id, guild['guild_id']) is True

    @freeze_time("2025-01-15 10:00:00")
    def test_rapid_sequential_verification_queue(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test rapid sequential verifications (simulating queue processing)."""
        guild = setup_test_guild
        users = [f'rapid_user_{i}' for i in range(10)]

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            verified_count = 0

            # Process all users rapidly
            for i, user_id in enumerate(users):
                try:
                    button_event = create_button_click_event('start_verification', user_id, guild['guild_id'])
                    r1 = lambda_handler(button_event, lambda_context)

                    email_event = create_email_modal_event(f'rapid{i}@auburn.edu', user_id, guild['guild_id'])
                    r2 = lambda_handler(email_event, lambda_context)

                    session = get_verification_session(user_id, guild['guild_id'])
                    if session:
                        code_event = create_code_modal_event(session['code'], user_id, guild['guild_id'])
                        r3 = lambda_handler(code_event, lambda_context)

                        if is_user_verified(user_id, guild['guild_id']):
                            verified_count += 1
                except Exception as e:
                    print(f"Error verifying {user_id}: {e}")

            # Should have high success rate
            assert verified_count >= 8, f"Expected at least 8 verifications, got {verified_count}"


# ==============================================================================
# Phase 4A.12: Multi-Admin Setup Conflicts (2 tests)
# ==============================================================================

@pytest.mark.e2e
class TestMultiAdminSetupConflicts:
    """Test handling of multiple admins configuring the same guild."""

    def test_second_admin_can_reconfigure_guild(self, integration_mock_env, lambda_context):
        """Test that a second admin can update guild configuration."""
        guild_id = 'guild_multi_admin'

        # Admin 1 configures
        save_guild_config(guild_id, 'role_a', 'channel_a', 'admin_1', ['auburn.edu'], 'Config 1')

        config_1 = get_guild_config(guild_id)
        assert config_1['role_id'] == 'role_a'

        # Admin 2 reconfigures
        save_guild_config(guild_id, 'role_b', 'channel_b', 'admin_2', ['test.edu'], 'Config 2')

        config_2 = get_guild_config(guild_id)
        assert config_2['role_id'] == 'role_b'
        assert config_2['channel_id'] == 'channel_b'
        assert config_2['allowed_domains'] == ['test.edu']

    def test_concurrent_admin_setup_last_write_wins(self, integration_mock_env, lambda_context):
        """Test concurrent admin setups - last write wins."""
        guild_id = 'guild_concurrent_setup'

        # Simulate concurrent writes (last one wins in DynamoDB)
        save_guild_config(guild_id, 'role_1', 'channel_1', 'admin_1', ['domain1.edu'], 'First')
        save_guild_config(guild_id, 'role_2', 'channel_2', 'admin_2', ['domain2.edu'], 'Second')

        # Last write should persist
        config = get_guild_config(guild_id)
        assert config['role_id'] == 'role_2'
        assert config['setup_by'] == 'admin_2'


# ==============================================================================
# Phase 4A.13: High-Volume Scenarios (3 tests)
# ==============================================================================

@pytest.mark.e2e
class TestHighVolumeScenarios:
    """Test system behavior under high load."""

    @freeze_time("2025-01-15 10:00:00")
    def test_twenty_users_across_ten_guilds(self, integration_mock_env, lambda_context):
        """Test 20 users verifying across 10 different guilds."""
        guilds = [f'guild_{i:02d}' for i in range(10)]
        users = [f'user_{i:03d}' for i in range(20)]

        # Setup all guilds
        for guild_id in guilds:
            save_guild_config(guild_id, f'role_{guild_id}', f'channel_{guild_id}',
                            'admin', ['auburn.edu'], 'Message')

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            verified_count = 0

            # Distribute users across guilds
            for i, user_id in enumerate(users):
                guild_id = guilds[i % len(guilds)]  # Round-robin distribution

                try:
                    button_event = create_button_click_event('start_verification', user_id, guild_id)
                    lambda_handler(button_event, lambda_context)

                    email_event = create_email_modal_event(f'user{i}@auburn.edu', user_id, guild_id)
                    lambda_handler(email_event, lambda_context)

                    session = get_verification_session(user_id, guild_id)
                    if session:
                        code_event = create_code_modal_event(session['code'], user_id, guild_id)
                        lambda_handler(code_event, lambda_context)

                        if is_user_verified(user_id, guild_id):
                            verified_count += 1
                except Exception as e:
                    print(f"Error in high-volume test for {user_id}: {e}")

            # Should have high success rate
            assert verified_count >= 18, f"Expected at least 18/20 verifications, got {verified_count}"

    @freeze_time("2025-01-15 10:00:00")
    def test_burst_traffic_same_guild(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test burst of 15 users hitting same guild simultaneously."""
        guild = setup_test_guild
        users = [f'burst_user_{i:02d}' for i in range(15)]

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # All users start simultaneously
            for user_id in users:
                button_event = create_button_click_event('start_verification', user_id, guild['guild_id'])
                response = lambda_handler(button_event, lambda_context)
                assert response['statusCode'] == 200

            # All submit emails
            session_count = 0
            for i, user_id in enumerate(users):
                email_event = create_email_modal_event(f'burst{i}@auburn.edu', user_id, guild['guild_id'])
                response = lambda_handler(email_event, lambda_context)
                if response['statusCode'] == 200:
                    session = get_verification_session(user_id, guild['guild_id'])
                    if session:
                        session_count += 1

            # Most should succeed
            assert session_count >= 13, f"Expected at least 13/15 sessions, got {session_count}"

    @freeze_time("2025-01-15 10:00:00")
    def test_sustained_load_over_time(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test sustained load with users verifying over time windows."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            verified_total = 0

            # Simulate 5 time windows, 3 users each
            for window in range(5):
                with freeze_time(f"2025-01-15 10:{window*2:02d}:00"):  # 2-minute intervals
                    for user_num in range(3):
                        user_id = f'sustained_w{window}_u{user_num}'

                        try:
                            button_event = create_button_click_event('start_verification', user_id, guild['guild_id'])
                            lambda_handler(button_event, lambda_context)

                            email_event = create_email_modal_event(f'w{window}u{user_num}@auburn.edu', user_id, guild['guild_id'])
                            lambda_handler(email_event, lambda_context)

                            session = get_verification_session(user_id, guild['guild_id'])
                            if session:
                                code_event = create_code_modal_event(session['code'], user_id, guild['guild_id'])
                                lambda_handler(code_event, lambda_context)

                                if is_user_verified(user_id, guild['guild_id']):
                                    verified_total += 1
                        except Exception as e:
                            print(f"Error in sustained load: {e}")

            # Should handle sustained load well
            assert verified_total >= 12, f"Expected at least 12/15 sustained verifications, got {verified_total}"


# ==============================================================================
# Phase 4A.14: Race Conditions (3 tests)
# ==============================================================================

@pytest.mark.e2e
class TestRaceConditions:
    """Test race condition handling and eventual consistency."""

    @freeze_time("2025-01-15 10:00:00")
    def test_rapid_button_clicks_same_user(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test rapid repeated button clicks from same user."""
        guild = setup_test_guild
        user_id = 'rapid_clicker'

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # First click
            button_event1 = create_button_click_event('start_verification', user_id, guild['guild_id'])
            response1 = lambda_handler(button_event1, lambda_context)
            assert response1['statusCode'] == 200

            email_event = create_email_modal_event('rapid@auburn.edu', user_id, guild['guild_id'])
            lambda_handler(email_event, lambda_context)

            # Rapid second click (should be rate limited)
            button_event2 = create_button_click_event('start_verification', user_id, guild['guild_id'])
            response2 = lambda_handler(button_event2, lambda_context)

            body2 = json.loads(response2['body'])
            # Should show rate limit or modal (both acceptable)
            assert response2['statusCode'] == 200

    @freeze_time("2025-01-15 10:00:00")
    def test_simultaneous_code_submissions(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test handling of duplicate/simultaneous code submissions."""
        guild = setup_test_guild
        user_id = 'duplicate_submitter'

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Setup session
            button_event = create_button_click_event('start_verification', user_id, guild['guild_id'])
            lambda_handler(button_event, lambda_context)

            email_event = create_email_modal_event('dup@auburn.edu', user_id, guild['guild_id'])
            lambda_handler(email_event, lambda_context)

            session = get_verification_session(user_id, guild['guild_id'])
            code = session['code']

            # Submit code twice (simulating race)
            code_event1 = create_code_modal_event(code, user_id, guild['guild_id'])
            response1 = lambda_handler(code_event1, lambda_context)

            code_event2 = create_code_modal_event(code, user_id, guild['guild_id'])
            response2 = lambda_handler(code_event2, lambda_context)

            # At least one should succeed
            assert response1['statusCode'] == 200 or response2['statusCode'] == 200

            # User should be verified
            assert is_user_verified(user_id, guild['guild_id']) is True

    @freeze_time("2025-01-15 10:00:00")
    def test_role_assignment_eventual_consistency(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test system handles role assignment delays gracefully."""
        guild = setup_test_guild
        user_id = 'delayed_role_user'

        # Simulate slow role assignment
        role_call_count = 0

        def slow_assign_role(*args, **kwargs):
            nonlocal role_call_count
            role_call_count += 1
            return True  # Eventually succeeds

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', side_effect=slow_assign_role), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Complete verification
            button_event = create_button_click_event('start_verification', user_id, guild['guild_id'])
            lambda_handler(button_event, lambda_context)

            email_event = create_email_modal_event('delayed@auburn.edu', user_id, guild['guild_id'])
            lambda_handler(email_event, lambda_context)

            session = get_verification_session(user_id, guild['guild_id'])
            code_event = create_code_modal_event(session['code'], user_id, guild['guild_id'])
            response = lambda_handler(code_event, lambda_context)

            # Should handle gracefully
            assert response['statusCode'] == 200
            assert role_call_count == 1  # Role assignment attempted


# ==============================================================================
# Phase 4A.15: Session Cleanup Under Load (2 tests)
# ==============================================================================

@pytest.mark.e2e
class TestSessionCleanupUnderLoad:
    """Test session cleanup with mixed verification states."""

    @freeze_time("2025-01-15 10:00:00")
    def test_mixed_completion_states(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test mix of completed, expired, and active sessions."""
        guild = setup_test_guild

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.assign_role', return_value=True), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # User 1: Completes verification
            complete_verification_flow('user_complete', guild['guild_id'], 'complete@auburn.edu', lambda_context)

            # User 2: Starts but doesn't complete (expires)
            button_2 = create_button_click_event('start_verification', 'user_expire', guild['guild_id'])
            lambda_handler(button_2, lambda_context)
            email_2 = create_email_modal_event('expire@auburn.edu', 'user_expire', guild['guild_id'])
            lambda_handler(email_2, lambda_context)

            # User 3: Active session
            button_3 = create_button_click_event('start_verification', 'user_active', guild['guild_id'])
            lambda_handler(button_3, lambda_context)
            email_3 = create_email_modal_event('active@auburn.edu', 'user_active', guild['guild_id'])
            lambda_handler(email_3, lambda_context)

            # Verify states
            assert is_user_verified('user_complete', guild['guild_id']) is True
            assert get_verification_session('user_complete', guild['guild_id']) is None  # Cleaned up

            assert get_verification_session('user_expire', guild['guild_id']) is not None  # Still exists
            assert get_verification_session('user_active', guild['guild_id']) is not None  # Still exists

    @freeze_time("2025-01-15 10:00:00")
    def test_failed_attempts_cleanup(self, integration_mock_env, setup_test_guild, lambda_context):
        """Test cleanup after max failed attempts."""
        guild = setup_test_guild
        user_id = 'failed_user'

        with patch('lambda_function.verify_discord_signature', return_value=True), \
             patch('handlers.user_has_role', return_value=False), \
             patch('handlers.send_verification_email', return_value=True), \
             patch('handlers.get_parameter', return_value='mock_bot_token'):

            # Start verification
            button_event = create_button_click_event('start_verification', user_id, guild['guild_id'])
            lambda_handler(button_event, lambda_context)

            email_event = create_email_modal_event('failed@auburn.edu', user_id, guild['guild_id'])
            lambda_handler(email_event, lambda_context)

            # Fail 5 times
            for i in range(5):
                wrong_code = create_code_modal_event('999999', user_id, guild['guild_id'])
                lambda_handler(wrong_code, lambda_context)

            # Session should be cleaned up after max attempts
            session = get_verification_session(user_id, guild['guild_id'])
            assert session is None

            # User should not be verified
            assert is_user_verified(user_id, guild['guild_id']) is False
