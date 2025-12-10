"""
Unit tests for lambda/setup_handler.py module.

Tests the admin setup wizard handlers including:
- Permission validation (security-critical)
- Setup command initialization
- Select menu handling (role/channel selection)
- Continue button logic
- Domains modal submission
- Message link flow (button, modal, fetching)
- Message fetching with Discord API
- Approval flow and configuration saving
- Message posting to channels
- Cancel flow and cleanup
"""
import pytest
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
import responses

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

from setup_handler import (
    has_admin_permissions,
    handle_setup_command,
    handle_setup_select_menu,
    handle_setup_continue,
    handle_domains_modal_submit,
    handle_message_link_button,
    handle_skip_message_button,
    handle_message_modal_submit,
    handle_setup_approve,
    handle_setup_cancel,
    post_verification_message,
    ephemeral_response,
    ADMINISTRATOR_PERMISSION
)
from discord_interactions import InteractionResponseType, MessageFlags, ComponentType, ButtonStyle


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def admin_member():
    """Discord member with admin permissions."""
    return {
        'user': {
            'id': '999888',
            'username': 'admin_user',
            'discriminator': '0001'
        },
        'permissions': str(ADMINISTRATOR_PERMISSION)  # 8 = ADMINISTRATOR
    }


@pytest.fixture
def non_admin_member():
    """Discord member without admin permissions."""
    return {
        'user': {
            'id': '777666',
            'username': 'regular_user',
            'discriminator': '0002'
        },
        'permissions': '0'  # No permissions
    }


@pytest.fixture
def sample_interaction(admin_member):
    """Sample Discord interaction payload."""
    return {
        'type': 2,  # APPLICATION_COMMAND
        'guild_id': '123456',
        'channel_id': '999888',
        'member': admin_member,
        'data': {}
    }


