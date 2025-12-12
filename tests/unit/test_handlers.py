"""
Unit tests for lambda/handlers.py module.

Tests the core verification flow handlers including:
- PING handler for Discord endpoint verification
- Button click routing (start verification, submit code)
- Start verification flow with security checks
- Email submission and validation
- Code verification with attempt tracking
- Modal routing and helpers
- Error handling and edge cases
"""
import pytest
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
from decimal import Decimal

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

from handlers import (
    handle_ping,
    handle_button_click,
    handle_start_verification,
    handle_modal_submit,
    handle_email_submission,
    handle_code_verification,
    show_code_modal,
    ephemeral_response,
    error_response
)
from discord_interactions import InteractionResponseType, MessageFlags, ComponentType, ButtonStyle


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def sample_user():
    """Sample Discord user data."""
    return {
        'id': '789012',
        'username': 'testuser',
        'discriminator': '1234'
    }


@pytest.fixture
def sample_member(sample_user):
    """Sample Discord member object."""
    return {
        'user': sample_user,
        'roles': []
    }


@pytest.fixture
def sample_interaction(sample_member):
    """Sample Discord interaction payload."""
    return {
        'type': 3,  # MESSAGE_COMPONENT
        'guild_id': '123456',
        'channel_id': '999888',
        'member': sample_member,
        'data': {}
    }


@pytest.fixture
def sample_guild_config():
    """Sample guild configuration."""
    return {
        'guild_id': '123456',
        'role_id': '111222',
        'channel_id': '999888',
        'allowed_domains': ['auburn.edu', 'student.sans.edu'],
        'custom_message': 'Click to verify!'
    }


@pytest.fixture
def sample_verification_session():
    """Sample verification session."""
    now = datetime.utcnow()
    return {
        'user_id': '789012',
        'guild_id': '123456',
        'email': 'test@auburn.edu',
        'code': '123456',
        'verification_id': 'test-verification-id-001',
        'attempts': 0,
        'state': 'awaiting_code',
        'created_at': now.isoformat(),
        'expires_at': (now + timedelta(minutes=15)).isoformat(),
        'ttl': int((now + timedelta(hours=24)).timestamp())
    }


# ==============================================================================
# 1. PING Handler Tests (1 test)
# ==============================================================================

@pytest.mark.unit
def test_handle_ping_returns_pong_response():
    """Test PING interaction returns type 1 (PONG) response."""
    response = handle_ping()

    assert response['statusCode'] == 200
    assert 'Content-Type' in response['headers']
    assert response['headers']['Content-Type'] == 'application/json'

    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.PONG


# ==============================================================================
# 2. Button Click Routing Tests (3 tests)
# ==============================================================================

@pytest.mark.unit
@patch('handlers.handle_start_verification')
def test_handle_button_click_start_verification(mock_start, sample_interaction):
    """Test button click routes to start_verification for start_verification button."""
    sample_interaction['data']['custom_id'] = 'start_verification'
    mock_start.return_value = {'statusCode': 200, 'body': '{}'}

    response = handle_button_click(sample_interaction)

    assert response['statusCode'] == 200
    mock_start.assert_called_once_with('789012', '123456')


@pytest.mark.unit
@patch('handlers.show_code_modal')
def test_handle_button_click_submit_code(mock_show_code, sample_interaction):
    """Test button click routes to code submission for submit_code button."""
    sample_interaction['data']['custom_id'] = 'submit_code'
    mock_show_code.return_value = {'statusCode': 200, 'body': '{}'}

    response = handle_button_click(sample_interaction)

    assert response['statusCode'] == 200
    mock_show_code.assert_called_once_with('789012', '123456')


