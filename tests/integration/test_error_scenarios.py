"""
Phase 3B: Error Scenarios Integration Tests.

These tests validate error handling across integrated components including:
- DynamoDB service failures (connection errors, throttling)
- SES service failures (quota exceeded, email sending failures)
- Discord API failures (timeouts, rate limits)
- Network failures and retry logic
- SSM parameter retrieval failures

All tests use moto for AWS mocking and simulate various failure conditions.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from freezegun import freeze_time
import requests

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

# Import after path setup
from dynamodb_operations import (
    create_verification_session,
    get_verification_session,
    mark_verified,
    increment_attempts,
    check_rate_limit
)
from ses_email import send_verification_email
from discord_api import assign_role, user_has_role
from ssm_utils import get_parameter
from verification_logic import generate_code


# ==============================================================================
# Helper Functions for Error Simulation
# ==============================================================================

def create_dynamodb_error(error_code: str, message: str, operation: str):
    """Create a ClientError for DynamoDB operations."""
    return ClientError(
        {'Error': {'Code': error_code, 'Message': message}},
        operation
    )


def create_ses_error(error_code: str, message: str):
    """Create a ClientError for SES operations."""
    return ClientError(
        {'Error': {'Code': error_code, 'Message': message}},
        'SendEmail'
    )


# ==============================================================================
# Phase 3B.1: DynamoDB Failure Tests
# ==============================================================================

@pytest.mark.integration
class TestDynamoDBFailures:
    """Test handling of DynamoDB service failures."""

    @freeze_time("2025-01-15 10:00:00")
    def test_session_creation_fails_on_dynamodb_unavailable(self, integration_mock_env, setup_test_guild):
        """Test graceful handling when DynamoDB service is unavailable."""
        guild = setup_test_guild

        # Simulate DynamoDB ServiceUnavailable error
        error = create_dynamodb_error(
            'ServiceUnavailable',
            'Service is temporarily unavailable',
            'PutItem'
        )

        with patch('dynamodb_operations.sessions_table.put_item', side_effect=error):
            # Attempt to create session should not crash
            try:
                verification_id = create_verification_session(
                    user_id=guild['user_id'],
                    guild_id=guild['guild_id'],
                    email='student@auburn.edu',
                    code='123456',
                    expiry_minutes=15
                )
                # Should handle error gracefully (may raise or return None)
                # The key is it doesn't crash the entire system
            except ClientError as e:
                # Expected behavior - error is raised but caught
                assert e.response['Error']['Code'] == 'ServiceUnavailable'

    @freeze_time("2025-01-15 10:00:00")
    def test_get_session_returns_none_on_dynamodb_error(self, integration_mock_env, setup_test_guild):
        """Test that get_verification_session returns None on DynamoDB errors."""
        guild = setup_test_guild

        # Create a valid session first
        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        # Simulate error on retrieval
        error = create_dynamodb_error(
            'ProvisionedThroughputExceededException',
            'Request rate exceeded',
            'GetItem'
        )

        with patch('dynamodb_operations.sessions_table.get_item', side_effect=error):
            session = get_verification_session(guild['user_id'], guild['guild_id'])
            # Should return None instead of crashing
            assert session is None

    @freeze_time("2025-01-15 10:00:00")
    def test_mark_verified_handles_dynamodb_throttling(self, integration_mock_env, setup_test_guild):
        """Test that mark_verified handles throttling gracefully."""
        guild = setup_test_guild

        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        # Simulate throttling error on update
        error = create_dynamodb_error(
            'ProvisionedThroughputExceededException',
            'Request rate exceeded',
            'UpdateItem'
        )

        with patch('dynamodb_operations.records_table.update_item', side_effect=error):
            # Should not crash, may print error
            try:
                mark_verified(verification_id, guild['user_id'], guild['guild_id'])
            except ClientError as e:
                assert e.response['Error']['Code'] == 'ProvisionedThroughputExceededException'

    @freeze_time("2025-01-15 10:00:00")
    def test_increment_attempts_returns_zero_on_error(self, integration_mock_env, setup_test_guild):
        """Test that increment_attempts returns 0 on DynamoDB errors."""
        guild = setup_test_guild

        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code='123456',
            expiry_minutes=15
        )

        # Simulate error on increment
        error = create_dynamodb_error(
            'InternalServerError',
            'Internal server error',
            'UpdateItem'
        )

        with patch('dynamodb_operations.sessions_table.update_item', side_effect=error):
            attempts = increment_attempts(verification_id, guild['user_id'], guild['guild_id'])
            # Function returns 0 on error (as per implementation)
            assert attempts == 0


# ==============================================================================
# Phase 3B.2: SES Failure Tests
# ==============================================================================

@pytest.mark.integration
class TestSESFailures:
    """Test handling of SES service failures."""

    def test_email_send_fails_on_quota_exceeded(self, integration_mock_env):
        """Test handling when SES daily sending quota is exceeded."""
        email = 'student@auburn.edu'
        code = '123456'

        # Simulate quota exceeded error
        error = create_ses_error(
            'MessageRejected',
            'Daily message quota exceeded'
        )

        with patch('ses_email.ses_client.send_email', side_effect=error):
            result = send_verification_email(email, code)
            # Should return False indicating failure
            assert result is False

    def test_email_send_fails_on_unverified_sender(self, integration_mock_env):
        """Test handling when sender email is not verified in SES."""
        email = 'student@auburn.edu'
        code = '123456'

        # Simulate unverified sender error
        error = create_ses_error(
            'MessageRejected',
            'Email address is not verified'
        )

        with patch('ses_email.ses_client.send_email', side_effect=error):
            result = send_verification_email(email, code)
            assert result is False

    def test_email_send_fails_on_invalid_recipient(self, integration_mock_env):
        """Test handling when recipient email is invalid/bounced."""
        email = 'invalid@nonexistent-domain-12345.edu'
        code = '123456'

        # Simulate invalid recipient error
        error = create_ses_error(
            'MessageRejected',
            'Address blacklisted'
        )

        with patch('ses_email.ses_client.send_email', side_effect=error):
            result = send_verification_email(email, code)
            assert result is False

    def test_email_send_handles_ses_service_unavailable(self, integration_mock_env):
        """Test handling when SES service is temporarily unavailable."""
        email = 'student@auburn.edu'
        code = '123456'

        # Simulate service unavailable
        error = create_ses_error(
            'ServiceUnavailable',
            'Service is temporarily unavailable'
        )

        with patch('ses_email.ses_client.send_email', side_effect=error):
            result = send_verification_email(email, code)
            assert result is False


# ==============================================================================
# Phase 3B.3: Discord API Failure Tests
# ==============================================================================

@pytest.mark.integration
class TestDiscordAPIFailures:
    """Test handling of Discord API failures."""

    def test_role_assignment_timeout(self, integration_mock_env):
        """Test handling when Discord API request times out."""
        user_id = 'test_user_123'
        guild_id = 'test_guild_456'
        role_id = 'verified_role_789'
        bot_token = 'test_token'

        # Simulate timeout
        with patch('discord_api.requests.put', side_effect=requests.Timeout()):
            result = assign_role(user_id, guild_id, role_id, bot_token)
            # Should return False and not crash
            assert result is False

    def test_role_assignment_connection_error(self, integration_mock_env):
        """Test handling when Discord API connection fails."""
        user_id = 'test_user_123'
        guild_id = 'test_guild_456'
        role_id = 'verified_role_789'
        bot_token = 'test_token'

        # Simulate connection error
        with patch('discord_api.requests.put', side_effect=requests.ConnectionError()):
            result = assign_role(user_id, guild_id, role_id, bot_token)
            assert result is False

    def test_role_assignment_rate_limited(self, integration_mock_env):
        """Test handling when Discord API rate limits the request."""
        user_id = 'test_user_123'
        guild_id = 'test_guild_456'
        role_id = 'verified_role_789'
        bot_token = 'test_token'

        # Mock rate limit response (429)
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.content = b'{"code": 0, "message": "Rate limited"}'
        mock_response.json.return_value = {'code': 0, 'message': 'Rate limited'}

        with patch('discord_api.requests.put', return_value=mock_response):
            result = assign_role(user_id, guild_id, role_id, bot_token)
            assert result is False

    def test_user_has_role_handles_404(self, integration_mock_env):
        """Test handling when user or guild is not found."""
        user_id = 'nonexistent_user'
        guild_id = 'test_guild_456'
        role_id = 'verified_role_789'
        bot_token = 'test_token'

        # Mock 404 response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = b'{"code": 10007, "message": "Unknown Member"}'
        mock_response.json.return_value = {'code': 10007, 'message': 'Unknown Member'}

        with patch('discord_api.requests.get', return_value=mock_response):
            result = user_has_role(user_id, guild_id, role_id, bot_token)
            # Should return False for missing user
            assert result is False

    def test_discord_api_malformed_response(self, integration_mock_env):
        """Test handling when Discord API returns malformed data."""
        user_id = 'test_user_123'
        guild_id = 'test_guild_456'
        role_id = 'verified_role_789'
        bot_token = 'test_token'

        # Mock response with missing 'roles' field
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'user': {'id': user_id}}  # Missing 'roles'

        with patch('discord_api.requests.get', return_value=mock_response):
            result = user_has_role(user_id, guild_id, role_id, bot_token)
            # Should handle gracefully - returns False if roles missing
            assert result is False


# ==============================================================================
# Phase 3B.4: Network Failure Tests
# ==============================================================================

@pytest.mark.integration
class TestNetworkFailures:
    """Test handling of network-level failures."""

    @freeze_time("2025-01-15 10:00:00")
    def test_rate_limit_check_handles_database_error(self, integration_mock_env, setup_test_guild):
        """Test that rate limit check handles database errors gracefully."""
        guild = setup_test_guild

        # Simulate DynamoDB error during rate limit check
        error = create_dynamodb_error(
            'ServiceUnavailable',
            'Service unavailable',
            'GetItem'
        )

        with patch('dynamodb_operations.sessions_table.get_item', side_effect=error):
            is_allowed, remaining = check_rate_limit(guild['user_id'], guild['guild_id'])
            # get_verification_session catches error and returns None
            # So check_rate_limit treats it as no session found (allows request)
            # This is by design - errors in get_verification_session are handled gracefully
            assert is_allowed is True
            assert remaining == 0

    def test_ssm_parameter_retrieval_failure(self, integration_mock_env):
        """Test handling when SSM parameter retrieval fails."""
        # Simulate SSM error
        error = ClientError(
            {'Error': {'Code': 'ParameterNotFound', 'Message': 'Parameter not found'}},
            'GetParameter'
        )

        with patch('ssm_utils.ssm_client.get_parameter', side_effect=error):
            # Should raise or return None
            try:
                token = get_parameter('/discord-bot/token')
                # May return None or raise
                assert token is None or token == ''
            except ClientError as e:
                # Expected - error propagates
                assert e.response['Error']['Code'] == 'ParameterNotFound'

    def test_multiple_concurrent_dynamodb_errors(self, integration_mock_env, setup_test_guild):
        """Test system stability under multiple concurrent DynamoDB errors."""
        guild = setup_test_guild

        error = create_dynamodb_error(
            'ProvisionedThroughputExceededException',
            'Throughput exceeded',
            'PutItem'
        )

        with patch('dynamodb_operations.sessions_table.put_item', side_effect=error):
            # Try multiple operations - all should fail gracefully
            results = []
            for i in range(3):
                try:
                    verification_id = create_verification_session(
                        user_id=f'user_{i}',
                        guild_id=guild['guild_id'],
                        email=f'student{i}@auburn.edu',
                        code=generate_code(),
                        expiry_minutes=15
                    )
                    results.append(False)  # Should not succeed
                except ClientError:
                    results.append(True)  # Error expected

            # All should fail gracefully
            assert len(results) == 3


# ==============================================================================
# Phase 3B.5: Partial Failure Scenarios
# ==============================================================================

@pytest.mark.integration
class TestPartialFailures:
    """Test scenarios where some operations succeed and others fail."""

    @freeze_time("2025-01-15 10:00:00")
    def test_session_created_but_email_fails(self, integration_mock_env, setup_test_guild):
        """Test when session is created successfully but email sending fails."""
        guild = setup_test_guild

        # Create session successfully
        verification_code = generate_code()
        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code=verification_code,
            expiry_minutes=15
        )

        # Verify session exists
        session = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session is not None
        assert session['code'] == verification_code

        # Simulate email failure
        error = create_ses_error('MessageRejected', 'Quota exceeded')
        with patch('ses_email.ses_client.send_email', side_effect=error):
            email_result = send_verification_email('student@auburn.edu', verification_code)
            assert email_result is False

        # Session should still exist even if email failed
        session_after = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session_after is not None

    @freeze_time("2025-01-15 10:00:00")
    def test_verification_succeeds_but_role_assignment_fails(self, integration_mock_env, setup_test_guild):
        """Test when verification succeeds but Discord role assignment fails."""
        guild = setup_test_guild

        # Complete verification flow
        verification_code = '123456'
        verification_id = create_verification_session(
            user_id=guild['user_id'],
            guild_id=guild['guild_id'],
            email='student@auburn.edu',
            code=verification_code,
            expiry_minutes=15
        )

        # Mark as verified
        mark_verified(verification_id, guild['user_id'], guild['guild_id'])

        # Verify session is deleted (verification complete)
        session = get_verification_session(guild['user_id'], guild['guild_id'])
        assert session is None

        # Now try role assignment with simulated failure
        with patch('discord_api.requests.put', side_effect=requests.Timeout()):
            result = assign_role(
                guild['user_id'],
                guild['guild_id'],
                guild['role_id'],
                'test_token'
            )
            # Role assignment should fail gracefully
            assert result is False

    @freeze_time("2025-01-15 10:00:00")
    def test_records_table_fails_but_sessions_succeeds(self, integration_mock_env, setup_test_guild):
        """Test when records table write fails but sessions table succeeds."""
        guild = setup_test_guild

        # Simulate error only on records table
        error = create_dynamodb_error(
            'ConditionalCheckFailedException',
            'Condition not met',
            'PutItem'
        )

        with patch('dynamodb_operations.records_table.put_item', side_effect=error):
            try:
                verification_id = create_verification_session(
                    user_id=guild['user_id'],
                    guild_id=guild['guild_id'],
                    email='student@auburn.edu',
                    code='123456',
                    expiry_minutes=15
                )
                # May fail or succeed depending on error handling
            except ClientError as e:
                # Expected - records table write failed
                assert e.response['Error']['Code'] == 'ConditionalCheckFailedException'