@pytest.fixture
def sample_guild_config():
    """Sample existing guild configuration."""
    return {
        'guild_id': '123456',
        'role_id': '111222',
        'channel_id': '999888',
        'allowed_domains': ['auburn.edu', 'student.sans.edu'],
        'custom_message': 'Click to verify your email!',
        'setup_by': '999888',
        'setup_timestamp': datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_pending_setup():
    """Sample pending setup configuration."""
    return {
        'role_id': '111222',
        'channel_id': '999888',
        'allowed_domains': ['auburn.edu', 'custom.edu'],
        'custom_message': 'Verify your .edu email address!'
    }


# ==============================================================================
# 1. Permission Validation Tests (6 tests)
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_has_admin_permissions_valid_admin(admin_member):
    """Test admin permission check returns True for valid admin."""
    result = has_admin_permissions(admin_member, '123456')

    assert result is True


@pytest.mark.unit
@pytest.mark.security
def test_has_admin_permissions_no_admin(non_admin_member):
    """Test admin permission check returns False for non-admin user."""
    result = has_admin_permissions(non_admin_member, '123456')

    assert result is False


@pytest.mark.unit
@pytest.mark.security
def test_has_admin_permissions_missing_field():
    """Test admin permission check handles missing permissions field."""
    member = {
        'user': {'id': '123', 'username': 'test'}
        # Missing 'permissions' field
    }

    result = has_admin_permissions(member, '123456')

    assert result is False


@pytest.mark.unit
@pytest.mark.security
def test_has_admin_permissions_invalid_permissions_value():
    """Test admin permission check handles invalid permissions value."""
    member = {
        'user': {'id': '123', 'username': 'test'},
        'permissions': 'invalid_string'  # Cannot be converted to int
    }

    result = has_admin_permissions(member, '123456')

    assert result is False


@pytest.mark.unit
@pytest.mark.security
def test_has_admin_permissions_dm_context():
    """Test admin permission check rejects DM context."""
    member = {
        'user': {'id': '123', 'username': 'test'},
        'permissions': str(ADMINISTRATOR_PERMISSION)
    }

    # DM contexts have guild_id = '@me' or None
    result_me = has_admin_permissions(member, '@me')
    result_none = has_admin_permissions(member, None)

    assert result_me is False
    assert result_none is False


@pytest.mark.unit
@pytest.mark.security
def test_has_admin_permissions_audit_logging(admin_member, capsys):
    """Test admin permission check logs authorization attempts."""
    has_admin_permissions(admin_member, '123456')

    captured = capsys.readouterr()
    assert 'Authorization check' in captured.out
    assert 'user=admin_user(999888)' in captured.out
    assert 'guild=123456' in captured.out
    assert 'admin=True' in captured.out


# ==============================================================================
# 2. Setup Command Tests (4 tests)
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_handle_setup_command_not_admin(sample_interaction, non_admin_member):
    """Test setup command rejects non-admin users."""
    sample_interaction['member'] = non_admin_member

    response = handle_setup_command(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Administrator' in body['data']['content']
    assert 'permissions' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.is_guild_configured')
def test_handle_setup_command_new_guild(mock_configured, sample_interaction):
    """Test setup command for first-time guild setup."""
    mock_configured.return_value = False

    response = handle_setup_command(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Bot Setup' in body['data']['content']
    assert 'Select the verification role and channel' in body['data']['content']

    # Verify components
    components = body['data']['components']
    assert len(components) == 3  # Role select, channel select, continue button

    # Check role select
    assert components[0]['components'][0]['type'] == ComponentType.ROLE_SELECT
    assert components[0]['components'][0]['custom_id'] == 'setup_role_select'

    # Check channel select
    assert components[1]['components'][0]['type'] == ComponentType.CHANNEL_SELECT
    assert components[1]['components'][0]['custom_id'] == 'setup_channel_select'

    # Check continue button
    assert components[2]['components'][0]['custom_id'] == 'setup_continue'


@pytest.mark.unit
@patch('setup_handler.is_guild_configured')
@patch('setup_handler.get_guild_config')
def test_handle_setup_command_existing_config(mock_get_config, mock_configured, sample_interaction, sample_guild_config):
    """Test setup command shows existing configuration."""
    mock_configured.return_value = True
    mock_get_config.return_value = sample_guild_config

    response = handle_setup_command(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'Current Configuration' in body['data']['content']
    assert '<@&111222>' in body['data']['content']  # Role mention
    assert '<#999888>' in body['data']['content']  # Channel mention
    assert 'auburn.edu' in body['data']['content']
    assert 'student.sans.edu' in body['data']['content']
    assert 'Update the role and channel' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.is_guild_configured')
def test_handle_setup_command_shows_select_menus(mock_configured, sample_interaction):
    """Test setup command returns proper select menus."""
    mock_configured.return_value = False

    response = handle_setup_command(sample_interaction)

    body = json.loads(response['body'])
    components = body['data']['components']

    # Role select menu
    role_select = components[0]['components'][0]
    assert role_select['type'] == ComponentType.ROLE_SELECT
    assert role_select['custom_id'] == 'setup_role_select'
    assert role_select['min_values'] == 1
    assert role_select['max_values'] == 1

    # Channel select menu
    channel_select = components[1]['components'][0]
    assert channel_select['type'] == ComponentType.CHANNEL_SELECT
    assert channel_select['custom_id'] == 'setup_channel_select'
    assert channel_select['min_values'] == 1
    assert channel_select['max_values'] == 1


# ==============================================================================
# 3. Select Menu Handling Tests (4 tests)
# ==============================================================================

@pytest.mark.unit
def test_handle_setup_select_menu_role(sample_interaction):
    """Test role selection updates message with selected role."""
    sample_interaction['data']['custom_id'] = 'setup_role_select'
    sample_interaction['data']['values'] = ['111222']
    sample_interaction['message'] = {
        'content': '## ⚙️ Bot Setup\n\nSelect the verification role and channel below.',
        'components': []
    }

    response = handle_setup_select_menu(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.UPDATE_MESSAGE
    assert '✅ **Selected Role:** <@&111222>' in body['data']['content']


@pytest.mark.unit
def test_handle_setup_select_menu_channel(sample_interaction):
    """Test channel selection updates message with selected channel."""
    sample_interaction['data']['custom_id'] = 'setup_channel_select'
    sample_interaction['data']['values'] = ['999888']
    sample_interaction['message'] = {
        'content': '## ⚙️ Bot Setup\n\nSelect the verification role and channel below.',
        'components': []
    }

    response = handle_setup_select_menu(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.UPDATE_MESSAGE
    assert '✅ **Selected Channel:** <#999888>' in body['data']['content']


@pytest.mark.unit
def test_handle_setup_select_menu_no_values(sample_interaction):
    """Test select menu handles empty selection."""
    sample_interaction['data']['custom_id'] = 'setup_role_select'
    sample_interaction['data']['values'] = []

    response = handle_setup_select_menu(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Please select an option' in body['data']['content']


@pytest.mark.unit
def test_handle_setup_select_menu_updates_message(sample_interaction):
    """Test select menu updates preserve message components."""
    sample_interaction['data']['custom_id'] = 'setup_role_select'
    sample_interaction['data']['values'] = ['111222']
    original_components = [
        {'type': ComponentType.ACTION_ROW, 'components': [{'custom_id': 'test'}]}
    ]
    sample_interaction['message'] = {
        'content': 'Original content',
        'components': original_components
    }

    response = handle_setup_select_menu(sample_interaction)

    body = json.loads(response['body'])
    assert body['data']['components'] == original_components


# ==============================================================================
# 4. Continue Button Tests (6 tests)
# ==============================================================================

@pytest.mark.unit
def test_handle_setup_continue_with_selections(sample_interaction):
    """Test continue button proceeds when user made selections."""
    sample_interaction['message'] = {
        'content': '## ⚙️ Bot Setup\n\n✅ **Selected Role:** <@&111222>\n✅ **Selected Channel:** <#999888>'
    }

    response = handle_setup_continue(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.MODAL
    assert body['data']['title'] == 'Email Domains'
    assert '111222_999888' in body['data']['custom_id']


@pytest.mark.unit
@patch('setup_handler.get_guild_config')
def test_handle_setup_continue_fallback_to_existing(mock_get_config, sample_interaction, sample_guild_config):
    """Test continue button uses existing config when no new selections."""
    sample_interaction['message'] = {
        'content': '## ⚙️ Bot Setup\n\n**Current Configuration:**\n• Role: <@&111222>\n• Channel: <#999888>'
    }
    mock_get_config.return_value = sample_guild_config

    response = handle_setup_continue(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.MODAL
    assert '111222_999888' in body['data']['custom_id']


@pytest.mark.unit
@patch('setup_handler.get_guild_config')
def test_handle_setup_continue_no_role_or_channel(mock_get_config, sample_interaction):
    """Test continue button rejects when role/channel missing."""
    sample_interaction['message'] = {
        'content': '## ⚙️ Bot Setup\n\nSelect the verification role and channel below.'
    }
    mock_get_config.return_value = None  # No existing config

    response = handle_setup_continue(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Please select both a role and a channel' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.get_guild_config')
def test_handle_setup_continue_shows_domains_modal(mock_get_config, sample_interaction):
    """Test continue button shows domains modal."""
    sample_interaction['message'] = {
        'content': '## ⚙️ Bot Setup\n\n✅ **Selected Role:** <@&111222>\n✅ **Selected Channel:** <#999888>'
    }
    mock_get_config.return_value = None

    response = handle_setup_continue(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.MODAL
    assert body['data']['custom_id'].startswith('setup_domains_modal_')

    # Check modal components
    components = body['data']['components']
    assert len(components) == 1
    domain_input = components[0]['components'][0]
    assert domain_input['custom_id'] == 'allowed_domains'
    assert domain_input['type'] == ComponentType.TEXT_INPUT


@pytest.mark.unit
@patch('setup_handler.get_guild_config')
def test_handle_setup_continue_domains_required_new_guild(mock_get_config, sample_interaction):
    """Test domains required for new guild setup."""
    sample_interaction['message'] = {
        'content': '## ⚙️ Bot Setup\n\n✅ **Selected Role:** <@&111222>\n✅ **Selected Channel:** <#999888>'
    }
    mock_get_config.return_value = None  # No existing config

    response = handle_setup_continue(sample_interaction)

    body = json.loads(response['body'])
    domain_input = body['data']['components'][0]['components'][0]
    assert domain_input['label'] == 'Allowed Email Domains'
    assert domain_input['required'] is True


@pytest.mark.unit
@patch('setup_handler.get_guild_config')
def test_handle_setup_continue_domains_optional_existing_guild(mock_get_config, sample_interaction, sample_guild_config):
    """Test domains optional for existing guild reconfiguration."""
    sample_interaction['message'] = {
        'content': '## ⚙️ Bot Setup\n\n✅ **Selected Role:** <@&111222>\n✅ **Selected Channel:** <#999888>'
    }
    mock_get_config.return_value = sample_guild_config

    response = handle_setup_continue(sample_interaction)

    body = json.loads(response['body'])
    domain_input = body['data']['components'][0]['components'][0]
    assert 'optional' in domain_input['label']
    assert domain_input['required'] is False


# ==============================================================================
# 5. Domains Modal Tests (5 tests)
# ==============================================================================

@pytest.mark.unit
@patch('setup_handler.extract_role_channel_from_custom_id')
@patch('dynamodb_operations.store_pending_setup')
@patch('guild_config.get_guild_config')
def test_handle_domains_modal_submit_valid(mock_get_config, mock_store, mock_extract, sample_interaction):
    """Test domains modal submission with valid domain list."""
    sample_interaction['data']['custom_id'] = 'setup_domains_modal_111222_999888'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'auburn.edu, custom.edu, university.edu'}]}
    ]
    mock_extract.return_value = ('111222', '999888')
    mock_get_config.return_value = None

    response = handle_domains_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE
    assert 'Create Your Verification Message' in body['data']['content']

    # Check that the button exists
    components = body['data']['components']
    assert len(components) > 0
    button = components[0]['components'][0]
    assert 'Submit Message Link' in button['label']

    # Verify pending setup was stored
    mock_store.assert_called_once()
    call_args = mock_store.call_args[1]
    assert call_args['role_id'] == '111222'
    assert call_args['channel_id'] == '999888'
    assert 'auburn.edu' in call_args['allowed_domains']
    assert 'custom.edu' in call_args['allowed_domains']


@pytest.mark.unit
@patch('setup_handler.extract_role_channel_from_custom_id')
@patch('guild_config.get_guild_config')
def test_handle_domains_modal_submit_empty_new_guild(mock_get_config, mock_extract, sample_interaction):
    """Test domains modal rejects empty input for new guild."""
    sample_interaction['data']['custom_id'] = 'setup_domains_modal_111222_999888'
    sample_interaction['data']['components'] = [
        {'components': [{'value': '   '}]}  # Empty/whitespace only
    ]
    mock_extract.return_value = ('111222', '999888')
    mock_get_config.return_value = None  # No existing config

    response = handle_domains_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'specify at least one allowed email domain' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_role_channel_from_custom_id')
@patch('dynamodb_operations.store_pending_setup')
@patch('guild_config.get_guild_config')
def test_handle_domains_modal_submit_empty_existing_guild(mock_get_config, mock_store, mock_extract, sample_interaction, sample_guild_config):
    """Test domains modal uses existing domains if input empty."""
    sample_interaction['data']['custom_id'] = 'setup_domains_modal_111222_999888'
    sample_interaction['data']['components'] = [
        {'components': [{'value': ''}]}  # Empty
    ]
    mock_extract.return_value = ('111222', '999888')
    mock_get_config.return_value = sample_guild_config

    response = handle_domains_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    # Should use existing domains
    call_args = mock_store.call_args[1]
    assert call_args['allowed_domains'] == ['auburn.edu', 'student.sans.edu']


@pytest.mark.unit
@patch('setup_handler.extract_role_channel_from_custom_id')
def test_handle_domains_modal_submit_invalid_custom_id(mock_extract, sample_interaction):
    """Test domains modal handles malformed custom_id."""
    sample_interaction['data']['custom_id'] = 'setup_domains_modal_invalid'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'auburn.edu'}]}
    ]
    mock_extract.return_value = (None, None)  # Invalid extraction

    response = handle_domains_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Invalid setup state' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_role_channel_from_custom_id')
@patch('dynamodb_operations.store_pending_setup')
@patch('guild_config.get_guild_config')
def test_handle_domains_modal_submit_stores_pending_setup(mock_get_config, mock_store, mock_extract, sample_interaction):
    """Test domains modal stores pending setup in DynamoDB."""
    sample_interaction['data']['custom_id'] = 'setup_domains_modal_111222_999888'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'auburn.edu'}]}
    ]
    sample_interaction['member']['user']['id'] = '999888'
    sample_interaction['guild_id'] = '123456'
    mock_extract.return_value = ('111222', '999888')
    mock_get_config.return_value = None

    response = handle_domains_modal_submit(sample_interaction)

    # Verify store_pending_setup was called with UUID format setup_id
    mock_store.assert_called_once()
    call_args = mock_store.call_args[1]
    # Check that setup_id is a valid UUID format (not old user_id_guild_id format)
    import re
    uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
    assert re.match(uuid_pattern, call_args['setup_id']), f"setup_id should be UUID format, got: {call_args['setup_id']}"
    assert call_args['user_id'] == '999888'
    assert call_args['guild_id'] == '123456'
    assert call_args['custom_message'] == ''  # Will be filled from message link