@pytest.mark.unit
def test_handle_button_click_unknown_action(sample_interaction):
    """Test button click returns error for unknown button custom_id."""
    sample_interaction['data']['custom_id'] = 'unknown_button_action'

    response = handle_button_click(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Unknown button action' in body['data']['content']


# ==============================================================================
# 3. Start Verification Flow Tests (8 tests)
# ==============================================================================

@pytest.mark.unit
@patch('handlers.is_guild_configured')
def test_start_verification_unconfigured_guild(mock_configured):
    """Test start verification rejects requests from unconfigured guilds."""
    mock_configured.return_value = False

    response = handle_start_verification('789012', '123456')

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'hasn\'t been configured yet' in body['data']['content']
    assert '/setup' in body['data']['content']


@pytest.mark.unit
@patch('handlers.is_guild_configured')
@patch('handlers.get_guild_role_id')
@patch('handlers.get_parameter')
@patch('handlers.user_has_role')
def test_start_verification_user_already_has_role(mock_has_role, mock_param, mock_role_id, mock_configured):
    """Test start verification rejects users who already have verified role."""
    mock_configured.return_value = True
    mock_role_id.return_value = '111222'
    mock_param.return_value = 'test_bot_token'
    mock_has_role.return_value = True

    response = handle_start_verification('789012', '123456')

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'already have the verified role' in body['data']['content']
    mock_has_role.assert_called_once_with('789012', '123456', '111222', 'test_bot_token')


@pytest.mark.unit
@patch('handlers.is_guild_configured')
@patch('handlers.get_guild_role_id')
@patch('handlers.get_parameter')
@patch('handlers.user_has_role')
@patch('handlers.is_user_verified')
@patch('handlers.check_rate_limit')
def test_start_verification_already_verified_in_db(mock_rate_limit, mock_verified, mock_has_role, mock_param, mock_role_id, mock_configured):
    """Test start verification allows re-verification if user doesn't have role."""
    mock_configured.return_value = True
    mock_role_id.return_value = '111222'
    mock_param.return_value = 'test_bot_token'
    mock_has_role.return_value = False
    mock_verified.return_value = True  # User is in DB but doesn't have role
    mock_rate_limit.return_value = (True, 0)  # Not rate limited

    response = handle_start_verification('789012', '123456')

    # Should show email modal (allow re-verification)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.MODAL
    # Database check is no longer performed - only role check matters
    mock_verified.assert_not_called()


@pytest.mark.unit
@patch('handlers.is_guild_configured')
@patch('handlers.get_guild_role_id')
@patch('handlers.get_parameter')
@patch('handlers.user_has_role')
@patch('handlers.is_user_verified')
@patch('handlers.check_rate_limit')
def test_start_verification_rate_limited(mock_rate_limit, mock_verified, mock_has_role, mock_param, mock_role_id, mock_configured):
    """Test start verification enforces rate limiting."""
    mock_configured.return_value = True
    mock_role_id.return_value = '111222'
    mock_param.return_value = 'test_bot_token'
    mock_has_role.return_value = False
    mock_verified.return_value = False
    mock_rate_limit.return_value = (False, 45)  # Rate limited, 45 seconds remaining

    response = handle_start_verification('789012', '123456')

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Please wait 45 seconds' in body['data']['content']
    assert 'cooldown prevents spam' in body['data']['content']
    mock_rate_limit.assert_called_once_with('789012', '123456', cooldown_seconds=60)


@pytest.mark.unit
@patch('handlers.is_guild_configured')
@patch('handlers.get_guild_role_id')
@patch('handlers.get_parameter')
@patch('handlers.user_has_role')
@patch('handlers.is_user_verified')
@patch('handlers.check_rate_limit')
def test_start_verification_shows_email_modal(mock_rate_limit, mock_verified, mock_has_role, mock_param, mock_role_id, mock_configured):
    """Test start verification shows email modal on success path."""
    mock_configured.return_value = True
    mock_role_id.return_value = '111222'
    mock_param.return_value = 'test_bot_token'
    mock_has_role.return_value = False
    mock_verified.return_value = False
    mock_rate_limit.return_value = (True, 0)  # Allowed

    response = handle_start_verification('789012', '123456')

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.MODAL
    assert body['data']['custom_id'] == 'email_submission_modal'
    assert body['data']['title'] == 'Email Verification'

    # Verify modal has email input component
    components = body['data']['components']
    assert len(components) == 1
    assert components[0]['type'] == ComponentType.ACTION_ROW
    assert components[0]['components'][0]['custom_id'] == 'edu_email'
    assert components[0]['components'][0]['type'] == ComponentType.TEXT_INPUT
    assert components[0]['components'][0]['required'] is True


@pytest.mark.unit
@patch('handlers.is_guild_configured')
@patch('handlers.get_guild_role_id')
def test_start_verification_config_error(mock_role_id, mock_configured):
    """Test start verification handles configuration fetch errors."""
    mock_configured.return_value = True
    mock_role_id.side_effect = Exception("DynamoDB error")

    response = handle_start_verification('789012', '123456')

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Configuration error' in body['data']['content']
    assert 'administrator' in body['data']['content']


@pytest.mark.unit
@patch('handlers.is_guild_configured')
@patch('handlers.get_guild_role_id')
@patch('handlers.get_parameter')
@patch('handlers.user_has_role')
def test_start_verification_role_check_api_error(mock_has_role, mock_param, mock_role_id, mock_configured):
    """Test start verification handles Discord API errors during role check."""
    mock_configured.return_value = True
    mock_role_id.return_value = '111222'
    mock_param.return_value = 'test_bot_token'
    mock_has_role.side_effect = Exception("Discord API error")

    # Should raise the exception (not caught at this level)
    with pytest.raises(Exception) as exc_info:
        handle_start_verification('789012', '123456')

    assert "Discord API error" in str(exc_info.value)


@pytest.mark.unit
@patch('handlers.is_guild_configured')
@patch('handlers.get_guild_role_id')
@patch('handlers.get_parameter')
@patch('handlers.user_has_role')
@patch('handlers.is_user_verified')
@patch('handlers.check_rate_limit')
def test_start_verification_success_path(mock_rate_limit, mock_verified, mock_has_role, mock_param, mock_role_id, mock_configured):
    """Test full happy path through start verification flow."""
    # Arrange - all checks pass
    mock_configured.return_value = True
    mock_role_id.return_value = '111222'
    mock_param.return_value = 'test_bot_token'
    mock_has_role.return_value = False
    mock_verified.return_value = False
    mock_rate_limit.return_value = (True, 0)

    # Act
    response = handle_start_verification('789012', '123456')

    # Assert - modal displayed
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.MODAL

    # Verify all security checks were performed
    mock_configured.assert_called_once_with('123456')
    mock_role_id.assert_called_once_with('123456')
    mock_has_role.assert_called_once()
    # Database verification check is no longer performed
    mock_verified.assert_not_called()
    mock_rate_limit.assert_called_once()


# ==============================================================================
# 4. Email Submission Tests (7 tests)
# ==============================================================================

@pytest.mark.unit
@patch('handlers.get_guild_allowed_domains')
@patch('handlers.validate_edu_email')
@patch('handlers.generate_code')
@patch('handlers.create_verification_session')
@patch('handlers.send_verification_email')
def test_email_submission_valid_domain(mock_send_email, mock_create_session, mock_gen_code, mock_validate, mock_domains, sample_interaction):
    """Test email submission succeeds with valid domain."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'test@auburn.edu'}]}
    ]
    mock_domains.return_value = ['auburn.edu', 'student.sans.edu']
    mock_validate.return_value = True
    mock_gen_code.return_value = '123456'
    mock_create_session.return_value = 'verification-id-001'
    mock_send_email.return_value = True

    # Act
    response = handle_email_submission(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE
    assert 'sent a verification code' in body['data']['content']
    assert 'test@auburn.edu' in body['data']['content']
    assert body['data']['flags'] == MessageFlags.EPHEMERAL

    # Verify components contain Submit Code button
    components = body['data']['components']
    assert len(components) == 1
    assert components[0]['components'][0]['custom_id'] == 'submit_code'
    assert components[0]['components'][0]['label'] == 'Submit Code'

    mock_validate.assert_called_once_with('test@auburn.edu', ['auburn.edu', 'student.sans.edu'])
    mock_create_session.assert_called_once_with('789012', '123456', 'test@auburn.edu', '123456')
    mock_send_email.assert_called_once_with('test@auburn.edu', '123456')


@pytest.mark.unit
@patch('handlers.get_guild_allowed_domains')
@patch('handlers.validate_edu_email')
def test_email_submission_invalid_domain(mock_validate, mock_domains, sample_interaction):
    """Test email submission rejects emails from disallowed domains."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'test@gmail.com'}]}
    ]
    mock_domains.return_value = ['auburn.edu', 'student.sans.edu']
    mock_validate.return_value = False

    # Act
    response = handle_email_submission(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'doesn\'t appear to be a valid email' in body['data']['content']
    assert '@auburn.edu' in body['data']['content']
    assert '@student.sans.edu' in body['data']['content']


@pytest.mark.unit
@patch('handlers.get_guild_allowed_domains')
@patch('handlers.validate_edu_email')
@patch('handlers.generate_code')
@patch('handlers.create_verification_session')
@patch('handlers.send_verification_email')
@patch('handlers.delete_session')
def test_email_submission_email_send_failure(mock_delete, mock_send_email, mock_create_session, mock_gen_code, mock_validate, mock_domains, sample_interaction):
    """Test email submission handles SES send failures."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'test@auburn.edu'}]}
    ]
    mock_domains.return_value = ['auburn.edu']
    mock_validate.return_value = True
    mock_gen_code.return_value = '123456'
    mock_create_session.return_value = 'verification-id-001'
    mock_send_email.return_value = False  # Email send failed

    # Act
    response = handle_email_submission(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Failed to send verification email' in body['data']['content']
    assert 'sandbox mode' in body['data']['content']

    # Verify session was cleaned up
    mock_delete.assert_called_once_with('789012', '123456')


@pytest.mark.unit
@patch('handlers.get_guild_allowed_domains')
@patch('handlers.validate_edu_email')
@patch('handlers.generate_code')
@patch('handlers.create_verification_session')
def test_email_submission_creates_session(mock_create_session, mock_gen_code, mock_validate, mock_domains, sample_interaction):
    """Test email submission creates DynamoDB session."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'test@auburn.edu'}]}
    ]
    mock_domains.return_value = ['auburn.edu']
    mock_validate.return_value = True
    mock_gen_code.return_value = '654321'
    mock_create_session.return_value = 'verification-id-002'

    with patch('handlers.send_verification_email', return_value=True):
        # Act
        response = handle_email_submission(sample_interaction, '789012', '123456')

        # Assert
        mock_create_session.assert_called_once_with(
            '789012',
            '123456',
            'test@auburn.edu',
            '654321'
        )