# ==============================================================================
# 6. Message Link Flow Tests (8 tests)
# ==============================================================================

@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
def test_handle_message_link_button_shows_modal(mock_extract, sample_interaction):
    """Test message link button shows URL input modal."""
    sample_interaction['data']['custom_id'] = 'setup_message_link_999888_123456'
    mock_extract.return_value = '999888_123456'

    response = handle_message_link_button(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.MODAL
    assert body['data']['title'] == 'Message Link'
    assert 'setup_link_modal_999888_123456' in body['data']['custom_id']

    # Check modal has message link input
    components = body['data']['components']
    link_input = components[0]['components'][0]
    assert link_input['custom_id'] == 'message_link'
    assert link_input['required'] is True
    assert 'discord.com/channels' in link_input['placeholder']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
def test_handle_message_link_button_invalid_setup_id(mock_extract, sample_interaction):
    """Test message link button handles invalid setup ID."""
    sample_interaction['data']['custom_id'] = 'setup_message_link_invalid'
    mock_extract.return_value = None  # Invalid

    response = handle_message_link_button(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Invalid state' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('guild_config.get_guild_config')
@patch('dynamodb_operations.store_pending_setup')
def test_handle_skip_message_button_uses_existing(mock_store, mock_get_config, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup, sample_guild_config):
    """Test skip message button uses existing message URL."""
    sample_interaction['data']['custom_id'] = 'setup_skip_message_999888_123456'
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_get_config.return_value = sample_guild_config

    response = handle_skip_message_button(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.UPDATE_MESSAGE
    assert 'Preview Your Verification Message' in body['data']['content']
    assert 'Click to verify your email!' in body['data']['content']

    # Verify pending setup was updated with existing message
    mock_store.assert_called_once()
    call_args = mock_store.call_args[1]
    assert call_args['custom_message'] == 'Click to verify your email!'


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('guild_config.get_guild_config')
def test_handle_skip_message_button_no_existing_message(mock_get_config, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test skip message button handles no existing message."""
    sample_interaction['data']['custom_id'] = 'setup_skip_message_999888_123456'
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_get_config.return_value = None  # No existing config

    response = handle_skip_message_button(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'No existing message found' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
def test_handle_skip_message_button_expired_session(mock_get_pending, mock_extract, sample_interaction):
    """Test skip message button handles expired setup session."""
    sample_interaction['data']['custom_id'] = 'setup_skip_message_999888_123456'
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = None  # Session expired

    response = handle_skip_message_button(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Setup session expired' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('setup_handler.validate_discord_message_url')
@patch('setup_handler.get_parameter')
@responses.activate
def test_handle_message_modal_submit_valid_link(mock_param, mock_validate, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test message modal submission with valid Discord message URL."""
    sample_interaction['data']['custom_id'] = 'setup_link_modal_999888_123456'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'https://discord.com/channels/123456/999888/777666'}]}
    ]
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_validate.return_value = ('123456', '999888', '777666')
    mock_param.return_value = 'test_bot_token'

    # Mock Discord API response
    responses.add(
        responses.GET,
        'https://discord.com/api/v10/channels/999888/messages/777666',
        json={
            'id': '777666',
            'content': 'Click the button to verify!',
            'author': {'id': '123', 'username': 'bot'}
        },
        status=200
    )

    response = handle_message_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'Preview Your Verification Message' in body['data']['content']
    assert 'Click the button to verify!' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('setup_handler.validate_discord_message_url')
def test_handle_message_modal_submit_invalid_link(mock_validate, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test message modal submission with invalid URL format."""
    sample_interaction['data']['custom_id'] = 'setup_link_modal_999888_123456'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'https://not-discord.com/invalid'}]}
    ]
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_validate.return_value = (None, None, None)  # Invalid URL

    response = handle_message_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Invalid message link' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('setup_handler.validate_discord_message_url')
def test_handle_message_modal_submit_wrong_guild(mock_validate, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test message modal submission with URL from different guild."""
    sample_interaction['data']['custom_id'] = 'setup_link_modal_999888_123456'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'https://discord.com/channels/999999/888888/777777'}]}
    ]
    sample_interaction['guild_id'] = '123456'
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_validate.return_value = (None, None, None)  # Validation fails (wrong guild)

    response = handle_message_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Invalid message link' in body['data']['content']


# ==============================================================================
# 7. Message Fetching Tests (6 tests)
# ==============================================================================

@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('setup_handler.validate_discord_message_url')
@patch('ssm_utils.get_parameter')
@responses.activate
def test_message_modal_submit_fetch_success(mock_param, mock_validate, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test successful message fetch from Discord API."""
    sample_interaction['data']['custom_id'] = 'setup_link_modal_999888_123456'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'https://discord.com/channels/123456/999888/777666'}]}
    ]
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_validate.return_value = ('123456', '999888', '777666')
    mock_param.return_value = 'test_bot_token'

    responses.add(
        responses.GET,
        'https://discord.com/api/v10/channels/999888/messages/777666',
        json={'id': '777666', 'content': 'Verify your email!'},
        status=200
    )

    response = handle_message_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    assert len(responses.calls) == 1
    assert 'Bot test_bot_token' in responses.calls[0].request.headers['Authorization']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('setup_handler.validate_discord_message_url')
@patch('ssm_utils.get_parameter')
@responses.activate
def test_message_modal_submit_fetch_404(mock_param, mock_validate, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test message fetch with 404 (message not found)."""
    sample_interaction['data']['custom_id'] = 'setup_link_modal_999888_123456'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'https://discord.com/channels/123456/999888/777666'}]}
    ]
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_validate.return_value = ('123456', '999888', '777666')
    mock_param.return_value = 'test_bot_token'

    responses.add(
        responses.GET,
        'https://discord.com/api/v10/channels/999888/messages/777666',
        json={'message': 'Unknown Message'},
        status=404
    )

    response = handle_message_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Could not fetch message' in body['data']['content']
    assert 'message exists' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('setup_handler.validate_discord_message_url')