@pytest.mark.unit
@patch('handlers.get_guild_allowed_domains')
@patch('handlers.validate_edu_email')
@patch('handlers.generate_code')
@patch('handlers.create_verification_session')
@patch('handlers.send_verification_email')
def test_email_submission_shows_submit_button(mock_send_email, mock_create_session, mock_gen_code, mock_validate, mock_domains, sample_interaction):
    """Test email submission returns UI with Submit Code button."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'test@auburn.edu'}]}
    ]
    mock_domains.return_value = ['auburn.edu']
    mock_validate.return_value = True
    mock_gen_code.return_value = '123456'
    mock_create_session.return_value = 'verification-id-001'
    mock_send_email.return_value = True

    # Act
    response = handle_email_submission(sample_interaction, '789012', '123456')

    # Assert
    body = json.loads(response['body'])
    components = body['data']['components']

    assert len(components) == 1
    assert components[0]['type'] == ComponentType.ACTION_ROW

    button = components[0]['components'][0]
    assert button['type'] == ComponentType.BUTTON
    assert button['style'] == ButtonStyle.PRIMARY
    assert button['label'] == 'Submit Code'
    assert button['custom_id'] == 'submit_code'


@pytest.mark.unit
@patch('guild_config.get_guild_allowed_domains')
@patch('handlers.validate_edu_email')
@patch('handlers.generate_code')
@patch('handlers.create_verification_session')
@patch('handlers.send_verification_email')
def test_email_submission_handles_multiple_domains(mock_send_email, mock_create_session, mock_gen_code, mock_validate, mock_domains, sample_interaction):
    """Test email submission with multi-domain guild config."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'test@custom.edu'}]}
    ]
    # get_guild_allowed_domains is imported locally inside handle_email_submission
    mock_domains.return_value = ['auburn.edu', 'custom.edu', 'university.edu']
    mock_validate.return_value = True
    mock_gen_code.return_value = '123456'
    mock_create_session.return_value = 'verification-id-001'
    mock_send_email.return_value = True

    # Act
    response = handle_email_submission(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    # Verify get_guild_allowed_domains was called for this guild
    mock_domains.assert_called_once_with('123456')
    # Verify validate_edu_email was called with the mocked domain list
    mock_validate.assert_called_once_with('test@custom.edu', ['auburn.edu', 'custom.edu', 'university.edu'])


@pytest.mark.unit
@patch('handlers.get_guild_allowed_domains')
@patch('handlers.validate_edu_email')
@patch('handlers.generate_code')
@patch('handlers.create_verification_session')
def test_email_submission_exception_handling(mock_create_session, mock_gen_code, mock_validate, mock_domains, sample_interaction):
    """Test email submission handles unexpected exceptions."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'test@auburn.edu'}]}
    ]
    mock_domains.return_value = ['auburn.edu']
    mock_validate.return_value = True
    mock_gen_code.return_value = '123456'
    mock_create_session.side_effect = Exception("Unexpected DynamoDB error")

    # Act
    response = handle_email_submission(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'error occurred' in body['data']['content']
    assert 'try again' in body['data']['content']


# ==============================================================================
# 5. Code Verification Tests (10 tests)
# ==============================================================================

@pytest.mark.unit
def test_code_verification_invalid_format(sample_interaction):
    """Test code verification rejects invalid code format."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': '12AB34'}]}  # Contains letters
    ]

    # Act
    response = handle_code_verification(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'valid 6-digit verification code' in body['data']['content']


@pytest.mark.unit
@patch('handlers.get_verification_session')
def test_code_verification_no_session(mock_get_session, sample_interaction):
    """Test code verification handles missing verification session."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': '123456'}]}
    ]
    mock_get_session.return_value = None

    # Act
    response = handle_code_verification(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'No pending verification found' in body['data']['content']
    assert 'start the verification process again' in body['data']['content']


@pytest.mark.unit
@patch('handlers.get_verification_session')
@patch('handlers.delete_session')
def test_code_verification_expired_code(mock_delete, mock_get_session, sample_interaction):
    """Test code verification handles expired codes."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': '123456'}]}
    ]

    # Session expired 1 minute ago
    expired_time = datetime.utcnow() - timedelta(minutes=1)
    mock_get_session.return_value = {
        'user_id': '789012',
        'guild_id': '123456',
        'code': '123456',
        'verification_id': 'test-id',
        'attempts': 0,
        'expires_at': expired_time.isoformat()
    }

    # Act
    response = handle_code_verification(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Verification code has expired' in body['data']['content']
    assert '15 minutes' in body['data']['content']

    # Verify session was deleted
    mock_delete.assert_called_once_with('789012', '123456')


@pytest.mark.unit
@patch('handlers.get_verification_session')
@patch('handlers.delete_session')
def test_code_verification_max_attempts_exceeded(mock_delete, mock_get_session, sample_interaction):
    """Test code verification rejects after max attempts."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': '123456'}]}
    ]

    future_time = datetime.utcnow() + timedelta(minutes=10)
    mock_get_session.return_value = {
        'user_id': '789012',
        'guild_id': '123456',
        'code': '654321',
        'verification_id': 'test-id',
        'attempts': 3,  # Max attempts reached
        'expires_at': future_time.isoformat()
    }

    # Act
    response = handle_code_verification(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Too many failed attempts' in body['data']['content']

    # Verify session was deleted
    mock_delete.assert_called_once_with('789012', '123456')


@pytest.mark.unit
@patch('handlers.get_verification_session')
@patch('handlers.increment_attempts')
def test_code_verification_incorrect_code_attempts_remaining(mock_increment, mock_get_session, sample_interaction):
    """Test code verification increments attempts on incorrect code."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': '111111'}]}  # Wrong code
    ]

    future_time = datetime.utcnow() + timedelta(minutes=10)
    mock_get_session.return_value = {
        'user_id': '789012',
        'guild_id': '123456',
        'code': '123456',  # Correct code
        'verification_id': 'test-id',
        'attempts': 1,
        'expires_at': future_time.isoformat()
    }
    mock_increment.return_value = 2  # Now at 2 attempts

    # Act
    response = handle_code_verification(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Incorrect code' in body['data']['content']
    assert '1 attempt(s) remaining' in body['data']['content']

    mock_increment.assert_called_once_with('test-id', '789012', '123456')


@pytest.mark.unit
@patch('handlers.get_verification_session')
@patch('handlers.increment_attempts')
@patch('handlers.delete_session')
def test_code_verification_incorrect_code_final_attempt(mock_delete, mock_increment, mock_get_session, sample_interaction):
    """Test code verification deletes session on final failed attempt."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': '111111'}]}  # Wrong code
    ]

    future_time = datetime.utcnow() + timedelta(minutes=10)
    mock_get_session.return_value = {
        'user_id': '789012',
        'guild_id': '123456',
        'code': '123456',
        'verification_id': 'test-id',
        'attempts': 2,  # 2 attempts used
        'expires_at': future_time.isoformat()
    }
    mock_increment.return_value = 3  # Max attempts reached

    # Act
    response = handle_code_verification(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Incorrect code' in body['data']['content']
    assert 'Too many failed attempts' in body['data']['content']
    assert 'Start Verification' in body['data']['content']

    # Verify session was deleted
    mock_delete.assert_called_once_with('789012', '123456')


@pytest.mark.unit
@patch('handlers.get_verification_session')
@patch('handlers.mark_verified')
@patch('handlers.get_guild_role_id')
@patch('handlers.get_parameter')
@patch('handlers.assign_role')
def test_code_verification_success_assigns_role(mock_assign_role, mock_param, mock_role_id, mock_mark_verified, mock_get_session, sample_interaction):
    """Test successful code verification assigns role."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': '123456'}]}
    ]

    future_time = datetime.utcnow() + timedelta(minutes=10)
    mock_get_session.return_value = {
        'user_id': '789012',
        'guild_id': '123456',
        'code': '123456',  # Correct code
        'verification_id': 'test-id',
        'attempts': 0,
        'expires_at': future_time.isoformat()
    }
    mock_role_id.return_value = '111222'
    mock_param.return_value = 'test_bot_token'
    mock_assign_role.return_value = True

    # Act
    response = handle_code_verification(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Verification complete' in body['data']['content']
    assert 'Welcome' in body['data']['content']

    # Verify calls
    mock_mark_verified.assert_called_once_with('test-id', '789012', '123456')
    mock_assign_role.assert_called_once_with('789012', '123456', '111222', 'test_bot_token')


@pytest.mark.unit
@patch('handlers.get_verification_session')
@patch('handlers.mark_verified')
@patch('handlers.get_guild_role_id')
@patch('handlers.get_parameter')
@patch('handlers.assign_role')
def test_code_verification_success_role_assignment_fails(mock_assign_role, mock_param, mock_role_id, mock_mark_verified, mock_get_session, sample_interaction):
    """Test code verification handles role assignment failures."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': '123456'}]}
    ]

    future_time = datetime.utcnow() + timedelta(minutes=10)
    mock_get_session.return_value = {
        'user_id': '789012',
        'guild_id': '123456',
        'code': '123456',
        'verification_id': 'test-id',
        'attempts': 0,
        'expires_at': future_time.isoformat()
    }
    mock_role_id.return_value = '111222'
    mock_param.return_value = 'test_bot_token'
    mock_assign_role.return_value = False  # Role assignment failed

    # Act
    response = handle_code_verification(sample_interaction, '789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Verification successful' in body['data']['content']
    assert 'issue assigning your role' in body['data']['content']
    assert 'contact a server administrator' in body['data']['content']

    # Verify user was still marked verified
    mock_mark_verified.assert_called_once_with('test-id', '789012', '123456')


@pytest.mark.unit
@patch('handlers.get_verification_session')
@patch('handlers.increment_attempts')
def test_code_verification_increments_attempts(mock_increment, mock_get_session, sample_interaction):
    """Test code verification increments attempt counter on failure."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': '999999'}]}  # Wrong code
    ]

    future_time = datetime.utcnow() + timedelta(minutes=10)
    mock_get_session.return_value = {
        'user_id': '789012',
        'guild_id': '123456',
        'code': '123456',
        'verification_id': 'test-verification-id',
        'attempts': 0,
        'expires_at': future_time.isoformat()
    }
    mock_increment.return_value = 1

    # Act
    response = handle_code_verification(sample_interaction, '789012', '123456')

    # Assert
    mock_increment.assert_called_once_with('test-verification-id', '789012', '123456')