@patch('ssm_utils.get_parameter')
@responses.activate
def test_message_modal_submit_fetch_403(mock_param, mock_validate, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test message fetch with 403 (no permission)."""
    sample_interaction['data']['custom_id'] = 'setup_link_modal_999888_123456'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'https://discord.com/channels/123456/999888/777666'}]}
    ]
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_validate.return_value = ('123456', '999888', '777666')
    mock_param.return_value = 'test_bot_token'

    responses.add(
        responses.GET,
        'https://discord.com/api/v10/channels/999888/messages/777666',
        json={'message': 'Missing Permissions'},
        status=403
    )

    response = handle_message_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'Could not fetch message' in body['data']['content']
    assert 'permission to view the channel' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('setup_handler.validate_discord_message_url')
@patch('ssm_utils.get_parameter')
@responses.activate
def test_message_modal_submit_empty_message(mock_param, mock_validate, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test message fetch when message has no text content."""
    sample_interaction['data']['custom_id'] = 'setup_link_modal_999888_123456'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'https://discord.com/channels/123456/999888/777666'}]}
    ]
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_validate.return_value = ('123456', '999888', '777666')
    mock_param.return_value = 'test_bot_token'

    responses.add(
        responses.GET,
        'https://discord.com/api/v10/channels/999888/messages/777666',
        json={'id': '777666', 'content': ''},  # Empty content
        status=200
    )

    response = handle_message_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'message appears to be empty' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('setup_handler.validate_discord_message_url')