@pytest.mark.unit
@patch('handlers.get_verification_session')
@patch('handlers.mark_verified')
@patch('handlers.get_guild_role_id')
@patch('handlers.get_parameter')
@patch('handlers.assign_role')
def test_code_verification_marks_verified(mock_assign_role, mock_param, mock_role_id, mock_mark_verified, mock_get_session, sample_interaction):
    """Test code verification marks user as verified in database."""
    # Arrange
    sample_interaction['data']['components'] = [
        {'components': [{'value': '123456'}]}
    ]

    future_time = datetime.utcnow() + timedelta(minutes=10)
    mock_get_session.return_value = {
        'user_id': '789012',
        'guild_id': '123456',
        'code': '123456',
        'verification_id': 'test-verification-id',
        'attempts': 0,
        'expires_at': future_time.isoformat()
    }
    mock_role_id.return_value = '111222'
    mock_param.return_value = 'test_bot_token'
    mock_assign_role.return_value = True

    # Act
    response = handle_code_verification(sample_interaction, '789012', '123456')

    # Assert
    mock_mark_verified.assert_called_once_with('test-verification-id', '789012', '123456')


# ==============================================================================
# 6. Modal Routing Tests (2 tests)
# ==============================================================================

@pytest.mark.unit
@patch('handlers.handle_email_submission')
def test_handle_modal_submit_email_modal(mock_email_handler, sample_interaction):
    """Test modal submit routes email_submission_modal correctly."""
    # Arrange
    sample_interaction['data']['custom_id'] = 'email_submission_modal'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'test@auburn.edu'}]}
    ]
    mock_email_handler.return_value = {'statusCode': 200, 'body': '{}'}

    # Act
    response = handle_modal_submit(sample_interaction)

    # Assert
    assert response['statusCode'] == 200
    mock_email_handler.assert_called_once_with(sample_interaction, '789012', '123456')