@patch('ssm_utils.get_parameter')
@responses.activate
def test_message_modal_submit_api_exception(mock_param, mock_validate, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test message fetch handles Discord API exceptions."""
    sample_interaction['data']['custom_id'] = 'setup_link_modal_999888_123456'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'https://discord.com/channels/123456/999888/777666'}]}
    ]
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_validate.return_value = ('123456', '999888', '777666')
    mock_param.side_effect = Exception("SSM error")

    response = handle_message_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Error fetching message' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
def test_message_modal_submit_expired_session(mock_get_pending, mock_extract, sample_interaction):
    """Test message modal handles expired setup session."""
    sample_interaction['data']['custom_id'] = 'setup_link_modal_999888_123456'
    sample_interaction['data']['components'] = [
        {'components': [{'value': 'https://discord.com/channels/123456/999888/777666'}]}
    ]
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = None  # Expired

    response = handle_message_modal_submit(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Setup session expired' in body['data']['content']


# ==============================================================================
# 8. Approval Flow Tests (5 tests)
# ==============================================================================

@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('setup_handler.save_guild_config')
@patch('setup_handler.post_verification_message')
@patch('dynamodb_operations.delete_pending_setup')
def test_handle_setup_approve_success(mock_delete, mock_post, mock_save, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test approval flow successfully saves config and posts message."""
    sample_interaction['data']['custom_id'] = 'setup_approve_999888_123456'
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_save.return_value = True
    mock_post.return_value = True

    response = handle_setup_approve(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.UPDATE_MESSAGE
    assert 'Setup Complete' in body['data']['content']
    assert '<@&111222>' in body['data']['content']  # Role mention
    assert '<#999888>' in body['data']['content']  # Channel mention

    # Verify calls
    mock_save.assert_called_once_with(
        '123456',  # guild_id
        '111222',  # role_id
        '999888',  # channel_id
        '999888',  # user_id (from member)
        ['auburn.edu', 'custom.edu'],
        'Verify your .edu email address!'
    )
    mock_post.assert_called_once_with('123456', '999888', 'Verify your .edu email address!')
    mock_delete.assert_called_once_with('999888_123456', '123456')  # Now includes guild_id parameter


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
def test_handle_setup_approve_invalid_setup_id(mock_extract, sample_interaction):
    """Test approval flow handles invalid setup ID."""
    sample_interaction['data']['custom_id'] = 'setup_approve_invalid'
    mock_extract.return_value = None

    response = handle_setup_approve(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Invalid approval state' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
def test_handle_setup_approve_expired_session(mock_get_pending, mock_extract, sample_interaction):
    """Test approval flow handles expired setup session."""
    sample_interaction['data']['custom_id'] = 'setup_approve_999888_123456'
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = None

    response = handle_setup_approve(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Setup session expired' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
def test_handle_setup_approve_missing_config_data(mock_get_pending, mock_extract, sample_interaction):
    """Test approval flow handles incomplete configuration data."""
    sample_interaction['data']['custom_id'] = 'setup_approve_999888_123456'
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = {
        'role_id': '111222'
        # Missing channel_id, allowed_domains, custom_message
    }

    response = handle_setup_approve(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Invalid configuration data' in body['data']['content']


@pytest.mark.unit
@patch('setup_handler.extract_setup_id_from_custom_id')
@patch('dynamodb_operations.get_pending_setup')
@patch('setup_handler.save_guild_config')
def test_handle_setup_approve_save_failure(mock_save, mock_get_pending, mock_extract, sample_interaction, sample_pending_setup):
    """Test approval flow handles DynamoDB save failures."""
    sample_interaction['data']['custom_id'] = 'setup_approve_999888_123456'
    mock_extract.return_value = '999888_123456'
    mock_get_pending.return_value = sample_pending_setup
    mock_save.return_value = False  # Save failed

    response = handle_setup_approve(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
    assert 'Failed to save configuration' in body['data']['content']


# ==============================================================================
# 9. Message Posting Tests (4 tests)
# ==============================================================================

@pytest.mark.unit
@patch('setup_handler.get_parameter')
@responses.activate
def test_post_verification_message_success(mock_param):
    """Test successful message post to Discord channel."""
    mock_param.return_value = 'test_bot_token'

    responses.add(
        responses.POST,
        'https://discord.com/api/v10/channels/999888/messages',
        json={'id': '123456', 'content': 'Posted!'},
        status=200
    )

    result = post_verification_message('123456', '999888', 'Click to verify!')

    assert result is True
    assert len(responses.calls) == 1

    # Verify request body
    request_body = json.loads(responses.calls[0].request.body)
    assert request_body['content'] == 'Click to verify!'
    assert len(request_body['components']) == 1
    assert request_body['components'][0]['components'][0]['custom_id'] == 'start_verification'


@pytest.mark.unit
@patch('setup_handler.get_parameter')
@responses.activate
def test_post_verification_message_403_forbidden(mock_param):
    """Test message post with 403 (no permission)."""
    mock_param.return_value = 'test_bot_token'

    responses.add(
        responses.POST,
        'https://discord.com/api/v10/channels/999888/messages',
        json={'message': 'Missing Permissions'},
        status=403
    )

    result = post_verification_message('123456', '999888', 'Click to verify!')

    assert result is False


@pytest.mark.unit
@patch('setup_handler.get_parameter')
@responses.activate
def test_post_verification_message_404_not_found(mock_param):
    """Test message post with 404 (channel not found)."""
    mock_param.return_value = 'test_bot_token'

    responses.add(
        responses.POST,
        'https://discord.com/api/v10/channels/999888/messages',
        json={'message': 'Unknown Channel'},
        status=404
    )

    result = post_verification_message('123456', '999888', 'Click to verify!')

    assert result is False


@pytest.mark.unit
@patch('setup_handler.get_parameter')
def test_post_verification_message_exception(mock_param):
    """Test message post handles exceptions."""
    mock_param.side_effect = Exception("Network error")

    result = post_verification_message('123456', '999888', 'Click to verify!')

    assert result is False


# ==============================================================================
# 10. Cancel Flow Tests (1 test)
# ==============================================================================

@pytest.mark.unit
def test_handle_setup_cancel(sample_interaction):
    """Test cancel button aborts setup and shows confirmation."""
    response = handle_setup_cancel(sample_interaction)

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.UPDATE_MESSAGE
    assert 'Setup cancelled' in body['data']['content']
    assert 'No changes were made' in body['data']['content']
    assert len(body['data']['components']) == 0  # Buttons removed


# ==============================================================================
# Additional Helper Tests
# ==============================================================================

@pytest.mark.unit
def test_ephemeral_response_helper():
    """Test ephemeral_response helper creates correct format."""
    response = ephemeral_response("Test content")

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE
    assert body['data']['content'] == "Test content"
    assert body['data']['flags'] == MessageFlags.EPHEMERAL