@pytest.mark.unit
@patch('handlers.handle_code_verification')
def test_handle_modal_submit_code_modal(mock_code_handler, sample_interaction):
    """Test modal submit routes code_submission_modal correctly."""
    # Arrange
    sample_interaction['data']['custom_id'] = 'code_submission_modal'
    sample_interaction['data']['components'] = [
        {'components': [{'value': '123456'}]}
    ]
    mock_code_handler.return_value = {'statusCode': 200, 'body': '{}'}

    # Act
    response = handle_modal_submit(sample_interaction)

    # Assert
    assert response['statusCode'] == 200
    mock_code_handler.assert_called_once_with(sample_interaction, '789012', '123456')


# ==============================================================================
# 7. Helper Functions Tests (2 tests)
# ==============================================================================

@pytest.mark.unit
@patch('handlers.get_verification_session')
def test_show_code_modal_with_session(mock_get_session):
    """Test show_code_modal generates modal when session exists."""
    # Arrange
    mock_get_session.return_value = {
        'user_id': '789012',
        'guild_id': '123456',
        'code': '123456',
        'verification_id': 'test-id'
    }

    # Act
    response = show_code_modal('789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.MODAL
    assert body['data']['custom_id'] == 'code_submission_modal'
    assert body['data']['title'] == 'Verification Code'

    # Verify modal components
    components = body['data']['components']
    assert len(components) == 1
    code_input = components[0]['components'][0]
    assert code_input['custom_id'] == 'verification_code'
    assert code_input['type'] == ComponentType.TEXT_INPUT
    assert code_input['min_length'] == 6
    assert code_input['max_length'] == 6
    assert code_input['required'] is True


@pytest.mark.unit
@patch('handlers.get_verification_session')
def test_show_code_modal_no_session(mock_get_session):
    """Test show_code_modal handles missing session."""
    # Arrange
    mock_get_session.return_value = None

    # Act
    response = show_code_modal('789012', '123456')

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'No pending verification found' in body['data']['content']
    assert 'Start Verification' in body['data']['content']


# ==============================================================================
# Additional Edge Case Tests
# ==============================================================================

@pytest.mark.unit
def test_ephemeral_response_format():
    """Test ephemeral_response helper creates correct format."""
    response = ephemeral_response("Test message")

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE
    assert body['data']['content'] == "Test message"
    assert body['data']['flags'] == MessageFlags.EPHEMERAL


@pytest.mark.unit
def test_error_response_format():
    """Test error_response helper prepends error emoji."""
    response = error_response("Something went wrong")

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['content'] == "❌ Something went wrong"
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
